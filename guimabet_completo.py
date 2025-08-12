# app.py
import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import os

DB_FILE = "guimabet.db"

# ==============================================================================
# 1. LÓGICA DE CRIAÇÃO E INICIALIZAÇÃO DO BANCO DE DADOS
# ==============================================================================

def init_db():
    """
    Cria e inicializa o banco de dados com todas as tabelas e dados padrão.
    """
    conn = sqlite3.connect(DB_FILE)
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
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_id INTEGER, odds_value REAL, description TEXT,
        FOREIGN KEY (match_id) REFERENCES matches (id)
    )''')
    
    # Tabela de apostas dos usuários (ESTRUTURA CORRETA E FINAL)
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
    conn = sqlite3.connect(DB_FILE)
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

def get_all_data(table_name):
    conn = db_connect()
    data = [dict(row) for row in conn.execute(f"SELECT * FROM {table_name}").fetchall()]
    conn.close()
    return data

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
    odds = [dict(row) for row in conn.execute("SELECT * FROM match_odds WHERE match_id = ?", (match_id,)).fetchall()]
    conn.close()
    return odds

def place_bet(username, match_id, match_odds_id, amount):
    if amount is None or amount <= 0: return False, "O valor da aposta deve ser maior que zero."
    conn = db_connect()
    try:
        user_row = conn.execute("SELECT points FROM users WHERE username = ?", (username,)).fetchone()
        if user_row is None: return False, "Erro: Usuário não encontrado."
        if user_row['points'] < amount: return False, "Pontos insuficientes."
        
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
    bets = [dict(row) for row in conn.execute("""
        SELECT b.amount, b.odds, b.status, b.timestamp, t1.name as team1_name, t2.name as team2_name, mo.description as bet_name
        FROM bets b
        JOIN matches m ON b.match_id = m.id JOIN teams t1 ON m.team1_id = t1.id JOIN teams t2 ON m.team2_id = t2.id
        LEFT JOIN match_odds mo ON b.match_odds_id = mo.id
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
            username = st.text_input("Usuário", value="admin")
            password = st.text_input("Senha", type="password", value="123")
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
    st.sidebar.metric("Seus Pontos", get_all_data("users")[0]['points'] if st.session_state.username == 'admin' else [u for u in get_all_data('users') if u['username'] == st.session_state.username][0]['points'])
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
                        conn.execute("INSERT INTO match_odds (match_id, odds_value, description) VALUES (?, ?, ?)", (match['id'], 2.10, f"Vitória {match['team1_name']}"))
                        conn.execute("INSERT INTO match_odds (match_id, odds_value, description) VALUES (?, ?, ?)", (match['id'], 3.20, "Empate"))
                        conn.execute("INSERT INTO match_odds (match_id, odds_value, description) VALUES (?, ?, ?)", (match['id'], 2.50, f"Vitória {match['team2_name']}"))
                        conn.commit()
                        conn.close()
                        st.success("Odds padrão criadas!"); st.rerun()
                continue
            with st.form(f"bet_form_{match['id']}"):
                odds_dict = {f"{o['description']} ({o['odds_value']:.2f})": o['id'] for o in odds}
                selected_odd_str = st.selectbox("Escolha sua aposta:", options=list(odds_dict.keys()))
                amount = st.number_input("Valor da aposta (pontos)", min_value=1, value=1, step=1)
                if st.form_submit_button("Fazer Aposta"):
                    selected_odd_id = odds_dict[selected_odd_str]
                    success, message = place_bet(st.session_state.username, match['id'], selected_odd_id, amount)
                    if success:
                        st.success(message); st.rerun()
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
            st.write(f"Sua aposta: *{bet.get('bet_name', 'Resultado')}*")
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
    with st.sidebar:
        admin_selection = st.radio("Menu do Admin", admin_pages, label_visibility="collapsed")

    if admin_selection == "Gerenciar Partidas": manage_matches_page()
    elif admin_selection == "Gerenciar Times": manage_teams_page()
    elif admin_selection == "Gerenciar Usuários": manage_users_page()

def manage_matches_page():
    st.header("Gerenciar Partidas")
    st.subheader("Adicionar Nova Partida")
    teams = get_all_data("teams")
    if len(teams) < 2:
        st.warning("Você precisa de pelo menos 2 times para criar uma partida.")
    else:
        team_dict = {t['name']: t['id'] for t in teams}
        with st.form("add_match"):
            c1, c2 = st.columns(2)
            team1 = c1.selectbox("Time 1", options=team_dict.keys())
            team2 = c2.selectbox("Time 2", options=team_dict.keys(), index=1)
            c1, c2 = st.columns(2)
            date = c1.date_input("Data")
            time = c2.time_input("Hora")
            if st.form_submit_button("Adicionar Partida"):
                if team1 == team2: st.error("Os times devem ser diferentes.")
                else:
                    conn = db_connect()
                    conn.execute("INSERT INTO matches (team1_id, team2_id, date, time) VALUES (?, ?, ?, ?)",
                                 (team_dict[team1], team_dict[team2], date.isoformat(), time.isoformat()))
                    conn.commit()
                    conn.close()
                    st.success("Partida adicionada!"); st.rerun()

    st.divider()
    st.subheader("Finalizar Partidas Pendentes")
    matches = get_upcoming_matches_with_names()
    if not matches: st.info("Nenhuma partida para finalizar.")
    else:
        for match in matches:
            with st.expander(f"{match['team1_name']} vs {match['team2_name']}"):
                with st.form(key=f"form_match_{match['id']}"):
                    c1, c2 = st.columns(2)
                    score1 = c1.number_input(f"Gols {match['team1_name']}", min_value=0, step=1)
                    score2 = c2.number_input(f"Gols {match['team2_name']}", min_value=0, step=1)
                    if st.form_submit_button("Finalizar e Pagar Apostas"):
                        conn = db_connect()
                        conn.execute("UPDATE matches SET status='completed', team1_score=?, team2_score=? WHERE id=?", (score1, score2, match['id']))
                        bets = conn.execute("SELECT * FROM bets WHERE match_id=? AND status='pending'", (match['id'],)).fetchall()
                        for bet in bets:
                            odd_info = conn.execute("SELECT * FROM match_odds WHERE id=?", (bet['match_odds_id'],)).fetchone()
                            # Lógica de vitória simplificada
                            is_winner = (score1 > score2 and "Vitória" in odd_info['description'] and match['team1_name'] in odd_info['description']) or \
                                        (score2 > score1 and "Vitória" in odd_info['description'] and match['team2_name'] in odd_info['description']) or \
                                        (score1 == score2 and "Empate" in odd_info['description'])
                            if is_winner:
                                winnings = bet['amount'] * bet['odds']
                                conn.execute("UPDATE users SET points = points + ? WHERE username=?", (winnings, bet['user_id']))
                                conn.execute("UPDATE bets SET status='won' WHERE id=?", (bet['id'],))
                            else:
                                conn.execute("UPDATE bets SET status='lost' WHERE id=?", (bet['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Partida finalizada!"); st.rerun()

def manage_teams_page():
    st.header("Gerenciar Times")
    st.subheader("Adicionar Novo Time")
    with st.form("add_team"):
        name = st.text_input("Nome do Time")
        if st.form_submit_button("Adicionar"):
            if name:
                conn = db_connect()
                try:
                    conn.execute("INSERT INTO teams (name) VALUES (?)", (name,))
                    conn.commit()
                    st.success("Time adicionado!"); st.rerun()
                except sqlite3.IntegrityError: st.error("Este time já existe.")
                finally: conn.close()
    st.divider()
    st.subheader("Times Existentes")
    teams = get_all_data("teams")
    for team in teams:
        with st.expander(team['name']):
            new_name = st.text_input("Novo nome", value=team['name'], key=f"name_{team['id']}")
            if st.button("Salvar", key=f"save_{team['id']}"):
                conn = db_connect()
                conn.execute("UPDATE teams SET name=? WHERE id=?", (new_name, team['id']))
                conn.commit()
                conn.close()
                st.success("Time atualizado!"); st.rerun()

def manage_users_page():
    st.header("Gerenciar Usuários")
    users = get_all_data("users")
    for user in users:
        with st.expander(f"{user['username']} (Admin: {'Sim' if user['is_admin'] else 'Não'})"):
            with st.form(key=f"user_{user['username']}"):
                points = st.number_input("Pontos", value=user['points'], min_value=0)
                is_admin = st.checkbox("Permissão de Admin", value=bool(user['is_admin']))
                if st.form_submit_button("Atualizar Usuário"):
                    conn = db_connect()
                    conn.execute("UPDATE users SET points=?, is_admin=? WHERE username=?", (points, int(is_admin), user['username']))
                    conn.commit()
                    conn.close()
                    st.success("Usuário atualizado!"); st.rerun()

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
    if not os.path.exists(DB_FILE):
        st.info("Banco de dados não encontrado. Criando e inicializando...")
        init_db()
    
    main()
