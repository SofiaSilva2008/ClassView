```markdown
# ClassView

Aplicação web para gestão escolar e acompanhamento do conselho de classe, desenvolvida com Python e Flask e integrada a um banco de dados relacional SQLite.

O ClassView permite gerenciar turmas, disciplinas, alunos e professores, registrar chamadas e notas, emitir relatórios pedagógicos em PDF e consultar indicadores institucionais. A aplicação possui sistema de autenticação por papéis (RBAC), painéis dinâmicos para professores e coordenadores e uma central de ajuda integrada.

## Demonstração

- **Dashboard do Coordenador:** Métricas gerais e alertas de turmas com média abaixo de 6.0.
- **Dashboard do Professor:** Acompanhamento de disciplinas e alertas de alunos com média abaixo de 6.0.
- **Lançamento de Chamada:** Registro rápido de frequência por disciplina.
- **Relatórios:** Emissão de pareceres descritivos e históricos acadêmicos.

## Funcionalidades

### Acadêmico e Pedagógico
- **Turmas e Disciplinas:** Organização e vínculo entre turmas, matérias e corpo docente.
- **Lançamento de Chamada (Ata):** Registro ágil de presença e falta por disciplina.
- **Avaliações e Notas:** Cadastro de notas e acompanhamento do desempenho individual.
- **Relatórios Pedagógicos:** Geração e exportação de documentos e históricos acadêmicos em PDF.

### Sistema de Alertas
- **Painel do Coordenador:** Monitoramento automático de turmas com média geral inferior a 6.0.
- **Painel do Professor:** Identificação imediata de alunos em situação de risco (média < 6.0) nas disciplinas lecionadas.

### Usuários e Autenticação
- **Controle de Acesso por Papéis (RBAC):** Distinção clara entre os perfis de **Professor** e **Coordenador**.
- **Autenticação Segura:** Controle de sessão por usuário logado.
- **Central de Suporte:** Página dedicada de **Ajuda & Tutoriais** adaptada ao perfil de acesso.

## Tecnologias Utilizadas

### Back-end
- Python 3
- Flask
- SQLite

### Front-end
- HTML5
- CSS3
- JavaScript
- FontAwesome
- Jinja2

### Ferramentas
- Git
- GitHub
- VS Code

## Instalação

### Pré-requisitos
- Python 3.8 ou superior instalado.

### Baixar o projeto e instalar as dependências

```bash
git clone [https://github.com/SEU-USUARIO/Conselho+.git](https://github.com/SEU-USUARIO/Conselho+.git)
cd Conselho+

```

Criar e ativar o ambiente virtual (`venv`):

* **Windows:**
```bash
python -m venv venv
venv\Scripts\activate

```


* **Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate

```



Instalar as dependências do projeto:

```bash
pip install -r requirements.txt

```

## Configuração

Crie um arquivo `.env` na raiz do projeto baseando-se no arquivo `.env.example`:

```env
SECRET_KEY=sua_chave_secreta_super_segura
ADMIN_EMAILS=seu_email@gmail.com

```

## Banco de dados

O projeto utiliza **SQLite**. As tabelas e conexões são gerenciadas de forma integrada ao iniciar a aplicação. O arquivo de banco de dados local gerado é ignorado automaticamente pelo Git através do arquivo `.gitignore`.

## Como iniciar

Depois de configurar o ambiente e o arquivo `.env`, execute:

```bash
python app.py

```

A aplicação ficará disponível para acesso no navegador em `http://127.0.0.1:5000`.
