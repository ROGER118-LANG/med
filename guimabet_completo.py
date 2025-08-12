# app.py
import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib

    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    print("Conectado ao banco de dados. Criando/Verificando tabelas...")

    # Tabela de usuários
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        points INTEGER DEFAULT 100,
        is_admin INTEGER DEFAULT 0
    )
    ''')

    # Tabela de times
    c.execute('''
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    ''')

    # Tabela de jogadores
    c.execute('''
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        team_id INTEGER,
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
    )
    ''')

    # Tabela de partidas
    c.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team1_id INTEGER,
        team2_id INTEGER,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        status TEXT DEFAULT 'upcoming',
        team1_score INTEGER,
        team2_score INTEGER,
        FOREIGN KEY (team1_id) REFERENCES teams (id),
        FOREIGN KEY (team2_id) REFERENCES teams (id)
    )
    ''')

    # Tabela de categorias de odds
    c.execute('''
    CREATE TABLE IF NOT EXISTS odds_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        is_active INTEGER DEFAULT 1
    )
    ''')

    # Tabela de templates de odds
    c.execute('''
    CREATE TABLE IF NOT EXISTS odds_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT NOT NULL,
        description TEXT,
        bet_type TEXT UNIQUE NOT NULL,
        default_odds REAL,
        is_active INTEGER DEFAULT 1,
        requires_player INTEGER DEFAULT 0,
        FOREIGN KEY (category_id) REFERENCES odds_categories (id)
    )
    ''')

    # Tabela de odds por partida
    c.execute('''
    CREATE TABLE IF NOT EXISTS match_odds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        template_id INTEGER,
        odds_value REAL,
        is_active INTEGER DEFAULT 1,
        player_id INTEGER,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (template_id) REFERENCES odds_templates (id),
        FOREIGN KEY (player_id) REFERENCES players (id)
    )
    ''')
    
    # Tabela de histórico de odds
    c.execute('''
    CREATE TABLE IF NOT EXISTS odds_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_odds_id INTEGER,
        old_value REAL,
        new_value REAL,
        changed_by TEXT,
        changed_at TEXT,
        reason TEXT,
        FOREIGN KEY (match_odds_id) REFERENCES match_odds (id)
    )
    ''')

    # Tabela de apostas personalizadas
    c.execute('''
    CREATE TABLE IF NOT EXISTS custom_bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        description TEXT NOT NULL,
        odds REAL NOT NULL,
        player_id INTEGER,
        status TEXT DEFAULT 'pending', -- pending, won, lost
        created_by TEXT,
        created_at TEXT,
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (player_id) REFERENCES players (id)
    )
    ''')

    # Tabela de propostas de apostas
    c.execute('''
    CREATE TABLE IF NOT EXISTS custom_bet_proposals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        match_id INTEGER,
        description TEXT,
        proposed_odds REAL,
        status TEXT DEFAULT 'pending', -- pending, approved, rejected
        admin_response TEXT,
        created_at TEXT,
        reviewed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (username),
        FOREIGN KEY (match_id) REFERENCES matches (id)
    )
    ''')

    # Tabela principal de apostas dos usuários (COM A ESTRUTURA CORRETA)
    c.execute('''
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        match_id INTEGER,
        amount REAL,
        odds REAL,
        status TEXT DEFAULT 'pending',
        timestamp TEXT,
        match_odds_id INTEGER,  -- <<-- COLUNA ESSENCIAL QUE ESTAVA FALTANDO
        custom_bet_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (username),
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (match_odds_id) REFERENCES match_odds (id),
        FOREIGN KEY (custom_bet_id) REFERENCES custom_bets (id)
    )
    ''')
# ==============================================================================

def db_connect():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_user(username, password):
    conn = db_connect()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password)).fetchone()
    conn.close()
    return user

def register_user(username, password):
    if not username or not password: return False, "Usuário e senha não podem ser vazios."
    conn = db_connect()
    try:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        return True, "Conta criada com sucesso! Faça o login."
    except sqlite3.IntegrityError: return False, "Este nome de usuário já existe."
    finally: conn.close()

def get_user_points(username):
    conn = db_connect()
    points = conn.execute("SELECT points FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return points['points'] if points else 0

def get_team_name(team_id):
    conn = db_connect()
    name = conn.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
    conn.close()
    return name['name'] if name else "Desconhecido"

def get_upcoming_matches_with_names():
    conn = db_connect()
    matches = [dict(row) for row in conn.execute("""
        SELECT m.id, m.date, m.time, t1.name as team1_name, t2.name as team2_name
        FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.status = 'upcoming' ORDER BY m.date, m.time
    """).fetchall()]
    conn.close()
    return matches

def get_match_odds(match_id):
    conn = db_connect()
    odds = [dict(row) for row in conn.execute("""
        SELECT mo.id, mo.odds_value, ot.name as template_name, ot.description
        FROM match_odds mo JOIN odds_templates ot ON mo.template_id = ot.id
        WHERE mo.match_id = ? AND mo.is_active = 1
    """, (match_id,)).fetchall()]
    conn.close()
    return odds

def place_bet(username, match_id, match_odds_id, amount):
    if amount is None or amount <= 0: return False, "O valor da aposta deve ser maior que zero."
    conn = db_connect()
    try:
        user_row = conn.execute("SELECT points FROM users WHERE username = ?", (username,)).fetchone()
        if user_row is None: return False, "Erro: Usuário não encontrado."
        user_points = user_row['points']
        if user_points < amount: return False, "Pontos insuficientes."
        
        odd_info = conn.execute("SELECT odds_value FROM match_odds WHERE id = ?", (match_odds_id,)).fetchone()
        if not odd_info: return False, "Odd não encontrada."
        
        conn.execute("UPDATE users SET points = points - ? WHERE username = ?", (amount, username))
        conn.execute("""
            INSERT INTO bets (user_id, match_id, amount, odds, match_odds_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, match_id, amount, odd_info['odds_value'], match_odds_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True, "Aposta realizada com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, f"Erro interno ao realizar aposta: {e}"
    finally: conn.close()

def get_user_bets(username):
    """Busca o histórico de apostas de um usuário (CONSULTA CORRIGIDA)."""
    conn = db_connect()
    bets = [dict(row) for row in conn.execute("""
        SELECT 
            b.amount, b.odds, b.status, b.timestamp,
            t1.name as team1_name, t2.name as team2_name,
            ot.name as bet_name
        FROM bets b
        JOIN matches m ON b.match_id = m.id
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        LEFT JOIN match_odds mo ON b.match_odds_id = mo.id
        LEFT JOIN odds_templates ot ON mo.template_id = ot.id
        WHERE b.user_id = ? ORDER BY b.timestamp DESC
    """, (username,)).fetchall()]
    conn.close()
    return bets

# ==============================================================================
# INTERFACE DO USUÁRIO (UI)
# ==============================================================================

def login_page():
    st.title("Bem-vindo ao GuimaBet!")
    tab1, tab2 = st.tabs(["Entrar", "Registrar"])
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                user = login_user(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = user['username']
                    st.session_state.is_admin = bool(user['is_admin'])
                    st.success("Login bem-sucedido!")
                    st.rerun()
                else: st.error("Usuário ou senha inválidos.")
    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("Escolha um nome de usuário")
            new_password = st.text_input("Crie uma senha", type="password")
            if st.form_submit_button("Registrar"):
                success, message = register_user(new_username, new_password)
                if success: st.success(message)
                else: st.error(message)

def main_dashboard():
    st.sidebar.title(f"Olá, {st.session_state.username}!")
    st.sidebar.metric("Seus Pontos", get_user_points(st.session_state.username))
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    pages = ["Apostar", "Minhas Apostas"]
    if st.session_state.get('is_admin', False): pages.append("Painel do Admin")
    selection = st.sidebar.radio("Navegação", pages)

    if selection == "Apostar": betting_page()
    elif selection == "Minhas Apostas": my_bets_page()
    elif selection == "Painel do Admin":
        st.title("Painel do Admin")
        st.info("A funcionalidade de administração deve ser colocada em um arquivo separado (`admin_panel.py`) para melhor organização.")

def betting_page():
    st.title("Partidas Disponíveis")
    matches = get_upcoming_matches_with_names()
    if not matches:
        st.info("Nenhuma partida futura disponível no momento.")
        return
    for match in matches:
        with st.expander(f"{match['team1_name']} vs {match['team2_name']} ({match['date']} {match['time']})"):
            odds = get_match_odds(match['id'])
            if not odds:
                st.write("Odds para esta partida ainda não foram definidas.")
                continue
            with st.form(f"bet_form_{match['id']}"):
                odds_dict = {f"{o['template_name']} ({o['odds_value']:.2f})": o['id'] for o in odds}
                selected_odd_str = st.selectbox("Escolha sua aposta:", options=list(odds_dict.keys()))
                amount = st.number_input("Valor da aposta (pontos)", min_value=1, value=1, step=1)
                if st.form_submit_button("Fazer Aposta"):
                    selected_odd_id = odds_dict[selected_odd_str]
                    success, message = place_bet(st.session_state.username, match['id'], selected_odd_id, amount)
                    if success:
                        st.success(message)
                        st.rerun()
                    else: st.error(message)

def my_bets_page():
    st.title("Meu Histórico de Apostas")
    bets = get_user_bets(st.session_state.username)
    if not bets:
        st.info("Você ainda não fez nenhuma aposta.")
        return
    for bet in bets:
        status_color = {"pending": "grey", "won": "green", "lost": "red"}
        status_icon = {"pending": "⏳", "won": "✅", "lost": "❌"}
        with st.container(border=True):
            st.write(f"**{bet['team1_name']} vs {bet['team2_name']}**")
            bet_name = bet.get('bet_name', 'Aposta Indefinida')
            st.write(f"Sua aposta: *{bet_name}*")
            col1, col2, col3 = st.columns(3)
            col1.metric("Apostado", f"{bet['amount']} pts")
            col2.metric("Odds", f"{bet['odds']:.2f}")
            status = bet['status']
            winnings = bet['amount'] * bet['odds']
            if status == 'won': col3.metric("Resultado", f"+{winnings:.0f} pts", delta_color="normal")
            elif status == 'lost': col3.metric("Resultado", f"-{bet['amount']} pts", delta_color="inverse")
            else: col3.metric("Ganhos Potenciais", f"{winnings:.0f} pts", delta_color="off")
            st.caption(f"Status: :{status_color.get(status, 'grey')}[{status.upper()}] {status_icon.get(status, '')} | Data: {bet['timestamp']}")

# ==============================================================================
# LÓGICA PRINCIPAL DA APLICAÇÃO
# ==============================================================================

def main():
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if not st.session_state.logged_in:
        login_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    try:
        with open('guimabet.db', 'r') as f: pass
    except FileNotFoundError:
        st.error("Banco de dados 'guimabet.db' não encontrado!")
        st.info("Por favor, rode o script 'guimabet_database.py' primeiro para criar o banco de dados.")
        st.stop()
    main()
