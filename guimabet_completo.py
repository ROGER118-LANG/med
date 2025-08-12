# app.py
import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib

# ==============================================================================
# 1. LÓGICA DE CRIAÇÃO E INICIALIZAÇÃO DO BANCO DE DADOS
# ==============================================================================

def init_db():
    """
    Cria e inicializa o banco de dados com todas as tabelas e dados padrão.
    """
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Tabela de usuários
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY, password TEXT NOT NULL, points INTEGER DEFAULT 100, is_admin INTEGER DEFAULT 0
    )''')

    # Tabela de times
    c.execute('''
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL
    )''')

    # Tabela de jogadores
    c.execute('''
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, team_id INTEGER,
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
    )''')

    # Tabela de partidas
    c.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT, team1_id INTEGER, team2_id INTEGER, date TEXT NOT NULL, time TEXT NOT NULL,
        status TEXT DEFAULT 'upcoming', team1_score INTEGER, team2_score INTEGER,
        FOREIGN KEY (team1_id) REFERENCES teams (id), FOREIGN KEY (team2_id) REFERENCES teams (id)
    )''')

    # Tabela de odds por partida
    c.execute('''
    CREATE TABLE IF NOT EXISTS match_odds (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER, template_id INTEGER, odds_value REAL,
        is_active INTEGER DEFAULT 1, player_id INTEGER, created_at TEXT, updated_at TEXT,
        FOREIGN KEY (match_id) REFERENCES matches (id)
    )''')
    
    # Tabela de apostas dos usuários (ESTRUTURA CORRIGIDA)
    c.execute('''
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, match_id INTEGER, amount REAL, odds REAL,
        status TEXT DEFAULT 'pending', timestamp TEXT, match_odds_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (username), FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (match_odds_id) REFERENCES match_odds (id)
    )''')

    # --- Inserção de Dados Padrão ---
    try:
        hashed_password = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, points, is_admin) VALUES (?, ?, ?, ?)",
                  ("admin", hashed_password, 1000, 1))
    except sqlite3.IntegrityError: pass

    default_teams = ["Tropa da Sônia", "Cubanos", "Dynamos", "Os Feras", "Gaviões", "Leões do Recreio"]
    try:
        c.executemany("INSERT INTO teams (name) VALUES (?)", [(team,) for team in default_teams])
    except sqlite3.IntegrityError: pass

    conn.commit()
    conn.close()
    st.toast("Banco de dados inicializado com sucesso!")

# ==============================================================================
# 2. FUNÇÕES DE BANCO DE DADOS (DB)
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
    # Simplificando a busca de odds para evitar dependências complexas
    odds = [dict(row) for row in conn.execute("""
        SELECT id, odds_value, template_id FROM match_odds WHERE match_id = ? AND is_active = 1
    """, (match_id,)).fetchall()]
    # Adicionando um nome simples para exibição
    for odd in odds:
        odd['template_name'] = f"Aposta Tipo {odd['template_id']}"
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
    conn = db_connect()
    # Consulta simplificada para garantir que funcione com a estrutura básica
    bets = [dict(row) for row in conn.execute("""
        SELECT b.amount, b.odds, b.status, b.timestamp, t1.name as team1_name, t2.name as team2_name
        FROM bets b
        JOIN matches m ON b.match_id = m.id
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE b.user_id = ? ORDER BY b.timestamp DESC
    """, (username,)).fetchall()]
    conn.close()
    return bets

# ==============================================================================
# 3. INTERFACE DO USUÁRIO (UI)
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
    elif selection == "Painel do Admin": admin_panel()

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
                if st.session_state.get('is_admin'):
                    if st.button("Criar Odds Padrão", key=f"create_odds_{match['id']}"):
                        conn = db_connect()
                        # Simplesmente cria uma odd de vitória para cada time
                        conn.execute("INSERT INTO match_odds (match_id, template_id, odds_value) VALUES (?, ?, ?)", (match['id'], 1, 2.0))
                        conn.execute("INSERT INTO match_odds (match_id, template_id, odds_value) VALUES (?, ?, ?)", (match['id'], 2, 2.0))
                        conn.commit()
                        conn.close()
                        st.success("Odds padrão criadas!")
                        st.rerun()
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
            st.write(f"Sua aposta: *Aposta em Resultado*") # Simplificado
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
# 4. PAINEL DE ADMINISTRAÇÃO
# ==============================================================================

def admin_panel():
    st.title("Painel de Administração")
    admin_pages = ["Gerenciar Partidas", "Gerenciar Times", "Gerenciar Usuários"]
    admin_selection = st.selectbox("Selecione uma área para gerenciar", admin_pages)

    if admin_selection == "Gerenciar Partidas":
        manage_matches_page()
    elif admin_selection == "Gerenciar Times":
        manage_teams_page()
    elif admin_selection == "Gerenciar Usuários":
        manage_users_page()

def manage_matches_page():
    st.header("Gerenciar Partidas")
    conn = db_connect()
    matches = conn.execute("SELECT m.*, t1.name as t1_name, t2.name as t2_name FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN teams t2 ON m.team2_id = t2.id WHERE m.status = 'upcoming'").fetchall()
    conn.close()
    
    st.subheader("Finalizar Partidas")
    if not matches:
        st.info("Nenhuma partida futura para finalizar.")
    else:
        for match in matches:
            with st.expander(f"{match['t1_name']} vs {match['t2_name']}"):
                with st.form(key=f"form_match_{match['id']}"):
                    c1, c2 = st.columns(2)
                    score1 = c1.number_input(f"Gols {match['t1_name']}", min_value=0, step=1)
                    score2 = c2.number_input(f"Gols {match['t2_name']}", min_value=0, step=1)
                    if st.form_submit_button("Finalizar Partida"):
                        # Lógica de finalização
                        conn = db_connect()
                        conn.execute("UPDATE matches SET status='completed', team1_score=?, team2_score=? WHERE id=?", (score1, score2, match['id']))
                        # Lógica de pagamento de apostas (simplificada)
                        bets_to_resolve = conn.execute("SELECT * FROM bets WHERE match_id=? AND status='pending'", (match['id'],)).fetchall()
                        for bet in bets_to_resolve:
                            # Vitória Time 1
                            if score1 > score2 and bet['match_odds_id'] == 1: # Simplificação: ID 1 = vitória time 1
                                conn.execute("UPDATE users SET points = points + ? WHERE username=?", (bet['amount'] * bet['odds'], bet['user_id']))
                                conn.execute("UPDATE bets SET status='won' WHERE id=?", (bet['id'],))
                            else:
                                conn.execute("UPDATE bets SET status='lost' WHERE id=?", (bet['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Partida finalizada e apostas processadas!")
                        st.rerun()

def manage_teams_page():
    st.header("Gerenciar Times")
    conn = db_connect()
    teams = conn.execute("SELECT * FROM teams").fetchall()
    st.dataframe(teams)
    conn.close()

def manage_users_page():
    st.header("Gerenciar Usuários")
    conn = db_connect()
    users = conn.execute("SELECT username, points, is_admin FROM users").fetchall()
    st.dataframe(users)
    conn.close()

# ==============================================================================
# 5. LÓGICA PRINCIPAL DA APLICAÇÃO
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
        st.info("Banco de dados não encontrado. Criando e inicializando...")
        init_db()
    
    main()
