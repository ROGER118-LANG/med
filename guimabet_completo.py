import streamlit as st
import pandas as pd
import datetime
import sqlite3
import hashlib
import admin_panel_enhanced # Certifique-se de que este arquivo está na mesma pasta

# --- Funções de Banco de Dados ---

def create_admin_if_not_exists(c):
    """Cria o usuário admin padrão se ele não existir."""
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        # Senha "123" criptografada com SHA-256
        hashed_password = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, points, is_admin) VALUES (?, ?, ?, ?)",
                  ("admin", hashed_password, 1000, 1))
        print("Usuário 'admin' criado com sucesso.")

def init_db():
    """Inicializa o banco de dados e cria as tabelas se não existirem."""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            points INTEGER,
            is_admin INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS matches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team1_id INTEGER,
            team2_id INTEGER,
            date TEXT,
            time TEXT,
            status TEXT DEFAULT 'upcoming',
            team1_score INTEGER DEFAULT 0,
            team2_score INTEGER DEFAULT 0
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS players (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            team_id INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            match_id INTEGER,
            bet_type TEXT,
            amount REAL,
            odds REAL,
            status TEXT DEFAULT 'pending',
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
            custom_bet_id INTEGER DEFAULT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS odds_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            description TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS odds_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGER,
            name TEXT,
            description TEXT,
            bet_type TEXT UNIQUE,
            default_odds REAL,
            requires_player INTEGER
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS match_odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            template_id INTEGER,
            odds_value REAL,
            player_id INTEGER DEFAULT NULL,
            last_updated_by TEXT,
            last_updated_reason TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS custom_bets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id INTEGER,
            description TEXT,
            odds REAL,
            player_id INTEGER DEFAULT NULL,
            status TEXT DEFAULT 'pending'
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS custom_bet_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            match_id INTEGER,
            description TEXT,
            proposed_odds REAL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Garante que o usuário admin exista
    create_admin_if_not_exists(c)
    
    conn.commit()
    conn.close()

def register_user(username, password):
    """Registra um novo usuário com senha criptografada."""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    try:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, points, is_admin) VALUES (?, ?, ?, ?)", (username, hashed_password, 100, 0))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Username already exists
    finally:
        conn.close()

def login(username, password):
    """Valida o login do usuário comparando a senha criptografada."""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    return user

def get_user_points(username):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE username = ?", (username,))
    points = c.fetchone()
    conn.close()
    return points[0] if points else 0

def update_user_points(username, points):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("UPDATE users SET points = ? WHERE username = ?", (points, username))
    conn.commit()
    conn.close()

def get_upcoming_matches():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE status = 'upcoming' ORDER BY date, time")
    matches = [dict(row) for row in c.fetchall()]
    conn.close()
    return matches

def get_match_by_id(match_id):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
    match = c.fetchone()
    conn.close()
    return dict(match) if match else None

def get_team_name(team_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT name FROM teams WHERE id = ?", (team_id,))
    name = c.fetchone()
    conn.close()
    return name[0] if name else "Desconhecido"

def get_match_odds(match_id):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT mo.id, mo.odds_value, mo.player_id, ot.name as template_name, ot.description, oc.name as category_name
        FROM match_odds mo
        JOIN odds_templates ot ON mo.template_id = ot.id
        JOIN odds_categories oc ON ot.category_id = oc.id
        WHERE mo.match_id = ?
    """, (match_id,))
    odds = [dict(row) for row in c.fetchall()]
    conn.close()
    return odds

# --- Interface do Streamlit ---

# Inicialização do estado da sessão
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.is_admin = False
    st.session_state.page = "main"

def login_page():
    """Página de login e registro."""
    st.title("Bem-vindo ao GuimaBet!")
    
    tab1, tab2 = st.tabs(["Entrar", "Registrar"])
    
    with tab1:
        st.subheader("Entrar na sua conta")
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("Usuário", key="login_username")
            password = st.text_input("Senha", type="password", key="login_password")
            # CORRIGIDO: Removido o argumento 'key'
            submit = st.form_submit_button("Entrar")
            
            if submit:
                user = login(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = user[0] # username
                    st.session_state.is_admin = bool(user[3]) # is_admin
                    st.session_state.page = "main"
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos")
    
    with tab2:
        st.subheader("Criar nova conta")
        with st.form("register_form", clear_on_submit=True):
            new_username = st.text_input("Novo Usuário", key="register_username")
            new_password = st.text_input("Nova Senha", type="password", key="register_password")
            # CORRIGIDO: Removido o argumento 'key'
            register_submit = st.form_submit_button("Registrar")
            
            if register_submit:
                if not new_username or not new_password:
                    st.warning("Por favor, preencha todos os campos.")
                elif register_user(new_username, new_password):
                    st.success("Conta criada com sucesso! Faça login para continuar.")
                else:
                    st.error("Nome de usuário já existe.")

def user_dashboard():
    """Dashboard principal para usuários logados."""
    st.sidebar.title(f"Olá, {st.session_state.username}!")
    st.sidebar.write(f"**Pontos:** {get_user_points(st.session_state.username)}")
    
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.session_state.page = "main"
        st.rerun()

    if st.session_state.is_admin:
        st.sidebar.subheader("Opções de Administrador")
        if st.sidebar.button("Painel Admin"):
            st.session_state.page = "admin_panel"
            st.rerun()

    # Botão para voltar ao dashboard principal
    if st.session_state.page != "main":
        if st.sidebar.button("Voltar ao Início"):
            st.session_state.page = "main"
            st.rerun()

    st.title("GuimaBet Dashboard")

    # Roteamento de página
    if st.session_state.is_admin and st.session_state.get('page') == 'admin_panel':
        admin_panel_enhanced.main_admin_panel_content()
    else:
        main_user_content()

def main_user_content():
    """Conteúdo principal do dashboard do usuário."""
    st.header("Partidas Disponíveis")
    matches = get_upcoming_matches()
    if matches:
        for match in matches:
            team1 = get_team_name(match['team1_id'])
            team2 = get_team_name(match['team2_id'])
            st.subheader(f"{team1} vs {team2}")
            st.caption(f"Data: {match['date']} - Hora: {match['time']}")
            
            odds = get_match_odds(match['id'])
            if odds:
                with st.expander("Ver e Apostar nas Odds"):
                    with st.form(f"bet_form_{match['id']}"):
                        st.write("**Odds disponíveis:**")
                        
                        # Usar um dicionário para facilitar a busca da odd selecionada
                        odds_dict = {o['id']: o for o in odds}
                        
                        selected_odd_id = st.selectbox(
                            "Selecione sua aposta:",
                            options=list(odds_dict.keys()),
                            format_func=lambda x: f"{odds_dict[x]['template_name']} (Odd: {odds_dict[x]['odds_value']})",
                            key=f"odd_select_{match['id']}"
                        )
                        
                        amount = st.number_input("Valor da Aposta:", min_value=1, value=10, step=1, key=f"bet_amount_{match['id']}")
                        
                        # CORRIGIDO: Removido o argumento 'key'
                        bet_submit = st.form_submit_button("Fazer Aposta")
                        
                        if bet_submit:
                            user_points = get_user_points(st.session_state.username)
                            if user_points >= amount:
                                # Lógica para registrar a aposta (placeholder)
                                st.success(f"Aposta de {amount} pontos realizada com sucesso!")
                                update_user_points(st.session_state.username, user_points - amount)
                                st.rerun()
                            else:
                                st.error("Pontos insuficientes para realizar esta aposta.")
            else:
                st.info("Odds ainda não disponíveis para esta partida.")
    else:
        st.info("Nenhuma partida futura disponível no momento.")

    st.header("Minhas Apostas")
    st.write("Em breve: Suas apostas ativas e histórico aparecerão aqui.")

def main():
    """Função principal que executa a aplicação."""
    init_db()
    if not st.session_state.logged_in:
        login_page()
    else:
        user_dashboard()

if __name__ == "__main__":
    main()
