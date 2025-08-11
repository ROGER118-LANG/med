import streamlit as st
import pandas as pd
import datetime
import sqlite3

# Importar o admin_panel_enhanced como um módulo
import admin_panel_enhanced

# Funções de banco de dados (assumindo que estão em guimabet_melhorado.py ou similar)
# Para este exemplo, vamos mockar algumas funções ou importá-las se existirem
# from guimabet_melhorado import *

# Mock de funções de banco de dados para que o Streamlit possa rodar
def init_db():
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
            status TEXT DEFAULT 'pending' -- pending, approved, rejected, finished
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS custom_bet_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            match_id INTEGER,
            description TEXT,
            proposed_odds REAL,
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def register_user(username, password):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password, points, is_admin) VALUES (?, ?, ?, ?)", (username, password, 1000, 0))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False # Username already exists
    finally:
        conn.close()

def login(username, password):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    return user

def get_user_points(username):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE username = ?", (username,))
    points = c.fetchone()[0]
    conn.close()
    return points

def update_user_points(username, points):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("UPDATE users SET points = ? WHERE username = ?", (points, username))
    conn.commit()
    conn.close()

def get_upcoming_matches():
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE status = 'upcoming' ORDER BY date, time")
    matches = c.fetchall()
    conn.close()
    return [{k: item[i] for i, k in enumerate(['id', 'team1_id', 'team2_id', 'date', 'time', 'status', 'team1_score', 'team2_score'])} for item in matches]

def get_match_by_id(match_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE id = ?", (match_id,))
    match = c.fetchone()
    conn.close()
    if match:
        return {k: match[i] for i, k in enumerate(['id', 'team1_id', 'team2_id', 'date', 'time', 'status', 'team1_score', 'team2_score'])}
    return None

def get_team_name(team_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT name FROM teams WHERE id = ?", (team_id,))
    name = c.fetchone()
    conn.close()
    return name[0] if name else "Desconhecido"

def get_all_teams():
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM teams")
    teams = c.fetchall()
    conn.close()
    return [{'id': t[0], 'name': t[1]} for t in teams]

def get_all_players():
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT id, name, team_id FROM players")
    players = c.fetchall()
    conn.close()
    return [{'id': p[0], 'name': p[1], 'team_id': p[2]} for p in players]

def get_player_name(player_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT name FROM players WHERE id = ?", (player_id,))
    name = c.fetchone()
    conn.close()
    return name[0] if name else "Desconhecido"

def get_match_players(match_id):
    match = get_match_by_id(match_id)
    if not match:
        return []
    team1_players = get_players_by_team(match['team1_id'])
    team2_players = get_players_by_team(match['team2_id'])
    return team1_players + team2_players

def get_players_by_team(team_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM players WHERE team_id = ?", (team_id,))
    players = c.fetchall()
    conn.close()
    return [{'id': p[0], 'name': p[1]} for p in players]

def get_match_odds(match_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("""
        SELECT mo.id, mo.odds_value, mo.player_id, ot.name as template_name, ot.description, oc.name as category_name
        FROM match_odds mo
        JOIN odds_templates ot ON mo.template_id = ot.id
        JOIN odds_categories oc ON ot.category_id = oc.id
        WHERE mo.match_id = ?
    """, (match_id,))
    odds = c.fetchall()
    conn.close()
    return [{k: item[i] for i, k in enumerate(['id', 'odds_value', 'player_id', 'template_name', 'description', 'category_name'])} for item in odds]

def get_odds_templates(category_id=None):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    if category_id:
        c.execute("SELECT * FROM odds_templates WHERE category_id = ?", (category_id,))
    else:
        c.execute("SELECT * FROM odds_templates")
    templates = c.fetchall()
    conn.close()
    return [{k: item[i] for i, k in enumerate(['id', 'category_id', 'name', 'description', 'bet_type', 'default_odds', 'requires_player'])} for item in templates]

def get_odds_categories():
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT * FROM odds_categories")
    categories = c.fetchall()
    conn.close()
    return [{k: item[i] for i, k in enumerate(['id', 'name', 'description'])} for item in categories]

def get_custom_bets(match_id=None):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    if match_id:
        c.execute("SELECT * FROM custom_bets WHERE match_id = ?", (match_id,))
    else:
        c.execute("SELECT * FROM custom_bets")
    custom_bets = c.fetchall()
    conn.close()
    return [{k: item[i] for i, k in enumerate(['id', 'match_id', 'description', 'odds', 'player_id', 'status'])} for item in custom_bets]

def get_custom_bet_proposals(status='pending'):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("""
        SELECT cbp.id, cbp.user_id, u.username, cbp.match_id, cbp.description, cbp.proposed_odds, cbp.status, cbp.created_at
        FROM custom_bet_proposals cbp
        JOIN users u ON cbp.user_id = u.username
        WHERE cbp.status = ?
    """, (status,))
    proposals = c.fetchall()
    conn.close()
    return [{k: item[i] for i, k in enumerate(['id', 'user_id', 'username', 'match_id', 'description', 'proposed_odds', 'status', 'created_at'])} for item in proposals]


# --- Streamlit App --- #

if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.is_admin = False

def login_page():
    st.title("Bem-vindo ao GuimaBet!")
    
    tab1, tab2 = st.tabs(["Entrar", "Registrar"])
    
    with tab1:
        st.subheader("Entrar na sua conta")
        
        with st.form("login_form", clear_on_submit=True):
            username = st.text_input("Usuário", key="login_username")
            password = st.text_input("Senha", type="password", key="login_password")  
            submit = st.form_submit_button("Entrar")

            
            if submit:
                user = login(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.is_admin = bool(user[3])
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos")
    
    with tab2:
        st.subheader("Criar nova conta")
        
        with st.form("register_form", clear_on_submit=True):
            new_username = st.text_input("Novo Usuário", key="register_username")
            new_password = st.text_input("Nova Senha", type="password", key="register_password")
            register_submit = st.form_submit_button("Registrar")

            
            if register_submit:
                if register_user(new_username, new_password):
                    st.success("Conta criada com sucesso! Faça login para continuar.")
                else:
                    st.error("Nome de usuário já existe.")

def user_dashboard():
    st.sidebar.title(f"Olá, {st.session_state.username}!")
    
    if st.sidebar.button("Logout", key="user_logout_button"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.rerun()

    if st.session_state.is_admin:
        st.sidebar.subheader("Opções de Administrador")
        if st.sidebar.button("Painel Admin", key="admin_panel_button"):
            st.session_state.page = "admin_panel"
            st.rerun()

    st.title("Dashboard do Usuário")
    st.write(f"Seus pontos: {get_user_points(st.session_state.username)}")

    # Main content area
    if st.session_state.is_admin and st.session_state.get('page') == 'admin_panel':
        admin_panel_enhanced.main_admin_panel_content()
    else:
        # Conteúdo normal do usuário
        st.header("Partidas Disponíveis")
        matches = get_upcoming_matches()
        if matches:
            for match in matches:
                team1 = get_team_name(match['team1_id'])
                team2 = get_team_name(match['team2_id'])
                st.subheader(f"{team1} vs {team2} - {match['date']} {match['time']}")
                
                odds = get_match_odds(match['id'])
                if odds:
                    with st.form(f"bet_form_{match['id']}"):
                        st.write("Odds disponíveis:")
                        selected_odd_id = st.selectbox(
                            "Selecione sua aposta:",
                            options=[o['id'] for o in odds],
                            format_func=lambda x: f"{next(item for item in odds if item['id'] == x)['template_name']} (Odds: {next(item for item in odds if item['id'] == x)['odds_value']})",
                            key=f"odd_select_{match['id']}"
                        )
                        
                        amount = st.number_input("Valor da Aposta:", min_value=1, value=10, key=f"bet_amount_{match['id']}")
                        
                        bet_submit = st.form_submit_button("Fazer Aposta", key=f"place_bet_button_{match['id']}")
                        
                        if bet_submit:
                            selected_odd = next(item for item in odds if item['id'] == selected_odd_id)
                            user_points = get_user_points(st.session_state.username)
                            
                            if user_points >= amount:
                                # Placeholder for placing bet logic
                                # In a real app, this would interact with a betting system
                                st.success(f"Aposta de {amount} pontos em {selected_odd['template_name']} realizada com sucesso!")
                                update_user_points(st.session_state.username, user_points - amount)
                                st.rerun()
                            else:
                                st.error("Pontos insuficientes.")
                else:
                    st.info("Odds ainda não disponíveis para esta partida.")
        else:
            st.info("Nenhuma partida futura disponível no momento.")

        st.header("Minhas Apostas")
        # Placeholder for displaying user's bets
        st.write("Suas apostas aparecerão aqui.")

def main():
    init_db()
    if not st.session_state.logged_in:
        login_page()
    else:
        user_dashboard()

if __name__ == "__main__":
    main()


