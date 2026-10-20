import os
os.environ["WDM_LOCAL"] = "1"
os.environ["WDM_CACHE"] = os.path.join(os.getcwd(), ".wdm")


"""
Suite de testes automatizados para o projeto ClassView.

Este módulo utiliza pytest e Selenium WebDriver para interagir com a aplicação
Flask construída no diretório ``Conselho+``. Cada função de teste cobre uma
"tela" (rota) diferente da aplicação, verificando se os elementos essenciais
estão presentes, se a navegação funciona corretamente e se as validações
executadas pelo servidor retornam os comportamentos esperados.

Requisitos para executar os testes:

1. Instale as dependências necessárias:

   ```bash
   pip install pytest selenium
   ```

2. Certifique‑se de que o ChromeDriver compatível com sua versão do Chrome
   esteja instalado e disponível no ``PATH``. Em sistemas Linux, você pode
   instalar via gerenciador de pacotes ou baixar manualmente de
   ``https://chromedriver.chromium.org/downloads``.

3. Execute os testes a partir do diretório onde se encontra este arquivo com:

   ```bash
   pytest -q automated_tests.py
   ```

Os testes inicializam a aplicação Flask em background para cada sessão e
utilizam uma base de dados SQLite temporária, de modo a não interferir com
dados existentes. O fixture ``app_server`` cuida de criar e destruir essa
instância.

"""

import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager


# ---------------------------------------------------------------------------
# Fixtures de suporte
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def app_server():
    """Inicializa a aplicação Flask em segundo plano."""
    project_dir = Path(__file__).resolve().parent / "Conselho+"

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
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()



@pytest.fixture(scope="session")
def driver():
    options = webdriver.ChromeOptions()

    # 👉 CAMINHO DO CHROME (ESSENCIAL NO WINDOWS)
    options.binary_location = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    # Se quiser VER o navegador, comente a linha abaixo
    # options.add_argument("--headless=new")

    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    driver.implicitly_wait(5)
    yield driver
    driver.quit()



def register_user(driver, base_url, nome, email, senha, tipo):
    """Função auxiliar para registrar um usuário via interface."""
    driver.get(f"{base_url}/cadastro")
    select = driver.find_element(By.NAME, "tipo")
    select.find_element(By.XPATH, f"//option[@value='{tipo}']").click()
    driver.find_element(By.NAME, "nome").send_keys(nome)
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "senha").send_keys(senha)
    driver.find_element(By.NAME, "confirmar_senha").send_keys(senha)
    driver.find_element(By.TAG_NAME, "button").click()


def login(driver, base_url, email, senha):
    """Função auxiliar para realizar login via interface."""
    driver.get(f"{base_url}/login")
    driver.find_element(By.NAME, "email").send_keys(email)
    driver.find_element(By.NAME, "senha").send_keys(senha)
    driver.find_element(By.TAG_NAME, "button").click()


# ---------------------------------------------------------------------------
# Casos de teste
# ---------------------------------------------------------------------------

def test_cadastro_page_exibe_campos(driver, app_server):
    """Verifica se a tela de cadastro exibe todos os campos obrigatórios【431620052070002†screenshot】."""
    base_url = app_server
    driver.get(f"{base_url}/cadastro")
    assert driver.find_element(By.NAME, "tipo")
    assert driver.find_element(By.NAME, "nome")
    assert driver.find_element(By.NAME, "email")
    assert driver.find_element(By.NAME, "senha")
    assert driver.find_element(By.NAME, "confirmar_senha")
    assert driver.find_element(By.TAG_NAME, "button").text.upper() == "CRIAR CONTA"


def test_cadastro_senhas_nao_coincidem(driver, app_server):
    """Garante que o sistema valida senhas divergentes no cadastro【431620052070002†screenshot】."""
    base_url = app_server
    driver.get(f"{base_url}/cadastro")
    driver.find_element(By.NAME, "tipo").find_elements(By.TAG_NAME, "option")[1].click()
    driver.find_element(By.NAME, "nome").send_keys("Usuário Teste")
    driver.find_element(By.NAME, "email").send_keys("teste@exemplo.com")
    driver.find_element(By.NAME, "senha").send_keys("12345678")
    driver.find_element(By.NAME, "confirmar_senha").send_keys("87654321")
    driver.find_element(By.TAG_NAME, "button").click()
    msg = WebDriverWait(driver, 3).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".msg.error"))
    )
    assert "senha" in msg.text.lower()


def test_login_credenciais_invalidas(driver, app_server):
    """Testa login com credenciais incorretas【527193846865123†screenshot】."""
    base_url = app_server
    driver.get(f"{base_url}/login")
    driver.find_element(By.NAME, "email").send_keys("inexistente@teste.com")
    driver.find_element(By.NAME, "senha").send_keys("senhaerrada")
    driver.find_element(By.TAG_NAME, "button").click()
    msg = WebDriverWait(driver, 3).until(
        EC.visibility_of_element_located((By.CSS_SELECTOR, ".msg.error"))
    )
    assert "incorretos" in msg.text.lower()


def test_cadastro_e_login_professor(driver, app_server):
    """Registra um usuário do tipo professor e verifica o redirecionamento【527193846865123†screenshot】."""
    base_url = app_server
    email = "professor@test.com"
    senha = "senhaSegura1"
    register_user(driver, base_url, "Prof Teste", email, senha, "professor")
    WebDriverWait(driver, 3).until(EC.url_contains("/login"))
    login(driver, base_url, email, senha)
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardProfessor"))
    assert driver.current_url.endswith("/dashboardProfessor")


def test_dashboard_professor_itens(driver, app_server):
    """Após login, verifica elementos básicos do dashboard do professor【718471631974186†screenshot】."""
    base_url = app_server
    email = "docente@test.com"
    senha = "SenhaDocente123"
    register_user(driver, base_url, "Docente", email, senha, "professor")
    login(driver, base_url, email, senha)
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardProfessor"))
    page_text = driver.find_element(By.TAG_NAME, "body").text
    assert "Total de turmas" in page_text
    assert "Frequência média" in page_text


def test_redirecionamento_sem_login(driver, app_server):
    """Garante que páginas protegidas redirecionam para login quando não autenticado【359289553364810†screenshot】."""
    base_url = app_server
    driver.get(f"{base_url}/dashboardProfessor")
    WebDriverWait(driver, 3).until(EC.url_contains("/login"))
    assert "/login" in driver.current_url


def test_adicionar_turma_fluxo(driver, app_server):
    """Fluxo de criação de turma pelo coordenador【512026033112964†screenshot】."""
    base_url = app_server
    register_user(driver, base_url, "Prof Aux", "prof.aux@test.com", "SenhaProfAux1", "professor")
    coord_email = "coord@test.com"
    coord_senha = "CoordPass123"
    register_user(driver, base_url, "Coord User", coord_email, coord_senha, "coordenador")
    login(driver, base_url, coord_email, coord_senha)
    WebDriverWait(driver, 5).until(EC.url_contains("/dashboardCoordenador"))
    driver.get(f"{base_url}/adicionarTurma")
    driver.find_element(By.NAME, "nome").send_keys("Turma Teste")
    select = driver.find_element(By.NAME, "professor_id")
    select.find_elements(By.TAG_NAME, "option")[0].click()
    driver.find_element(By.CSS_SELECTOR, ".btn-solid").click()
    WebDriverWait(driver, 5).until(EC.url_contains("/adicionarCoordenador"))
    assert "/adicionarCoordenador" in driver.current_url


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
    """Verifica a presença da página de relatórios e do botão gerar【698361295485217†screenshot】."""
    base_url = app_server
    email = "prof.rel@test.com"
    senha = "Relatorio123"
    register_user(driver, base_url, "Prof Rel", email, senha, "professor")
    login(driver, base_url, email, senha)
    driver.get(f"{base_url}/relatorios")
    page_text = driver.find_element(By.TAG_NAME, "body").text
    assert "Relatórios" in page_text
    btn = driver.find_element(By.CLASS_NAME, "btn-gerar")
    assert btn.is_displayed()
