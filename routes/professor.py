from flask import Blueprint, render_template, request, g, redirect, url_for, flash, session, abort, send_file
from datetime import date
import sqlite3
from xhtml2pdf import pisa
import io

professor_bp = Blueprint('professor', __name__)
DATABASE = 'database.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON;')
    return g.db

def professor_leciona_na_turma(turma_id):
    """True se o usuário logado leciona alguma disciplina na turma."""
    db = get_db()
    return db.execute(
        'SELECT 1 FROM turma_disciplinas WHERE turma_id = ? AND professor_id = ?',
        (turma_id, session.get('user_id'))
    ).fetchone() is not None

def pode_acessar_turma(turma_id):
    if 'user_id' not in session:
        return False

    db = get_db()
    turma = db.execute('SELECT id FROM turmas WHERE id = ?', (turma_id,)).fetchone()
    if not turma:
        return False

    if session.get('tipo') == 'coordenador':
        return True

    return session.get('tipo') == 'professor' and professor_leciona_na_turma(turma_id)

def disciplinas_permitidas(turma_id):
    """Disciplinas da turma que o usuário logado pode lançar/consultar.
    Coordenador vê todas; professor vê apenas as que ele leciona."""
    db = get_db()
    if session.get('tipo') == 'coordenador':
        return db.execute('''
            SELECT d.id, d.nome
            FROM turma_disciplinas td
            JOIN disciplinas d ON d.id = td.disciplina_id
            WHERE td.turma_id = ?
            ORDER BY d.nome
        ''', (turma_id,)).fetchall()

    return db.execute('''
        SELECT d.id, d.nome
        FROM turma_disciplinas td
        JOIN disciplinas d ON d.id = td.disciplina_id
        WHERE td.turma_id = ? AND td.professor_id = ?
        ORDER BY d.nome
    ''', (turma_id, session.get('user_id'))).fetchall()

def filtro_disciplinas(tipo, turma_id, coluna):
    """Devolve (sql, params) para limitar uma consulta às disciplinas que o
    professor leciona na turma. Coordenador não tem filtro."""
    if tipo == 'professor':
        sql = (
            f" AND {coluna} IN (SELECT disciplina_id FROM turma_disciplinas "
            "WHERE turma_id = ? AND professor_id = ?)"
        )
        return sql, (turma_id, session['user_id'])
    return '', ()

def dashboard_do_usuario():
    if session.get('tipo') == 'coordenador':
        return redirect(url_for('coordenador.dashboard_coordenador'))
    return redirect(url_for('professor.dashboardProfessor'))

@professor_bp.route('/dashboardProfessor')
def dashboardProfessor():
    if 'user_id' not in session or session.get('tipo') != 'professor':
        return redirect(url_for('auth.login'))

    db = get_db()
    user_id = session['user_id']

    user = db.execute(
        'SELECT nome FROM usuarios WHERE id = ?',
        (session['user_id'],)
    ).fetchone()


    media_geral_db = db.execute('''
        SELECT AVG(a.nota) AS media
        FROM avaliacoes a
        JOIN turma_disciplinas td 
          ON a.disciplina_id = td.disciplina_id 
         AND a.aluno_id IN (SELECT id FROM alunos WHERE turma_id = td.turma_id)
        WHERE td.professor_id = ? AND a.nota IS NOT NULL
    ''', (user_id,)).fetchone()

    media_geral = round(media_geral_db['media'], 1) if media_geral_db and media_geral_db['media'] is not None else 0.0

    turmas = db.execute('''
        SELECT DISTINCT t.id, t.nome
        FROM turmas t
        JOIN turma_disciplinas td ON td.turma_id = t.id
        WHERE td.professor_id = ?
        ORDER BY t.nome
    ''', (session['user_id'],)).fetchall()

    disciplinas_por_turma = {}
    for turma in turmas:
        disciplinas = db.execute('''
            SELECT d.nome
            FROM disciplinas d
            JOIN turma_disciplinas td ON d.id = td.disciplina_id
            WHERE td.turma_id = ? AND td.professor_id = ?
            ORDER BY d.nome
        ''', (turma['id'], session['user_id'])).fetchall()
        disciplinas_por_turma[turma['id']] = disciplinas

    alunos_por_turma = {}
    total_alunos = 0
    for turma in turmas:
        alunos = db.execute(
            'SELECT id, nome, email FROM alunos WHERE turma_id = ?',
            (turma['id'],)
        ).fetchall()
        alunos_por_turma[turma['id']] = alunos
        total_alunos += len(alunos)

    total_presencas = 0
    total_aulas = 0
    for turma in turmas:
        alunos = alunos_por_turma.get(turma['id'], [])
        for aluno in alunos:
            presencas = db.execute(
                '''
                SELECT presente FROM presencas
                WHERE aluno_id = ?
                  AND disciplina_id IN (
                      SELECT disciplina_id FROM turma_disciplinas
                      WHERE turma_id = ? AND professor_id = ?
                  )
                ''',
                (aluno['id'], turma['id'], session['user_id'])
            ).fetchall()
            total_presencas += sum(p['presente'] for p in presencas)
            total_aulas += len(presencas)

    frequencia_media = round(total_presencas / total_aulas * 100) if total_aulas > 0 else 0

    alertas_alunos = db.execute('''
        SELECT a.id, AVG(av.nota) AS media_aluno
        FROM alunos a
        JOIN avaliacoes av ON av.aluno_id = a.id
        JOIN turma_disciplinas td ON td.disciplina_id = av.disciplina_id AND td.turma_id = a.turma_id
        WHERE td.professor_id = ? AND av.nota IS NOT NULL
        GROUP BY a.id, av.disciplina_id
        HAVING media_aluno < 6.0
    ''', (user_id,)).fetchall()

    total_alertas = len(alertas_alunos)

    return render_template(
        'dashboardProfessor.html',
        nome=user['nome'],
        turmas=turmas,
        disciplinas_por_turma=disciplinas_por_turma,
        alunos_por_turma=alunos_por_turma,
        total_alunos=total_alunos,
        frequencia_media=frequencia_media,
        media_geral=media_geral,
        total_alertas=total_alertas
    )

@professor_bp.route('/perfilProfessor')
def perfilProfessor():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    db = get_db()

    usuario = db.execute(
        'SELECT id, nome, email FROM usuarios WHERE id = ?',
        (session['user_id'],)
    ).fetchone()

    disciplinas = db.execute('''
        SELECT DISTINCT d.nome
        FROM disciplinas d
        JOIN turma_disciplinas td ON td.disciplina_id = d.id
        WHERE td.professor_id = ?
        ORDER BY d.nome
    ''', (session['user_id'],)).fetchall()

    turmas = db.execute('''
        SELECT t.id, t.nome AS turma_nome,
               GROUP_CONCAT(d.nome, ', ') AS disciplinas
        FROM turmas t
        JOIN turma_disciplinas td ON td.turma_id = t.id
        JOIN disciplinas d ON d.id = td.disciplina_id
        WHERE td.professor_id = ?
        GROUP BY t.id
        ORDER BY t.nome
    ''', (session['user_id'],)).fetchall()

    total_alunos = db.execute('''
        SELECT COUNT(*)
        FROM alunos
        WHERE turma_id IN (
            SELECT turma_id FROM turma_disciplinas WHERE professor_id = ?
        )
    ''', (session['user_id'],)).fetchone()[0]

    return render_template(
        'perfilProfessor.html',
        usuario=usuario,
        turmas=turmas,
        disciplinas=disciplinas,
        total_alunos=total_alunos
    )

@professor_bp.route('/ata/turma/<int:turma_id>', methods=['GET'])
def ata(turma_id):
    if 'user_id' not in session:
        flash('Faça login para acessar.', 'error')
        return redirect(url_for('auth.login'))

    if not pode_acessar_turma(turma_id):
        abort(403)

    db = get_db()

    turma = db.execute(
        'SELECT nome FROM turmas WHERE id = ?',
        (turma_id,)
    ).fetchone()

    disciplinas = disciplinas_permitidas(turma_id)
    if not disciplinas:
        flash('Esta turma ainda não tem disciplinas atribuídas.', 'error')
        return dashboard_do_usuario()

    ids_permitidos = [d['id'] for d in disciplinas]
    disciplina_id = request.args.get('disciplina_id', type=int)
    if disciplina_id is None:
        disciplina_id = ids_permitidos[0]
    elif disciplina_id not in ids_permitidos:
        abort(403)

    disciplina_nome = next(d['nome'] for d in disciplinas if d['id'] == disciplina_id)

    data_hoje = date.today().strftime('%Y-%m-%d')
    datas_aulas = [data_hoje]

    alunos_db = db.execute(
        'SELECT id, nome FROM alunos WHERE turma_id = ? ORDER BY nome',
        (turma_id,)
    ).fetchall()

    alunos = []
    for aluno in alunos_db:
        presencas_db = db.execute(
            '''
            SELECT data, presente FROM presencas
            WHERE aluno_id = ? AND turma_id = ? AND disciplina_id = ?
            ''',
            (aluno['id'], turma_id, disciplina_id)
        ).fetchall()

        presencas_dict = {p['data']: p['presente'] for p in presencas_db}

        alunos.append({
            'id': aluno['id'],
            'nome': aluno['nome'],
            'presencas': presencas_dict
        })

    observacoes = db.execute(
        '''
        SELECT data, texto FROM observacoes
        WHERE turma_id = ? AND disciplina_id = ?
        ORDER BY data DESC
        ''',
        (turma_id, disciplina_id)
    ).fetchall()

    return render_template(
        'ata.html',
        turma_nome=turma['nome'],
        turma_id=turma_id,
        disciplinas=disciplinas,
        disciplina_id=disciplina_id,
        disciplina_nome=disciplina_nome,
        datas_aulas=datas_aulas,
        alunos=alunos,
        observacoes=observacoes,
        data_hoje=data_hoje
    )

@professor_bp.route('/ata/turma/<int:turma_id>', methods=['POST'])
def salvar_presencas(turma_id):
    if 'user_id' not in session:
        flash('Faça login para acessar.', 'error')
        return redirect(url_for('auth.login'))

    if not pode_acessar_turma(turma_id):
        abort(403)

    db = get_db()

    # A chamada é sempre de UMA disciplina; valida se o usuário pode lançá-la
    disciplina_id = request.form.get('disciplina_id', type=int)
    ids_permitidos = [d['id'] for d in disciplinas_permitidas(turma_id)]
    if disciplina_id not in ids_permitidos:
        abort(403)

    data_hoje = date.today().strftime('%Y-%m-%d')
    observacao = request.form.get('observacao')

    if observacao:
        existente = db.execute(
            '''
            SELECT id FROM observacoes
            WHERE turma_id = ? AND disciplina_id = ? AND data = ?
            ''',
            (turma_id, disciplina_id, data_hoje)
        ).fetchone()

        if existente:
            db.execute(
                'UPDATE observacoes SET texto = ? WHERE id = ?',
                (observacao, existente['id'])
            )
        else:
            db.execute(
                'INSERT INTO observacoes (turma_id, disciplina_id, data, texto) VALUES (?, ?, ?, ?)',
                (turma_id, disciplina_id, data_hoje, observacao)
            )

    marcados = set()
    for key in request.form:
        if key.startswith('presenca-'):
            partes = key.split('-', 2)
            if len(partes) == 3 and partes[1].isdigit():
                marcados.add(int(partes[1]))

    alunos = db.execute('SELECT id FROM alunos WHERE turma_id = ?', (turma_id,)).fetchall()

    for aluno in alunos:
        presente = 1 if aluno['id'] in marcados else 0
        db.execute('''
            INSERT INTO presencas (aluno_id, turma_id, disciplina_id, data, presente)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(aluno_id, turma_id, disciplina_id, data)
            DO UPDATE SET presente = excluded.presente
        ''', (aluno['id'], turma_id, disciplina_id, data_hoje, presente))

    db.commit()
    flash('Ata salva com sucesso!', 'success')
    return dashboard_do_usuario()

@professor_bp.route('/novaAvaliacao', methods=['GET', 'POST'])
def novaAvaliacao():
    if 'user_id' not in session or session.get('tipo') != 'professor':
        flash('Acesso permitido apenas para professores.', 'error')
        return redirect(url_for('auth.login'))

    db = get_db()

    turmas = db.execute('''
        SELECT DISTINCT t.id, t.nome
        FROM turmas t
        JOIN turma_disciplinas td ON td.turma_id = t.id
        WHERE td.professor_id = ?
        ORDER BY t.nome
    ''', (session['user_id'],)).fetchall()

    turma_id = request.args.get('turma_id', type=int)

    if turma_id and not pode_acessar_turma(turma_id):
        abort(403)

    alunos = []
    disciplinas = []

    if turma_id:
        alunos = db.execute(
            'SELECT id, nome FROM alunos WHERE turma_id = ?',
            (turma_id,)
        ).fetchall()
        # Só as disciplinas que ESTE professor leciona nesta turma
        disciplinas = db.execute(
            '''
            SELECT d.id, d.nome
            FROM disciplinas d
            JOIN turma_disciplinas td ON d.id = td.disciplina_id
            WHERE td.turma_id = ? AND td.professor_id = ?
            ORDER BY d.nome
            ''',
            (turma_id, session['user_id'])
        ).fetchall()

    if request.method == 'POST':
        disciplina_id = request.form.get('disciplina_id', type=int)
        data = request.form.get('data')

        # Impede lançar nota em disciplina que o professor não leciona nessa turma
        if disciplina_id not in [d['id'] for d in disciplinas]:
            abort(403)

        for aluno in alunos:
            aluno_id = aluno['id']
            nota = request.form.get(f'nota_{aluno_id}')
            presente = request.form.get(f'presente_{aluno_id}')
            observacoes = request.form.get(f'observacoes_{aluno_id}')

            presente_valor = 1 if presente == 'on' else 0
            nota_valor = float(nota) if nota else None

            db.execute(
                'INSERT INTO avaliacoes (aluno_id, disciplina_id, nota, presente, observacoes, data) VALUES (?, ?, ?, ?, ?, ?)',
                (aluno_id, disciplina_id, nota_valor, presente_valor, observacoes, data)
            )
        db.commit()
        flash('Avaliação registrada com sucesso!', 'success')
        return redirect(url_for('professor.dashboardProfessor'))

    hoje = date.today().strftime('%Y-%m-%d')

    return render_template(
        'novaAvaliacao.html', 
        turmas=turmas,
        turma_id=turma_id,
        alunos=alunos,
        disciplinas=disciplinas,
        hoje=hoje
    )

@professor_bp.route('/perfilAluno')
def perfilAluno():
    if 'user_id' not in session:
        flash('Faça login para acessar.', 'error')
        return redirect(url_for('auth.login'))

    db = get_db()

    user = db.execute(
        'SELECT nome, tipo FROM usuarios WHERE id = ?',
        (session['user_id'],)
    ).fetchone()

    alunos = []
    turmas = []

    if user['tipo'] == 'professor':
        alunos = db.execute('''
            SELECT 
                a.id,
                a.nome AS aluno_nome,
                a.email,
                t.nome AS turma_nome
            FROM alunos a
            JOIN turmas t ON a.turma_id = t.id
            WHERE t.id IN (
                SELECT turma_id FROM turma_disciplinas WHERE professor_id = ?
            )
            ORDER BY t.nome, a.nome
        ''', (session['user_id'],)).fetchall()

    elif user['tipo'] == 'coordenador':
        turmas = db.execute('''
            SELECT id, nome
            FROM turmas
            ORDER BY nome
        ''').fetchall()

    alunos_por_turma = {}
    for turma in turmas:
        alunos_item = db.execute('''
            SELECT id, nome AS aluno_nome, email
            FROM alunos
            WHERE turma_id = ?
            ORDER BY nome
        ''', (turma['id'],)).fetchall()
        alunos_por_turma[turma['id']] = alunos_item

    return render_template(
        'perfilAluno.html',
        nome=user['nome'],
        tipo=user['tipo'],
        alunos=alunos if user['tipo'] == 'professor' else None,
        turmas=turmas if user['tipo'] == 'coordenador' else None,
        alunos_por_turma=alunos_por_turma if user['tipo'] == 'coordenador' else None
    )

@professor_bp.route('/perfilIndividual/<int:aluno_id>')
def perfilIndividual(aluno_id):
    if 'user_id' not in session:
        flash('Faça login para acessar.', 'error')
        return redirect(url_for('auth.login'))

    db = get_db()

    user = db.execute(
        'SELECT nome, tipo FROM usuarios WHERE id = ?',
        (session['user_id'],)
    ).fetchone()

    aluno = db.execute('''
        SELECT 
            a.id,
            a.nome AS aluno_nome,
            a.email,
            a.turma_id,
            t.nome AS turma_nome
        FROM alunos a
        JOIN turmas t ON a.turma_id = t.id
        WHERE a.id = ?
    ''', (aluno_id,)).fetchone()

    if not aluno:
        flash('Aluno não encontrado.', 'error')
        return redirect(url_for('professor.perfilAluno'))

    if user['tipo'] == 'professor' and not professor_leciona_na_turma(aluno['turma_id']):
        flash('Acesso negado.', 'error')
        return redirect(url_for('professor.perfilAluno'))

    # Professor só enxerga as disciplinas que ele leciona na turma do aluno
    f_av, p_av = filtro_disciplinas(user['tipo'], aluno['turma_id'], 'a.disciplina_id')
    f_pr, p_pr = filtro_disciplinas(user['tipo'], aluno['turma_id'], 'disciplina_id')

    avaliacoes = db.execute(f'''
        SELECT 
            a.id,
            d.nome AS disciplina,
            a.nota,
            a.presente,
            a.data,
            a.observacoes
        FROM avaliacoes a
        JOIN disciplinas d ON a.disciplina_id = d.id
        WHERE a.aluno_id = ?{f_av}
        ORDER BY a.data ASC
    ''', (aluno_id,) + p_av).fetchall()

    medias_por_disciplina = db.execute(f'''
        SELECT 
            d.nome AS disciplina,
            AVG(a.nota) AS media
        FROM avaliacoes a
        JOIN disciplinas d ON a.disciplina_id = d.id
        WHERE a.aluno_id = ?{f_av}
        GROUP BY d.id
        ORDER BY media DESC
        LIMIT 3
    ''', (aluno_id,) + p_av).fetchall()

    presencas = db.execute(
        f'SELECT presente FROM presencas WHERE aluno_id = ?{f_pr}',
        (aluno_id,) + p_pr
    ).fetchall()

    total_aulas = len(presencas)
    total_presencas = sum(p['presente'] for p in presencas)
    frequencia = round((total_presencas / total_aulas) * 100) if total_aulas > 0 else 0

    notas = [av['nota'] for av in avaliacoes if av['nota'] is not None]
    if notas:
        media_geral = round(sum(notas) / len(notas), 2)
        total_avaliacoes = len(notas)
        
        # Lógica simples para calcular a tendência baseada nas notas cronológicas
        if len(notas) >= 2:
            # Compara a média das últimas avaliações com as primeiras
            metade = len(notas) // 2
            media_antiga = sum(notas[:metade]) / metade
            media_recente = sum(notas[metade:]) / (len(notas) - metade)
            
            if media_recente > media_antiga:
                tendencia = 'subindo'
            elif media_recente < media_antiga:
                tendencia = 'descendo'
            else:
                tendencia = 'estável'
        else:
            tendencia = 'estável'
    else:
        media_geral = 0
        total_avaliacoes = 0
        tendencia = 'estável'

    return render_template(
        'perfilIndividual.html',
        nome=user['nome'],
        tipo=user['tipo'],
        aluno=aluno,
        frequencia=frequencia,
        avaliacoes=avaliacoes,
        competencias=medias_por_disciplina,
        media_geral=media_geral,
        total_avaliacoes=total_avaliacoes,
        tendencia=tendencia  # <--- Variável nova enviada para o HTML
    )


@professor_bp.route('/relatorio/professor/<int:aluno_id>', methods=['GET', 'POST'])
def relatorio_professor(aluno_id):
    if 'user_id' not in session or session.get('tipo') != 'professor':
        return redirect(url_for('auth.login'))

    db = get_db()

    aluno = db.execute('''
        SELECT a.nome AS aluno_nome, t.nome AS turma_nome, t.id AS turma_id
        FROM alunos a
        JOIN turmas t ON a.turma_id = t.id
        WHERE a.id = ?
    ''', (aluno_id,)).fetchone()

    if not aluno:
        flash('Aluno não encontrado.', 'error')
        return redirect(url_for('professor.perfilAluno'))

    if not professor_leciona_na_turma(aluno['turma_id']):
        abort(403)

    f_av, p_av = filtro_disciplinas('professor', aluno['turma_id'], 'a.disciplina_id')
    f_pr, p_pr = filtro_disciplinas('professor', aluno['turma_id'], 'disciplina_id')

    freq = db.execute(f'''
        SELECT COUNT(*) total, COALESCE(SUM(presente), 0) presencas
        FROM presencas
        WHERE aluno_id = ?{f_pr}
    ''', (aluno_id,) + p_pr).fetchone()

    porcentagem = round((freq['presencas'] / freq['total']) * 100) if freq['total'] else 0

    avaliacoes = db.execute(f'''
        SELECT d.nome AS disciplina, a.nota
        FROM avaliacoes a
        JOIN disciplinas d ON d.id = a.disciplina_id
        WHERE a.aluno_id = ?{f_av}
    ''', (aluno_id,) + p_av).fetchall()

    if request.method == 'POST':
        comportamento = request.form['comportamento']
        observacoes = request.form['observacoes']
        hoje = date.today().strftime('%Y-%m-%d')

        html = render_template(
            'relatorioProfessorPDF.html',
            aluno=aluno,
            avaliacoes=avaliacoes,
            comportamento=comportamento,
            observacoes=observacoes,
            frequencia=f"{freq['presencas']}/{freq['total']} ({porcentagem}%)",
            data=date.today().strftime('%d/%m/%Y'),
            professor=session['nome']
        )

        db.execute('''
            INSERT INTO relatorios
            (tipo, referencia_id, titulo, data, html, criado_por)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            'professor',
            aluno_id,
            f"Relatório do Aluno {aluno['aluno_nome']}",
            hoje,
            html,
            session['user_id']
        ))

        db.commit()
        flash('Relatório do aluno gerado com sucesso!', 'success')
        return redirect(url_for('professor.relatorios'))

    return render_template(
        'relatorioProfessor.html',
        aluno=aluno,
        avaliacoes=avaliacoes,
        frequencia=f"{freq['presencas']}/{freq['total']} ({porcentagem}%)"
    )

@professor_bp.route('/relatorios')
def relatorios():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    db = get_db()

    relatorios = db.execute('''
        SELECT id, titulo, data
        FROM relatorios
        WHERE criado_por = ?
            AND tipo = ?
        ORDER BY data DESC
    ''', (
        session['user_id'],
        session['tipo']
    )).fetchall()

    return render_template(
        'relatorios.html',
        relatorios=relatorios,
        nome=session['nome'],
        tipo=session['tipo']
    )

@professor_bp.route('/relatorio/<int:id>')
def visualizarRelatorio(id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    db = get_db()
    relatorio = db.execute('''
        SELECT * FROM relatorios
        WHERE id = ? AND criado_por = ?
    ''', (id, session['user_id'])).fetchone()

    if not relatorio:
        flash('Acesso negado.', 'error')
        return redirect(url_for('professor.relatorios'))

    return relatorio['html']

@professor_bp.route('/relatorio/<int:id>/download')
def baixarRelatorio(id):
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    db = get_db()
    relatorio = db.execute(
        'SELECT * FROM relatorios WHERE id = ? AND criado_por = ?',
        (id, session['user_id'])
    ).fetchone()

    if not relatorio:
        flash('Relatório não encontrado.', 'error')
        return redirect(url_for('professor.relatorios'))

    css_pdf = """
    <style>
        body {
            font-family: Arial, Helvetica, sans-serif;
            color: #333;
            padding: 40px;
        }

        h1, h2, h3 {
            color: #6c5ce7;
            border-bottom: 2px solid #6c5ce7;
            padding-bottom: 5px;
        }

        p {
            line-height: 1.6;
            margin: 10px 0;
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }

        th {
            background: #6c5ce7;
            color: white;
            padding: 8px;
            text-align: left;
        }

        td {
            border: 1px solid #ddd;
            padding: 8px;
        }

        .info {
            margin-top: 20px;
        }
    </style>
    """

    html_pdf = f"""
    <html>
        <head>
            {css_pdf}
        </head>
        <body>
            {relatorio['html']}
        </body>
    </html>
    """

    pdf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html_pdf), dest=pdf)
    pdf.seek(0)

    return send_file(
        pdf,
        download_name=f"relatorio_{id}.pdf",
        as_attachment=True,
        mimetype="application/pdf"
    )

@professor_bp.route('/relatorio/<int:id>/delete', methods=['POST'])
def excluirRelatorio(id):
    if 'user_id' not in session:
        flash('Faça login para acessar.', 'error')
        return redirect(url_for('auth.login'))

    db = get_db()

    cursor = db.execute(
        'DELETE FROM relatorios WHERE id = ? AND criado_por = ?',
        (id, session['user_id'])
    )
    db.commit()

    if cursor.rowcount == 0:
        flash('Relatório não encontrado ou sem permissão para excluí-lo.', 'error')
    else:
        flash('Relatório excluído com sucesso!', 'success')

    return redirect(url_for('professor.relatorios'))

@professor_bp.route('/AjudaTutoriais')
def AjudaTutoriais():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

    return render_template(
        'AjudaTutoriais.html',
        nome=session.get('nome'),
        tipo=session.get('tipo')
    )