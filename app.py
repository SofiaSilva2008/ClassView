from flask import Flask, g
import sqlite3
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do ficheiro .env
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("Defina a variável de ambiente SECRET_KEY")

DATABASE = os.environ.get('DATABASE', 'database.db')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON;')
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def create_tables():
    db = get_db()

    # USUÁRIOS
    db.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            tipo TEXT NOT NULL
        )
    ''')

        # TURMAS (sem professor responsável)
    db.execute('''
        CREATE TABLE IF NOT EXISTS turmas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL
        )
    ''')

    # DISCIPLINAS (catálogo, sem professor)
    db.execute('''
        CREATE TABLE IF NOT EXISTS disciplinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL UNIQUE
        )
    ''')

    # TURMA_DISCIPLINAS: turma + disciplina + professor que leciona
    db.execute('''
        CREATE TABLE IF NOT EXISTS turma_disciplinas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turma_id INTEGER NOT NULL,
            disciplina_id INTEGER NOT NULL,
            professor_id INTEGER NOT NULL,
            UNIQUE(turma_id, disciplina_id),
            FOREIGN KEY (turma_id) REFERENCES turmas(id) ON DELETE CASCADE,
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id),
            FOREIGN KEY (professor_id) REFERENCES usuarios(id)
        )
    ''')

    # ALUNOS
    db.execute('''
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE,
            turma_id INTEGER NOT NULL,
            FOREIGN KEY (turma_id) REFERENCES turmas(id)
        )
    ''')

        # PRESENÇAS (por disciplina)
    db.execute('''
        CREATE TABLE IF NOT EXISTS presencas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            turma_id INTEGER NOT NULL,
            disciplina_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            presente INTEGER NOT NULL DEFAULT 0,
            UNIQUE(aluno_id, turma_id, disciplina_id, data),
            FOREIGN KEY (aluno_id) REFERENCES alunos(id),
            FOREIGN KEY (turma_id) REFERENCES turmas(id),
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
        )
    ''')

    # OBSERVAÇÕES DAS AULAS (por disciplina)
    db.execute('''
        CREATE TABLE IF NOT EXISTS observacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turma_id INTEGER NOT NULL,
            disciplina_id INTEGER NOT NULL,
            data TEXT NOT NULL,
            texto TEXT NOT NULL,
            FOREIGN KEY (turma_id) REFERENCES turmas(id),
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
        )
    ''')

    # AVALIAÇÕES
    db.execute('''
        CREATE TABLE IF NOT EXISTS avaliacoes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            disciplina_id INTEGER NOT NULL,
            nota REAL,
            presente INTEGER DEFAULT 1,
            observacoes TEXT,
            data TEXT NOT NULL,
            FOREIGN KEY (aluno_id) REFERENCES alunos(id),
            FOREIGN KEY (disciplina_id) REFERENCES disciplinas(id)
        )
    ''')

    # RELATÓRIOS
    db.execute('''
        CREATE TABLE IF NOT EXISTS relatorios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL CHECK(tipo IN ('professor', 'coordenador')),
            referencia_id INTEGER NOT NULL,
            titulo TEXT NOT NULL,
            data TEXT NOT NULL,
            html TEXT NOT NULL,
            criado_por INTEGER NOT NULL,
            FOREIGN KEY (criado_por) REFERENCES usuarios(id)
        )
    ''')

    db.commit()

with app.app_context():
    create_tables()

# ===========================================================================
# REGISTO DOS BLUEPRINTS (Módulos de Rotas)
# ===========================================================================
from routes.auth import auth_bp
from routes.professor import professor_bp
from routes.coordenador import coordenador_bp

app.register_blueprint(auth_bp)
app.register_blueprint(professor_bp)
app.register_blueprint(coordenador_bp)

if __name__ == '__main__':
    app.run(debug=False)
