import streamlit as st
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import uuid
import json
import requests
import hashlib
from typing import Dict, List, Optional
import time

# Configuração da página
st.set_page_config(
    page_title="Sistema de Pesquisas",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        color: #1f77b4;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #1f77b4;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 10px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# Configuração da OpenAI
OPENAI_API_KEY = "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"

class DatabaseManager:
    def __init__(self, db_path="survey_system.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Inicializa o banco de dados com as tabelas necessárias"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabela Companies
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela Surveys
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS surveys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                company_id INTEGER NOT NULL,
                public_id TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (company_id) REFERENCES companies (id)
            )
        ''')
        
        # Tabela Questions
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                question_type TEXT DEFAULT 'text',
                options TEXT,
                importance INTEGER DEFAULT 1,
                order_num INTEGER DEFAULT 0,
                FOREIGN KEY (survey_id) REFERENCES surveys (id)
            )
        ''')
        
        # Tabela Responses
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id INTEGER NOT NULL,
                respondent_id TEXT NOT NULL,
                responses_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ai_analysis TEXT,
                FOREIGN KEY (survey_id) REFERENCES surveys (id)
            )
        ''')
        
        # Tabela AI Analysis
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                survey_id INTEGER NOT NULL,
                analysis_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (survey_id) REFERENCES surveys (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def execute_query(self, query: str, params: tuple = (), fetch: bool = False):
        """Executa uma query no banco de dados"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute(query, params)
            if fetch:
                result = cursor.fetchall()
                conn.close()
                return result
            else:
                conn.commit()
                result = cursor.lastrowid
                conn.close()
                return result
        except Exception as e:
            conn.close()
            raise e

def hash_password(password: str) -> str:
    """Gera hash da senha"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, password_hash: str) -> bool:
    """Verifica se a senha está correta"""
    return hash_password(password) == password_hash

def analyze_with_openai(survey_data: Dict, responses_data: List) -> str:
    """Analisa respostas usando OpenAI API"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }

        prompt = f"""
        Analise as seguintes respostas de pesquisa e forneça insights detalhados:

        Pesquisa: {survey_data['title']}
        Descrição: {survey_data['description']}

        Respostas coletadas: {len(responses_data)}

        Dados das respostas:
        {json.dumps(responses_data, indent=2, ensure_ascii=False)}

        Por favor, forneça:
        1. Resumo geral dos resultados
        2. Principais tendências identificadas
        3. Pontos de atenção ou problemas
        4. Recomendações baseadas nos dados
        5. Sentimento geral dos respondentes

        Responda em formato de texto limpo e organizado para análise.
        """

        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Erro na análise: {response.status_code}"

    except Exception as e:
        return f"Erro ao conectar com OpenAI: {str(e)}"

def main():
    # Inicializa o gerenciador de banco de dados
    if 'db_manager' not in st.session_state:
        st.session_state.db_manager = DatabaseManager()
    
    # Inicializa estado da sessão
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'company_id' not in st.session_state:
        st.session_state.company_id = None
    if 'company_name' not in st.session_state:
        st.session_state.company_name = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'home'

    db = st.session_state.db_manager

    # Sidebar para navegação
    with st.sidebar:
        st.title("📊 Sistema de Pesquisas")
        
        if not st.session_state.authenticated:
            st.subheader("Acesso")
            if st.button("🏠 Início"):
                st.session_state.current_page = 'home'
            if st.button("📝 Cadastro"):
                st.session_state.current_page = 'register'
            if st.button("🔑 Login"):
                st.session_state.current_page = 'login'
            if st.button("📋 Responder Pesquisa"):
                st.session_state.current_page = 'public_survey'
        else:
            st.success(f"Logado como: {st.session_state.company_name}")
            if st.button("📊 Dashboard"):
                st.session_state.current_page = 'dashboard'
            if st.button("➕ Nova Pesquisa"):
                st.session_state.current_page = 'new_survey'
            if st.button("📋 Minhas Pesquisas"):
                st.session_state.current_page = 'my_surveys'
            if st.button("🚪 Logout"):
                st.session_state.authenticated = False
                st.session_state.company_id = None
                st.session_state.company_name = None
                st.session_state.current_page = 'home'
                st.rerun()

    # Conteúdo principal baseado na página atual
    if st.session_state.current_page == 'home':
        show_home_page()
    elif st.session_state.current_page == 'register':
        show_register_page(db)
    elif st.session_state.current_page == 'login':
        show_login_page(db)
    elif st.session_state.current_page == 'dashboard':
        if st.session_state.authenticated:
            show_dashboard(db)
        else:
            st.error("Você precisa fazer login primeiro!")
            st.session_state.current_page = 'login'
    elif st.session_state.current_page == 'new_survey':
        if st.session_state.authenticated:
            show_new_survey_page(db)
        else:
            st.error("Você precisa fazer login primeiro!")
            st.session_state.current_page = 'login'
    elif st.session_state.current_page == 'my_surveys':
        if st.session_state.authenticated:
            show_my_surveys_page(db)
        else:
            st.error("Você precisa fazer login primeiro!")
            st.session_state.current_page = 'login'
    elif st.session_state.current_page == 'public_survey':
        show_public_survey_page(db)
    elif st.session_state.current_page == 'edit_survey':
        if st.session_state.authenticated:
            show_edit_survey_page(db)
        else:
            st.error("Você precisa fazer login primeiro!")
            st.session_state.current_page = 'login'
    elif st.session_state.current_page == 'analytics':
        if st.session_state.authenticated:
            show_analytics_page(db)
        else:
            st.error("Você precisa fazer login primeiro!")
            st.session_state.current_page = 'login'

def show_home_page():
    st.markdown('<h1 class="main-header">📊 Sistema de Pesquisas com IA</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("""
        <div class="metric-card">
            <h3>🏢 Para Empresas</h3>
            <p>Crie pesquisas personalizadas e obtenha insights valiosos sobre seus clientes e mercado.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown("""
        <div class="metric-card">
            <h3>🤖 Análise com IA</h3>
            <p>Nossa IA analisa automaticamente as respostas e fornece relatórios detalhados.</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown("""
        <div class="metric-card">
            <h3>📈 Visualizações</h3>
            <p>Gráficos interativos e dashboards para melhor compreensão dos dados.</p>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### Como funciona?")
    st.markdown("""
    1. **Cadastre-se** ou faça **login** em sua conta
    2. **Crie suas pesquisas** com diferentes tipos de perguntas
    3. **Compartilhe** o link da pesquisa com seu público
    4. **Receba análises automáticas** geradas por IA
    5. **Visualize os resultados** em dashboards interativos
    """)

def show_register_page(db):
    st.markdown('<h1 class="main-header">📝 Cadastro de Empresa</h1>', unsafe_allow_html=True)
    
    with st.form("register_form"):
        name = st.text_input("Nome da Empresa")
        email = st.text_input("Email")
        password = st.text_input("Senha", type="password")
        confirm_password = st.text_input("Confirmar Senha", type="password")
        
        submitted = st.form_submit_button("Cadastrar")
        
        if submitted:
            if not name or not email or not password:
                st.error("Todos os campos são obrigatórios!")
            elif password != confirm_password:
                st.error("As senhas não coincidem!")
            else:
                # Verifica se email já existe
                existing = db.execute_query(
                    "SELECT id FROM companies WHERE email = ?", 
                    (email,), 
                    fetch=True
                )
                
                if existing:
                    st.error("Email já cadastrado!")
                else:
                    # Cadastra nova empresa
                    password_hash = hash_password(password)
                    db.execute_query(
                        "INSERT INTO companies (name, email, password_hash) VALUES (?, ?, ?)",
                        (name, email, password_hash)
                    )
                    st.success("Cadastro realizado com sucesso!")
                    time.sleep(2)
                    st.session_state.current_page = 'login'
                    st.rerun()

def show_login_page(db):
    st.markdown('<h1 class="main-header">🔑 Login</h1>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Senha", type="password")
        
        submitted = st.form_submit_button("Entrar")
        
        if submitted:
            if not email or not password:
                st.error("Email e senha são obrigatórios!")
            else:
                # Verifica credenciais
                company = db.execute_query(
                    "SELECT id, name, password_hash FROM companies WHERE email = ?", 
                    (email,), 
                    fetch=True
                )
                
                if company and verify_password(password, company[0][2]):
                    st.session_state.authenticated = True
                    st.session_state.company_id = company[0][0]
                    st.session_state.company_name = company[0][1]
                    st.success("Login realizado com sucesso!")
                    time.sleep(1)
                    st.session_state.current_page = 'dashboard'
                    st.rerun()
                else:
                    st.error("Email ou senha inválidos!")

def show_dashboard(db):
    st.markdown('<h1 class="main-header">📊 Dashboard</h1>', unsafe_allow_html=True)
    
    # Busca dados da empresa
    surveys = db.execute_query(
        "SELECT id, title, description, created_at, is_active FROM surveys WHERE company_id = ?",
        (st.session_state.company_id,),
        fetch=True
    )
    
    # Calcula estatísticas
    total_surveys = len(surveys)
    total_responses = 0
    
    for survey in surveys:
        responses = db.execute_query(
            "SELECT COUNT(*) FROM responses WHERE survey_id = ?",
            (survey[0],),
            fetch=True
        )
        total_responses += responses[0][0] if responses else 0
    
    # Exibe métricas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📋 Total de Pesquisas", total_surveys)
    
    with col2:
        st.metric("📝 Total de Respostas", total_responses)
    
    with col3:
        active_surveys = sum(1 for survey in surveys if survey[4])
        st.metric("✅ Pesquisas Ativas", active_surveys)
    
    st.markdown("---")
    
    # Lista de pesquisas recentes
    st.subheader("📋 Suas Pesquisas Recentes")
    
    if surveys:
        for survey in surveys[:5]:  # Mostra apenas as 5 mais recentes
            with st.expander(f"📊 {survey[1]}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Descrição:** {survey[2] or 'Sem descrição'}")
                    st.write(f"**Criada em:** {survey[3]}")
                    st.write(f"**Status:** {'🟢 Ativa' if survey[4] else '🔴 Inativa'}")
                
                with col2:
                    if st.button(f"Editar", key=f"edit_{survey[0]}"):
                        st.session_state.current_survey_id = survey[0]
                        st.session_state.current_page = 'edit_survey'
                        st.rerun()
                    
                    if st.button(f"Análises", key=f"analytics_{survey[0]}"):
                        st.session_state.current_survey_id = survey[0]
                        st.session_state.current_page = 'analytics'
                        st.rerun()
    else:
        st.info("Você ainda não criou nenhuma pesquisa. Clique em 'Nova Pesquisa' para começar!")

def show_new_survey_page(db):
    st.markdown('<h1 class="main-header">➕ Nova Pesquisa</h1>', unsafe_allow_html=True)
    
    with st.form("new_survey_form"):
        title = st.text_input("Título da Pesquisa")
        description = st.text_area("Descrição da Pesquisa")
        
        submitted = st.form_submit_button("Criar Pesquisa")
        
        if submitted:
            if not title:
                st.error("O título é obrigatório!")
            else:
                # Cria nova pesquisa
                public_id = str(uuid.uuid4())
                survey_id = db.execute_query(
                    "INSERT INTO surveys (title, description, company_id, public_id) VALUES (?, ?, ?, ?)",
                    (title, description, st.session_state.company_id, public_id)
                )
                
                st.success("Pesquisa criada com sucesso!")
                st.session_state.current_survey_id = survey_id
                time.sleep(1)
                st.session_state.current_page = 'edit_survey'
                st.rerun()

def show_my_surveys_page(db):
    st.markdown('<h1 class="main-header">📋 Minhas Pesquisas</h1>', unsafe_allow_html=True)
    
    surveys = db.execute_query(
        "SELECT id, title, description, public_id, created_at, is_active FROM surveys WHERE company_id = ? ORDER BY created_at DESC",
        (st.session_state.company_id,),
        fetch=True
    )
    
    if surveys:
        for survey in surveys:
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.write(f"**{survey[1]}**")
                    st.write(f"{survey[2] or 'Sem descrição'}")
                    st.write(f"🔗 Link público: `{survey[3]}`")
                
                with col2:
                    # Conta respostas
                    responses = db.execute_query(
                        "SELECT COUNT(*) FROM responses WHERE survey_id = ?",
                        (survey[0],),
                        fetch=True
                    )
                    st.metric("Respostas", responses[0][0] if responses else 0)
                
                with col3:
                    if st.button("Editar", key=f"edit_{survey[0]}"):
                        st.session_state.current_survey_id = survey[0]
                        st.session_state.current_page = 'edit_survey'
                        st.rerun()
                
                with col4:
                    if st.button("Análises", key=f"analytics_{survey[0]}"):
                        st.session_state.current_survey_id = survey[0]
                        st.session_state.current_page = 'analytics'
                        st.rerun()
                
                st.markdown("---")
    else:
        st.info("Você ainda não criou nenhuma pesquisa.")

def show_edit_survey_page(db):
    if 'current_survey_id' not in st.session_state:
        st.error("Pesquisa não encontrada!")
        return
    
    survey_id = st.session_state.current_survey_id
    
    # Busca dados da pesquisa
    survey = db.execute_query(
        "SELECT title, description, public_id FROM surveys WHERE id = ? AND company_id = ?",
        (survey_id, st.session_state.company_id),
        fetch=True
    )
    
    if not survey:
        st.error("Pesquisa não encontrada!")
        return
    
    survey = survey[0]
    
    st.markdown(f'<h1 class="main-header">✏️ Editando: {survey[0]}</h1>', unsafe_allow_html=True)
    
    # Informações da pesquisa
    st.info(f"🔗 **Link público:** `{survey[2]}`")
    
    # Busca perguntas existentes
    questions = db.execute_query(
        "SELECT id, text, question_type, options, importance, order_num FROM questions WHERE survey_id = ? ORDER BY order_num",
        (survey_id,),
        fetch=True
    )
    
    # Exibe perguntas existentes
    st.subheader("📝 Perguntas Atuais")
    
    if questions:
        for i, question in enumerate(questions):
            with st.expander(f"Pergunta {i+1}: {question[1][:50]}..."):
                st.write(f"**Texto:** {question[1]}")
                st.write(f"**Tipo:** {question[2]}")
                if question[3]:
                    st.write(f"**Opções:** {question[3]}")
                st.write(f"**Importância:** {question[4]}/5")
    else:
        st.info("Nenhuma pergunta adicionada ainda.")
    
    # Formulário para nova pergunta
    st.subheader("➕ Adicionar Nova Pergunta")
    
    with st.form("add_question_form"):
        text = st.text_area("Texto da Pergunta")
        question_type = st.selectbox(
            "Tipo de Pergunta",
            ["text", "multiple_choice", "rating"]
        )
        
        options = ""
        if question_type == "multiple_choice":
            options = st.text_area("Opções (uma por linha)")
        
        importance = st.slider("Importância", 1, 5, 3)
        
        submitted = st.form_submit_button("Adicionar Pergunta")
        
        if submitted:
            if not text:
                st.error("O texto da pergunta é obrigatório!")
            else:
                # Conta perguntas existentes para definir ordem
                question_count = len(questions)
                
                db.execute_query(
                    "INSERT INTO questions (survey_id, text, question_type, options, importance, order_num) VALUES (?, ?, ?, ?, ?, ?)",
                    (survey_id, text, question_type, options, importance, question_count + 1)
                )
                
                st.success("Pergunta adicionada com sucesso!")
                time.sleep(1)
                st.rerun()

def show_public_survey_page(db):
    st.markdown('<h1 class="main-header">📋 Responder Pesquisa</h1>', unsafe_allow_html=True)
    
    # Input para o ID público da pesquisa
    public_id = st.text_input("Digite o código da pesquisa:")
    
    if public_id:
        # Busca a pesquisa
        survey = db.execute_query(
            "SELECT id, title, description FROM surveys WHERE public_id = ? AND is_active = 1",
            (public_id,),
            fetch=True
        )
        
        if not survey:
            st.error("Pesquisa não encontrada ou inativa!")
            return
        
        survey = survey[0]
        survey_id = survey[0]
        
        st.success(f"Pesquisa encontrada: **{survey[1]}**")
        st.write(survey[2] or "")
        
        # Busca perguntas
        questions = db.execute_query(
            "SELECT id, text, question_type, options FROM questions WHERE survey_id = ? ORDER BY order_num",
            (survey_id,),
            fetch=True
        )
        
        if questions:
            with st.form("survey_response_form"):
                responses = {}
                
                for question in questions:
                    st.markdown(f"**{question[1]}**")
                    
                    if question[2] == "text":
                        responses[question[0]] = st.text_area("Sua resposta:", key=f"q_{question[0]}")
                    
                    elif question[2] == "multiple_choice":
                        options = question[3].split('\n') if question[3] else []
                        responses[question[0]] = st.selectbox("Escolha uma opção:", options, key=f"q_{question[0]}")
                    
                    elif question[2] == "rating":
                        responses[question[0]] = st.slider("Avalie de 1 a 5:", 1, 5, 3, key=f"q_{question[0]}")
                    
                    st.markdown("---")
                
                submitted = st.form_submit_button("Enviar Respostas")
                
                if submitted:
                    # Salva resposta
                    respondent_id = str(uuid.uuid4())
                    responses_json = json.dumps(responses)
                    
                    db.execute_query(
                        "INSERT INTO responses (survey_id, respondent_id, responses_data) VALUES (?, ?, ?)",
                        (survey_id, respondent_id, responses_json)
                    )
                    
                    st.success("Respostas enviadas com sucesso! Obrigado pela participação.")
                    
                    # Atualiza análise AI
                    update_ai_analysis(db, survey_id)
        else:
            st.warning("Esta pesquisa ainda não possui perguntas.")

def show_analytics_page(db):
    if 'current_survey_id' not in st.session_state:
        st.error("Pesquisa não encontrada!")
        return
    
    survey_id = st.session_state.current_survey_id
    
    # Busca dados da pesquisa
    survey = db.execute_query(
        "SELECT title, description FROM surveys WHERE id = ? AND company_id = ?",
        (survey_id, st.session_state.company_id),
        fetch=True
    )
    
    if not survey:
        st.error("Pesquisa não encontrada!")
        return
    
    survey = survey[0]
    
    st.markdown(f'<h1 class="main-header">📈 Análises: {survey[0]}</h1>', unsafe_allow_html=True)
    
    # Busca respostas
    responses = db.execute_query(
        "SELECT responses_data, created_at FROM responses WHERE survey_id = ?",
        (survey_id,),
        fetch=True
    )
    
    if not responses:
        st.warning("Esta pesquisa ainda não possui respostas.")
        return
    
    # Métricas básicas
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("📝 Total de Respostas", len(responses))
    
    with col2:
        # Respostas por dia
        dates = [r[1][:10] for r in responses]  # Extrai apenas a data
        unique_dates = len(set(dates))
        st.metric("📅 Dias com Respostas", unique_dates)
    
    with col3:
        # Média de respostas por dia
        avg_per_day = len(responses) / max(unique_dates, 1)
        st.metric("📊 Média por Dia", f"{avg_per_day:.1f}")
    
    # Gráfico de respostas ao longo do tempo
    st.subheader("📈 Respostas ao Longo do Tempo")
    
    df_responses = pd.DataFrame(responses, columns=['responses_data', 'created_at'])
    df_responses['date'] = pd.to_datetime(df_responses['created_at']).dt.date
    daily_counts = df_responses.groupby('date').size().reset_index(name='count')
    
    fig = px.line(daily_counts, x='date', y='count', title='Respostas por Dia')
    st.plotly_chart(fig, use_container_width=True)
    
    # Análise com IA
    st.subheader("🤖 Análise com Inteligência Artificial")
    
    # Busca análise existente
    ai_analysis = db.execute_query(
        "SELECT analysis_data, updated_at FROM ai_analyses WHERE survey_id = ? ORDER BY updated_at DESC LIMIT 1",
        (survey_id,),
        fetch=True
    )
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        if st.button("🔄 Atualizar Análise"):
            with st.spinner("Gerando análise com IA..."):
                update_ai_analysis(db, survey_id)
                st.success("Análise atualizada!")
                st.rerun()
    
    with col1:
        if ai_analysis:
            st.write(f"**Última atualização:** {ai_analysis[0][1]}")
            st.markdown("---")
            st.write(ai_analysis[0][0])
        else:
            st.info("Nenhuma análise disponível. Clique em 'Atualizar Análise' para gerar.")
    
    # Análise detalhada das respostas
    st.subheader("📊 Análise Detalhada das Respostas")
    
    # Busca perguntas para análise
    questions = db.execute_query(
        "SELECT id, text, question_type FROM questions WHERE survey_id = ? ORDER BY order_num",
        (survey_id,),
        fetch=True
    )
    
    if questions:
        for question in questions:
            question_id, question_text, question_type = question
            
            st.write(f"**{question_text}**")
            
            # Extrai respostas para esta pergunta
            question_responses = []
            for response in responses:
                try:
                    response_data = json.loads(response[0])
                    if str(question_id) in response_data:
                        question_responses.append(response_data[str(question_id)])
                except:
                    continue
            
            if question_responses:
                if question_type == "rating":
                    # Para perguntas de avaliação, mostra distribuição
                    ratings_df = pd.DataFrame({'rating': question_responses})
                    fig = px.histogram(ratings_df, x='rating', title=f'Distribuição - {question_text[:50]}...')
                    st.plotly_chart(fig, use_container_width=True)
                
                elif question_type == "multiple_choice":
                    # Para múltipla escolha, mostra gráfico de pizza
                    choices_df = pd.DataFrame({'choice': question_responses})
                    choice_counts = choices_df['choice'].value_counts()
                    fig = px.pie(values=choice_counts.values, names=choice_counts.index, 
                                title=f'Distribuição - {question_text[:50]}...')
                    st.plotly_chart(fig, use_container_width=True)
                
                else:
                    # Para texto, mostra algumas respostas
                    st.write("**Algumas respostas:**")
                    for i, resp in enumerate(question_responses[:5]):
                        st.write(f"• {resp}")
                    if len(question_responses) > 5:
                        st.write(f"... e mais {len(question_responses) - 5} respostas")
            
            st.markdown("---")

def update_ai_analysis(db, survey_id):
    """Atualiza análise AI para uma pesquisa"""
    try:
        # Busca dados da pesquisa
        survey = db.execute_query(
            "SELECT title, description FROM surveys WHERE id = ?",
            (survey_id,),
            fetch=True
        )
        
        if not survey:
            return
        
        survey = survey[0]
        
        # Busca perguntas
        questions = db.execute_query(
            "SELECT text, importance FROM questions WHERE survey_id = ?",
            (survey_id,),
            fetch=True
        )
        
        # Busca respostas
        responses = db.execute_query(
            "SELECT responses_data, created_at FROM responses WHERE survey_id = ?",
            (survey_id,),
            fetch=True
        )
        
        if not responses:
            return
        
        # Prepara dados para análise
        survey_data = {
            'title': survey[0],
            'description': survey[1],
            'questions': [{'text': q[0], 'importance': q[1]} for q in questions]
        }
        
        responses_data = []
        for response in responses:
            try:
                response_dict = json.loads(response[0])
                responses_data.append({
                    'date': response[1],
                    'answers': response_dict
                })
            except:
                continue
        
        # Chama OpenAI
        analysis_result = analyze_with_openai(survey_data, responses_data)
        
        # Salva ou atualiza análise
        existing_analysis = db.execute_query(
            "SELECT id FROM ai_analyses WHERE survey_id = ?",
            (survey_id,),
            fetch=True
        )
        
        if existing_analysis:
            db.execute_query(
                "UPDATE ai_analyses SET analysis_data = ?, updated_at = CURRENT_TIMESTAMP WHERE survey_id = ?",
                (analysis_result, survey_id)
            )
        else:
            db.execute_query(
                "INSERT INTO ai_analyses (survey_id, analysis_data) VALUES (?, ?)",
                (survey_id, analysis_result)
            )
    
    except Exception as e:
        st.error(f"Erro ao gerar análise: {str(e)}")

if __name__ == "__main__":
    main()
