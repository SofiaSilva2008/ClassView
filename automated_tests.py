import uuid

def email_unico(prefix="user"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Evita problemas do webdriver_manager no Windows
os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_CACHE"] = os.path.join(os.getcwd(), ".wdm")

# ---------------------------------------------------------------------------
# Fixture: servidor Flask
# ---------------------------------------------------------------------------


def email_unico(prefix="user"):
    return f"{prefix}_{uuid.uuid4().hex[:8]}@test.com"


@pytest.fixture(autouse=True)
def limpar_banco():
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    cur.execute("DELETE FROM presencas")
    cur.execute("DELETE FROM alunos")
    cur.execute("DELETE FROM turmas")
    cur.execute("DELETE FROM usuarios")
    conn.commit()
    conn.close()




@pytest.fixture(scope="session")
def app_server():
    """Inicializa a aplicação Flask em segundo plano."""
    project_dir = Path(__file__).resolve().parent

    env = os.environ.copy()
    env["FLASK_APP"] = "app.py"

    proc = subprocess.Popen(
        [sys.executable, "app.py"],
        cwd=project_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    base_url = "http://localhost:5000"

    for _ in range(20):
        try:
            import socket
            sock = socket.create_connection(("localhost", 5000), timeout=1)
            sock.close()
            break
        except Exception:
            time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("Não foi possível iniciar o servidor Flask.")

    yield base_url

    proc.terminate()

# ---------------------------------------------------------------------------
# Fixture: Selenium WebDriver
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def driver():
    options = webdriver.ChromeOptions()
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    driver.implicitly_wait(5)

    yield driver

    driver.quit()


def logout(driver, base_url):
    driver.get(f"{base_url}/logout")


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------

def register_user(driver, base_url, nome, email, senha, tipo):
    driver.get(f"{base_url}/cadastro")
    select = driver.find_element(By.NAME, "tipo")
    select.find_element(By.XPATH, f"//option[@value='{tipo}']").click()
    driver.find_element(By.NAME, "nome").send_keys(nome)
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "senha").send_keys(senha)
    driver.find_element(By.NAME, "confirmar_senha").send_keys(senha)
    driver.find_element(By.TAG_NAME, "button").click()


def login(driver, base_url, email, senha):
    driver.get(f"{base_url}/login")
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "senha").send_keys(senha)
    driver.find_element(By.TAG_NAME, "button").click()

# ---------------------------------------------------------------------------
# Caso de teste
# ---------------------------------------------------------------------------


def test_redirecionamento_sem_login(driver, app_server):
    base_url = app_server
    driver.get(f"{base_url}/logout")
    driver.get(f"{base_url}/dashboardProfessor")
    WebDriverWait(driver, 5).until(EC.url_contains("/login"))
    assert "/login" in driver.current_url


def test_dashboard_professor_itens(driver, app_server):
    base_url = app_server
    email = email_unico("docente")
    senha = "SenhaDocente123"

    register_user(driver, base_url, "Docente", email, senha, "professor")
    login(driver, base_url, email, senha)

    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardProfessor"))
    body = driver.find_element(By.TAG_NAME, "body").text

    assert "Total de turmas" in body
    assert "Frequência" in body



def test_adicionar_turma_coordenador(driver, app_server):
    base_url = app_server

    prof_email = email_unico("prof")
    coord_email = email_unico("coord")

    register_user(driver, base_url, "Professor", prof_email, "Senha1234", "professor")
    register_user(driver, base_url, "Coordenador", coord_email, "Senha1234", "coordenador")

    login(driver, base_url, coord_email, "Senha1234")
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardCoordenador"))

    driver.get(f"{base_url}/adicionarTurma")
    driver.find_element(By.NAME, "nome").send_keys("Turma Teste")
    driver.find_element(By.NAME, "professor_id").find_elements(By.TAG_NAME, "option")[0].click()
    driver.find_element(By.CSS_SELECTOR, ".btn-solid").click()

    WebDriverWait(driver, 5).until(EC.url_contains("/adicionarCoordenador"))
    assert "/adicionarCoordenador" in driver.current_url



def test_cadastro_page_exibe_campos(driver, app_server):
    base_url = app_server
    driver.get(f"{base_url}/cadastro")

    for campo in ["tipo", "nome", "email", "senha", "confirmar_senha"]:
        assert driver.find_element(By.NAME, campo)

    assert "CRIAR CONTA" in driver.find_element(By.TAG_NAME, "button").text.upper()



def test_cadastro_senhas_nao_coincidem(driver, app_server):
    base_url = app_server
    driver.get(f"{base_url}/cadastro")

    driver.find_element(By.NAME, "tipo").find_elements(By.TAG_NAME, "option")[1].click()
    driver.find_element(By.NAME, "nome").send_keys("Teste")
    driver.find_element(By.NAME, "email").send_keys(email_unico("senha"))
    driver.find_element(By.NAME, "senha").send_keys("12345678")
    driver.find_element(By.NAME, "confirmar_senha").send_keys("87654321")
    driver.find_element(By.TAG_NAME, "button").click()

    msg = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".msg.error"))
    )

    assert "senha" in msg.text.lower()


    
def test_login_credenciais_invalidas(driver, app_server):
    base_url = app_server
    driver.get(f"{base_url}/login")

    driver.find_element(By.NAME, "email").send_keys(email_unico("fake"))
    driver.find_element(By.NAME, "senha").send_keys("errada")
    driver.find_element(By.TAG_NAME, "button").click()

    msg = WebDriverWait(driver, 5).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".msg.error"))
    )

    assert "incorretos" in msg.text.lower()



def test_cadastro_e_login_professor(driver, app_server):
    """Registra um usuário do tipo professor e verifica o redirecionamento【527193846865123†screenshot】."""
    base_url = app_server
    email = "professor@test9.com"
    senha = "senhaSegura1"
    register_user(driver, base_url, "Prof Teste", email, senha, "professor")
    WebDriverWait(driver, 3).until(EC.url_contains("/login"))
    login(driver, base_url, email, senha)
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardProfessor"))
    assert driver.current_url.endswith("/dashboardProfessor")





def test_adicionar_aluno_fluxo(driver, app_server):
    """Cria uma turma e adiciona um aluno via interface【454296094849533†screenshot】."""
    base_url = app_server
    register_user(driver, base_url, "Prof Base", "prof.base@test.com", "SenhaProfBase1", "professor")
    coord_email = "coord2@test.com"
    coord_senha = "CoordPass234"
    register_user(driver, base_url, "Coord Dois", coord_email, coord_senha, "coordenador")
    login(driver, base_url, coord_email, coord_senha)
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardCoordenador"))
    driver.get(f"{base_url}/adicionarTurma")
    driver.find_element(By.NAME, "nome").send_keys("Turma Base")
    driver.find_element(By.NAME, "professor_id").find_elements(By.TAG_NAME, "option")[0].click()
    driver.find_element(By.CSS_SELECTOR, ".btn-solid").click()
    WebDriverWait(driver, 5).until(EC.url_contains("/adicionarCoordenador"))
    driver.get(f"{base_url}/adicionarAluno")
    driver.find_element(By.NAME, "nome").send_keys("Aluno Teste")
    driver.find_element(By.NAME, "email").send_keys("aluno@test.com")
    driver.find_element(By.NAME, "turma_id").find_elements(By.TAG_NAME, "option")[0].click()
    driver.find_element(By.CSS_SELECTOR, ".btn-solid").click()
    WebDriverWait(driver, 5).until(EC.url_contains("/adicionarCoordenador"))
    assert "/adicionarCoordenador" in driver.current_url



def test_ata_presencas(driver, app_server):
    """Preenche e salva presenças na ata de uma turma【569968301895322†screenshot】."""
    base_url = app_server
    email = "prof.presenca@test.com"
    senha = "ProfPres123"
    register_user(driver, base_url, "Prof Presença", email, senha, "professor")
    login(driver, base_url, email, senha)
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardProfessor"))
    # Insere turma e aluno via banco
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    prof_id = cur.execute("SELECT id FROM usuarios WHERE email=?", (email,)).fetchone()[0]
    cur.execute("INSERT INTO turmas (nome, professor_id) VALUES (?, ?)", ("Turma Presença", prof_id))
    turma_id = cur.lastrowid
    cur.execute("INSERT INTO alunos (nome, email, turma_id) VALUES (?, ?, ?)", ("Aluno P", "aluno.p@test.com", turma_id))
    aluno_id = cur.lastrowid
    data_hoje = time.strftime("%Y-%m-%d")
    cur.execute(
        "INSERT INTO presencas (aluno_id, turma_id, data, presente) VALUES (?, ?, ?, 0)",
        (aluno_id, turma_id, data_hoje),
    )
    conn.commit()
    conn.close()
    driver.get(f"{base_url}/ata/turma/{turma_id}")
    checkbox = driver.find_element(By.NAME, f"presenca-{aluno_id}-{data_hoje}")
    if not checkbox.is_selected():
        checkbox.click()
    driver.find_element(By.CSS_SELECTOR, "form button").click()
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardProfessor"))
    assert "/dashboardProfessor" in driver.current_url


def test_perfil_aluno_e_perfil_individual(driver, app_server):
    """Exibe lista de alunos e navega até o perfil individual【847710128365410†screenshot】【166786968655523†screenshot】."""
    base_url = app_server
    email = "prof.perfil@test.com"
    senha = "PerfilTest123"
    register_user(driver, base_url, "Prof Perfil", email, senha, "professor")
    login(driver, base_url, email, senha)
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardProfessor"))
    conn = sqlite3.connect("database.db")
    cur = conn.cursor()
    prof_id = cur.execute("SELECT id FROM usuarios WHERE email=?", (email,)).fetchone()[0]
    cur.execute("INSERT INTO turmas (nome, professor_id) VALUES (?, ?)", ("Turma Perfil", prof_id))
    turma_id = cur.lastrowid
    cur.execute(
        "INSERT INTO alunos (nome, email, turma_id) VALUES (?, ?, ?)",
        ("Aluno Perfil", "aluno.perfil@test.com", turma_id),
    )
    aluno_id = cur.lastrowid
    conn.commit()
    conn.close()
    driver.get(f"{base_url}/perfilAluno")
    cards = driver.find_elements(By.CLASS_NAME, "student-card")
    assert any("Aluno Perfil" in card.text for card in cards)
    driver.find_element(By.LINK_TEXT, "Ver Perfil").click()
    WebDriverWait(driver, 5).until(EC.url_contains("/perfilIndividual"))
    assert f"/perfilIndividual/{aluno_id}" in driver.current_url
    page_text = driver.find_element(By.TAG_NAME, "body").text
    assert "Média Geral" in page_text
    assert "Frequência" in page_text


def test_relatorios_pagina(driver, app_server):
    base_url = app_server
    email = email_unico("rel")
    senha = "Relatorio123"

    register_user(driver, base_url, "Prof Rel", email, senha, "professor")
    login(driver, base_url, email, senha)

    driver.get(f"{base_url}/relatorios")

    body = driver.find_element(By.TAG_NAME, "body").text
    assert "Relatórios" in body
    assert driver.find_element(By.CLASS_NAME, "btn-gerar").is_displayed()


#Novos
def test_professor_nao_acessa_dashboard_coordenador(driver, app_server):
    base_url = app_server
    email = email_unico("prof")
    senha = "SenhaProf123"

    register_user(driver, base_url, "Prof Bloqueado", email, senha, "professor")
    login(driver, base_url, email, senha)

    driver.get(f"{base_url}/dashboardCoordenador")
    WebDriverWait(driver, 5).until(EC.url_contains("/login"))

    assert "/login" in driver.current_url

def test_logout_bloqueia_acesso(driver, app_server):
    base_url = app_server
    email = email_unico("logout")
    senha = "Logout123"

    register_user(driver, base_url, "User Logout", email, senha, "professor")
    login(driver, base_url, email, senha)

    driver.get(f"{base_url}/logout")
    driver.get(f"{base_url}/dashboardProfessor")

    WebDriverWait(driver, 5).until(EC.url_contains("/login"))
    assert "/login" in driver.current_url

def test_perfil_professor_exibe_dados(driver, app_server):
    base_url = app_server
    email = email_unico("perfilprof")
    senha = "PerfilProf123"

    register_user(driver, base_url, "Professor Perfil", email, senha, "professor")
    login(driver, base_url, email, senha)

    driver.get(f"{base_url}/perfilProfessor")

    body = driver.find_element(By.TAG_NAME, "body").text
    assert "Professor Perfil" in body
    assert "Total de alunos" in body.lower()

def test_ajuda_exige_login(driver, app_server):
    base_url = app_server

    driver.get(f"{base_url}/AjudaTutoriais")
    WebDriverWait(driver, 5).until(EC.url_contains("/login"))

    assert "/login" in driver.current_url

def test_perfil_coordenador(driver, app_server):
    base_url = app_server
    email = email_unico("coordperfil")
    senha = "CoordPerfil123"

    register_user(driver, base_url, "Coord Perfil", email, senha, "coordenador")
    login(driver, base_url, email, senha)

    driver.get(f"{base_url}/perfilCoordenador")

    body = driver.find_element(By.TAG_NAME, "body").text
    assert "Total de professores" in body
    assert "Total de turmas" in body

def test_relatorios_sem_registros(driver, app_server):
    base_url = app_server
    email = email_unico("relatorio")
    senha = "Relatorio123"

    register_user(driver, base_url, "User Relatorio", email, senha, "professor")
    login(driver, base_url, email, senha)

    driver.get(f"{base_url}/relatorios")

    body = driver.find_element(By.TAG_NAME, "body").text.lower()
    assert "relatório" in body

def test_adicionar_disciplina(driver, app_server):
    base_url = app_server

    prof_email = email_unico("profdisc")
    coord_email = email_unico("coorddisc")

    register_user(driver, base_url, "Professor D", prof_email, "Senha123", "professor")
    register_user(driver, base_url, "Coord D", coord_email, "Senha123", "coordenador")

    login(driver, base_url, coord_email, "Senha123")

    driver.get(f"{base_url}/adicionarDisciplina")
    driver.find_element(By.NAME, "nome").send_keys("Matemática")
    driver.find_element(By.NAME, "professor_id").find_elements(By.TAG_NAME, "option")[0].click()
    driver.find_elements(By.NAME, "turmas")[0].click()
    driver.find_element(By.CSS_SELECTOR, ".btn-solid").click()

    WebDriverWait(driver, 5).until(EC.url_contains("/adicionarCoordenador"))
    assert "/adicionarCoordenador" in driver.current_url

def test_geracao_pdf_relatorio(client, login_professor):
    response = client.get('/relatorio/1/download')

    assert response.status_code == 200
    assert response.headers['Content-Type'] == 'application/pdf'
    assert len(response.data) > 0

def calcular_media(valores):
    return sum(valores) / len(valores)

def test_calculo_media():
    notas = [7.0, 8.0, 9.0]
    media = calcular_media(notas)

    assert media == 8.0

import time

def test_tempo_resposta_dashboard(client, login_professor):
    inicio = time.time()
    response = client.get('/dashboardProfessor')
    fim = time.time()

    assert response.status_code == 200
    assert (fim - inicio) < 2  # menos de 2 segundos

def test_sessoes_independentes(app):
    client1 = app.test_client()
    client2 = app.test_client()

    client1.post('/login', data={
        'email': 'prof1@email.com',
        'senha': '123'
    })

    client2.post('/login', data={
        'email': 'coord@email.com',
        'senha': '123'
    })

    resp1 = client1.get('/dashboardProfessor')
    resp2 = client2.get('/dashboardCoordenador')

    assert resp1.status_code == 200
    assert resp2.status_code == 200
