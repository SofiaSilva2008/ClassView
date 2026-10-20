from flask import Blueprint, render_template, request, redirect, url_for, flash, session, g
from werkzeug.security import check_password_hash, generate_password_hash
import sqlite3
import os

auth_bp = Blueprint('auth', __name__)

ADMIN_EMAILS = {e.strip().lower() for e in os.environ.get('ADMIN_EMAILS', '').split(',') if e.strip()}
DATABASE = 'database.db'

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON;')
    return g.db

@auth_bp.route('/')
def home():
    return render_template('index.html')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']

        db = get_db()
        user = db.execute(
            'SELECT * FROM usuarios WHERE email = ?',
            (email,)
        ).fetchone()

        if user and check_password_hash(user['senha'], senha):
            session['user_id'] = user['id']
            session['tipo'] = user['tipo']
            session['nome'] = user['nome']

            if user['tipo'] == 'professor':
                return redirect(url_for('professor.dashboardProfessor'))
            elif user['tipo'] == 'coordenador':
                return redirect(url_for('coordenador.dashboard_coordenador'))
            else:
                flash('Tipo de usuário inválido.', 'error')
        else:
            flash('E-mail ou senha incorretos.', 'error')

    return render_template('login.html')

@auth_bp.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        senha = request.form['senha']
        confirmar = request.form['confirmar_senha']
        
        email_normalizado = email.strip().lower()
        tipo = 'coordenador' if email_normalizado in ADMIN_EMAILS else 'professor'

        if senha != confirmar:
            flash('As senhas não coincidem.', 'error')
            return redirect(url_for('auth.cadastro'))

        senha_hash = generate_password_hash(senha)
        db = get_db()
        try:
            db.execute(
                'INSERT INTO usuarios (nome, email, senha, tipo) VALUES (?, ?, ?, ?)',
                (nome, email_normalizado, senha_hash, tipo)
            )
            db.commit()
            flash('Cadastro realizado com sucesso!', 'success')
            return redirect(url_for('auth.login'))
        except sqlite3.IntegrityError:
            flash('E-mail já cadastrado.', 'error')

    return render_template('cadastro.html')

@auth_bp.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso.', 'success')
    return redirect(url_for('auth.login'))
