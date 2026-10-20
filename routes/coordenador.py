import sqlite3
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, g
from datetime import date

coordenador_bp = Blueprint('coordenador', __name__)

DATABASE = 'database.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON;')
    return g.db

@coordenador_bp.route('/dashboardCoordenador')
def dashboard_coordenador():
    if 'user_id' not in session or session.get('tipo') != 'coordenador':
        return redirect(url_for('auth.login'))

    db = get_db()
    user = db.execute('SELECT nome, tipo FROM usuarios WHERE id = ?', (session['user_id'],)).fetchone()

    media_geral_db = db.execute('''
        SELECT AVG(nota) AS media FROM avaliacoes WHERE nota IS NOT NULL
    ''').fetchone()
    
    media_geral = round(media_geral_db['media'], 1) if media_geral_db and media_geral_db['media'] is not None else 0.0

    # Turmas não têm mais professor responsável: lista os professores
    # que lecionam alguma disciplina na turma (via turma_disciplinas).
    turmas = db.execute('''
        SELECT t.id, t.nome,
               GROUP_CONCAT(DISTINCT u.nome) AS professores
        FROM turmas t
        LEFT JOIN turma_disciplinas td ON td.turma_id = t.id
        LEFT JOIN usuarios u ON u.id = td.professor_id
        GROUP BY t.id
        ORDER BY t.nome
    ''').fetchall()

    alunos_por_turma = {}
    total_alunos = 0
    for turma in turmas:
        alunos = db.execute('SELECT id, nome, email FROM alunos WHERE turma_id = ?', (turma['id'],)).fetchall()
        alunos_por_turma[turma['id']] = alunos
        total_alunos += len(alunos)

    total_turmas = len(turmas)
    total_presencas = 0
    total_aulas = 0

    for turma in turmas:
        alunos = alunos_por_turma.get(turma['id'], [])
        for aluno in alunos:
            presencas = db.execute('SELECT presente FROM presencas WHERE aluno_id = ?', (aluno['id'],)).fetchall()
            total_presencas += sum(p['presente'] for p in presencas)
            total_aulas += len(presencas)

    frequencia_media = round(total_presencas / total_aulas * 100) if total_aulas > 0 else 0

    alertas_turmas = db.execute('''
        SELECT t.id, AVG(av.nota) as media_turma
        FROM turmas t
        LEFT JOIN alunos a ON a.turma_id = t.id
        LEFT JOIN avaliacoes av ON av.aluno_id = a.id
        GROUP BY t.id
        HAVING media_turma IS NOT NULL AND media_turma < 6.0
    ''').fetchall()
    
    total_alertas = len(alertas_turmas)

    return render_template(
        'dashboardCoordenador.html',
        nome=user['nome'],
        tipo=user['tipo'],
        turmas=turmas,
        alunos_por_turma=alunos_por_turma,
        total_turmas=total_turmas,
        total_alunos=total_alunos,
        frequencia_media=frequencia_media,
        media_geral=media_geral,
        total_alertas=total_alertas
    )

@coordenador_bp.route('/perfilCoordenador')
def perfil_coordenador():
    if 'user_id' not in session or session.get('tipo') != 'coordenador':
        flash('Acesso restrito a coordenadores.', 'error')
        return redirect(url_for('auth.login'))

    db = get_db()

    usuario = db.execute(
        'SELECT * FROM usuarios WHERE id = ?',
        (session['user_id'],)
    ).fetchone()

    total_professores = db.execute(
        "SELECT COUNT(*) FROM usuarios WHERE tipo = 'professor'"
    ).fetchone()[0]

    total_turmas = db.execute(
        "SELECT COUNT(*) FROM turmas"
    ).fetchone()[0]

    total_alunos = db.execute(
        "SELECT COUNT(*) FROM alunos"
    ).fetchone()[0]

    return render_template(
        'perfilCoordenador.html',
        usuario=usuario,
        total_professores=total_professores,
        total_turmas=total_turmas,
        total_alunos=total_alunos
    )

@coordenador_bp.route('/adicionarTurma', methods=['GET', 'POST'])
def adicionar_turma():
    if session.get('tipo') != 'coordenador':
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        nome = request.form['nome'].strip()

        if not nome:
            flash('Informe o nome da turma.', 'error')
            return redirect(url_for('coordenador.adicionar_turma'))

        db = get_db()
        db.execute("INSERT INTO turmas (nome) VALUES (?)", (nome,))
        db.commit()
        flash('Turma criada com sucesso!', 'success')
        return redirect(url_for('coordenador.dashboard_coordenador'))

    return render_template('adicionarTurma.html')

@coordenador_bp.route('/adicionarAluno', methods=['GET', 'POST'])
def adicionar_aluno():
    if session.get('tipo') != 'coordenador':
        return redirect(url_for('auth.login'))

    db = get_db()
    turmas = db.execute("SELECT id, nome FROM turmas ORDER BY nome").fetchall()

    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        turma_id = request.form['turma_id']

        db.execute(
            "INSERT INTO alunos (nome, email, turma_id) VALUES (?, ?, ?)",
            (nome, email, turma_id)
        )
        db.commit()
        flash('Aluno adicionado com sucesso!', 'success')
        return redirect(url_for('coordenador.dashboard_coordenador'))

    return render_template('adicionarAluno.html', turmas=turmas)

@coordenador_bp.route('/adicionarDisciplina', methods=['GET', 'POST'])
def adicionar_disciplina():
    if session.get('tipo') != 'coordenador':
        return redirect(url_for('auth.login'))

    db = get_db()
    professores = db.execute(
        "SELECT id, nome FROM usuarios WHERE tipo = 'professor' ORDER BY nome"
    ).fetchall()
    turmas = db.execute(
        "SELECT id, nome FROM turmas ORDER BY nome"
    ).fetchall()

    if request.method == 'POST':
        nome = request.form['nome'].strip()
        professor_id = request.form['professor_id']
        turmas_ids = request.form.getlist('turmas')

        if not nome:
            flash('Informe o nome da disciplina.', 'error')
            return redirect(url_for('coordenador.adicionar_disciplina'))

        if not turmas_ids:
            flash('Selecione ao menos uma turma.', 'error')
            return redirect(url_for('coordenador.adicionar_disciplina'))

        # Reaproveita a disciplina se ela já existir (nome é UNIQUE)
        disc = db.execute('SELECT id FROM disciplinas WHERE nome = ?', (nome,)).fetchone()
        if disc:
            disciplina_id = disc['id']
        else:
            disciplina_id = db.execute(
                "INSERT INTO disciplinas (nome) VALUES (?)", (nome,)
            ).lastrowid

        # Vincula disciplina + professor a cada turma selecionada.
        # Se já existir o vínculo, apenas troca o professor.
        for turma_id in turmas_ids:
            db.execute('''
                INSERT INTO turma_disciplinas (turma_id, disciplina_id, professor_id)
                VALUES (?, ?, ?)
                ON CONFLICT(turma_id, disciplina_id)
                DO UPDATE SET professor_id = excluded.professor_id
            ''', (turma_id, disciplina_id, professor_id))

        db.commit()
        flash('Disciplina adicionada e vinculada às turmas!', 'success')
        return redirect(url_for('coordenador.dashboard_coordenador'))

    return render_template(
        'adicionarDisciplina.html',
        professores=professores,
        turmas=turmas
    )

@coordenador_bp.route('/relatorio/coordenador/<int:turma_id>', methods=['GET', 'POST'])
def relatorio_coordenador(turma_id):
    if 'user_id' not in session or session.get('tipo') != 'coordenador':
        return redirect(url_for('auth.login'))

    db = get_db()

    turma = db.execute('''
        SELECT t.id, t.nome
        FROM turmas t
        WHERE t.id = ?
    ''', (turma_id,)).fetchone()

    if not turma:
        abort(404)

    # Busca as disciplinas e os respectivos professores desta turma
    disciplinas = db.execute('''
        SELECT d.nome, u.nome AS professor_disciplina
        FROM turma_disciplinas td
        JOIN disciplinas d ON d.id = td.disciplina_id
        JOIN usuarios u ON u.id = td.professor_id
        WHERE td.turma_id = ?
        ORDER BY d.nome
    ''', (turma_id,)).fetchall()

    # Aluno, disciplina, professor da disciplina e média do aluno nela
    alunos = db.execute('''
        SELECT a.nome AS aluno_nome,
               d.nome AS disciplina_nome,
               u.nome AS professor_nome,
               AVG(av.nota) AS media
        FROM alunos a
        JOIN turma_disciplinas td ON td.turma_id = a.turma_id
        JOIN disciplinas d ON d.id = td.disciplina_id
        JOIN usuarios u ON u.id = td.professor_id
        LEFT JOIN avaliacoes av ON av.aluno_id = a.id AND av.disciplina_id = d.id
        WHERE a.turma_id = ?
        GROUP BY a.id, d.id
        ORDER BY a.nome, d.nome
    ''', (turma_id,)).fetchall()

    # Média geral da turma
    media_geral_res = db.execute('''
        SELECT AVG(av.nota) as media_geral
        FROM avaliacoes av
        JOIN alunos a ON a.id = av.aluno_id
        WHERE a.turma_id = ?
    ''', (turma_id,)).fetchone()

    media_geral = round(media_geral_res['media_geral'], 2) if media_geral_res and media_geral_res['media_geral'] else 0

    freq = db.execute('''
        SELECT COUNT(*) total, COALESCE(SUM(presente), 0) presencas
        FROM presencas
        WHERE turma_id = ?
    ''', (turma_id,)).fetchone()

    frequencia = round((freq['presencas'] / freq['total']) * 100) if freq['total'] else 0

    html = render_template(
        'relatorioCoordenador_pdf.html',
        turma=turma,
        disciplinas=disciplinas,
        alunos=alunos,
        media_geral=media_geral,
        frequencia=frequencia,
        data=date.today().strftime('%d/%m/%Y'),
        coordenador=session['nome']
    )

    db.execute('''
        INSERT INTO relatorios
        (tipo, referencia_id, titulo, data, html, criado_por)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (
        'coordenador',
        turma_id,
        f"Relatório da Turma {turma['nome']}",
        date.today().strftime('%Y-%m-%d'),
        html,
        session['user_id']
    ))
    db.commit()

    return redirect(url_for('professor.relatorios'))

@coordenador_bp.route('/adicionarCoordenador')
def adicionar_coordenador():
    if 'user_id' not in session or session.get('tipo') != 'coordenador':
        flash('Acesso permitido apenas para coordenadores.', 'error')
        return redirect(url_for('auth.login'))
    return render_template('adicionarCoordenador.html')

@coordenador_bp.route('/turma/<int:turma_id>')
def verTurma(turma_id):
    if 'user_id' not in session or session.get('tipo') != 'coordenador':
        return redirect(url_for('auth.login'))

    db = get_db()
    turma = db.execute(
        'SELECT id, nome FROM turmas WHERE id = ?',
        (turma_id,)
    ).fetchone()

    if not turma:
        flash('Turma não encontrada.', 'error')
        return redirect(url_for('coordenador.dashboard_coordenador'))

    # Disciplinas da turma com o professor que leciona cada uma
    disciplinas = db.execute('''
        SELECT d.id, d.nome, u.nome AS professor_disciplina
        FROM turma_disciplinas td
        JOIN disciplinas d ON d.id = td.disciplina_id
        JOIN usuarios u ON u.id = td.professor_id
        WHERE td.turma_id = ?
        ORDER BY d.nome
    ''', (turma_id,)).fetchall()

    alunos = db.execute('''
        SELECT id, nome, email
        FROM alunos
        WHERE turma_id = ?
        ORDER BY nome
    ''', (turma_id,)).fetchall()

    total_presencas = 0
    total_aulas = 0
    for aluno in alunos:
        presencas = db.execute('SELECT presente FROM presencas WHERE aluno_id = ? AND turma_id = ?', (aluno['id'], turma_id)).fetchall()
        total_presencas += sum(p['presente'] for p in presencas)
        total_aulas += len(presencas)

    frequencia_geral = round((total_presencas / total_aulas) * 100) if total_aulas else 0

    return render_template(
        'verTurma.html',
        nome=session.get('nome'),
        tipo=session.get('tipo'),
        turma=turma,
        disciplinas=disciplinas,
        alunos=alunos,
        frequencia_geral=frequencia_geral
    )