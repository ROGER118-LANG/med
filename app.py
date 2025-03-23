import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import os
import random

# Initialize the database if it doesn't exist
def init_db():
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Create users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT,
        points INTEGER,
        is_admin INTEGER
    )
    ''')
    
    # Create teams table
    c.execute('''
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT
    )
    ''')
    
    # Create players table
    c.execute('''
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        team_id INTEGER,
        FOREIGN KEY (team_id) REFERENCES teams (id)
    )
    ''')
    
    # Create matches table
    c.execute('''
    CREATE TABLE IF NOT EXISTS matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team1_id INTEGER,
        team2_id INTEGER,
        date TEXT,
        time TEXT,
        status TEXT DEFAULT 'upcoming',
        team1_score INTEGER DEFAULT NULL,
        team2_score INTEGER DEFAULT NULL,
        FOREIGN KEY (team1_id) REFERENCES teams (id),
        FOREIGN KEY (team2_id) REFERENCES teams (id)
    )
    ''')
    
    # Create odds table
    c.execute('''
    CREATE TABLE IF NOT EXISTS odds (
        match_id INTEGER,
        team1_win REAL,
        draw REAL,
        team2_win REAL,
        FOREIGN KEY (match_id) REFERENCES matches (id)
    )
    ''')
    
    # Create bets table
    c.execute('''
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        match_id INTEGER,
        bet_type TEXT,
        amount INTEGER,
        status TEXT DEFAULT 'pending',
        timestamp TEXT,
        custom_bet_id INTEGER DEFAULT NULL,
        player_id INTEGER DEFAULT NULL,
        FOREIGN KEY (user_id) REFERENCES users (username),
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (custom_bet_id) REFERENCES custom_bets (id),
        FOREIGN KEY (player_id) REFERENCES players (id)
    )
    ''')
    
    # Create custom bets table
    c.execute('''
    CREATE TABLE IF NOT EXISTS custom_bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        description TEXT,
        odds REAL,
        player_id INTEGER DEFAULT NULL,
        status TEXT DEFAULT 'pending',
        result TEXT DEFAULT NULL,
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (player_id) REFERENCES players (id)
    )
    ''')
    
    # Insert default admin user if not exists
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        hashed_password = hashlib.sha256("123".encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, points, is_admin) VALUES (?, ?, ?, ?)",
                 ("admin", hashed_password, 1000, 1))
    
    # Insert default teams if not exists
    default_teams = ["Tropa da Sônia", "Cubanos", "Dynamos", "Os Feras", "Gaviões", "Leões do Recreio"]
    for team in default_teams:
        c.execute("SELECT * FROM teams WHERE name = ?", (team,))
        if not c.fetchone():
            c.execute("INSERT INTO teams (name) VALUES (?)", (team,))
    
    conn.commit()
    conn.close()

# Get team name by ID
def get_team_name(team_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT name FROM teams WHERE id = ?", (team_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "Unknown Team"

# Get player name by ID
def get_player_name(player_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT name FROM players WHERE id = ?", (player_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "Unknown Player"

# Login function
def login(username, password):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    return user

# Register function
def register(username, password):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    try:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        c.execute("INSERT INTO users (username, password, points, is_admin) VALUES (?, ?, ?, ?)",
                 (username, hashed_password, 100, 0))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

# Get upcoming matches
def get_upcoming_matches():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
    SELECT m.id, m.team1_id, m.team2_id, m.date, m.time, m.status, m.team1_score, m.team2_score,
           o.team1_win, o.draw, o.team2_win
    FROM matches m
    LEFT JOIN odds o ON m.id = o.match_id
    WHERE m.status = 'upcoming' OR m.status = 'live'
    ORDER BY m.date, m.time
    ''')
    matches = [dict(row) for row in c.fetchall()]
    conn.close()
    return matches

# Get match history
def get_match_history():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
    SELECT m.id, m.team1_id, m.team2_id, m.date, m.time, m.status, m.team1_score, m.team2_score,
           o.team1_win, o.draw, o.team2_win
    FROM matches m
    LEFT JOIN odds o ON m.id = o.match_id
    WHERE m.status = 'completed'
    ORDER BY m.date DESC, m.time DESC
    ''')
    matches = [dict(row) for row in c.fetchall()]
    conn.close()
    return matches

# Get custom bets for a match
def get_custom_bets(match_id=None):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if match_id:
        c.execute('''
        SELECT * FROM custom_bets WHERE match_id = ? AND status = 'pending'
        ''', (match_id,))
    else:
        c.execute('SELECT * FROM custom_bets WHERE status = "pending"')
    
    custom_bets = [dict(row) for row in c.fetchall()]
    conn.close()
    return custom_bets

# Get user bets
def get_user_bets(username):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
    SELECT b.id, b.match_id, b.bet_type, b.amount, b.status, b.timestamp, b.custom_bet_id, b.player_id,
           m.team1_id, m.team2_id, m.date, m.time, m.status as match_status, m.team1_score, m.team2_score
    FROM bets b
    JOIN matches m ON b.match_id = m.id
    WHERE b.user_id = ?
    ORDER BY b.timestamp DESC
    ''', (username,))
    bets = [dict(row) for row in c.fetchall()]
    conn.close()
    return bets

# Place bet function
def place_bet(username, match_id, bet_type, amount, custom_bet_id=None, player_id=None):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Check if user has enough points
    c.execute("SELECT points FROM users WHERE username = ?", (username,))
    user_points = c.fetchone()[0]
    
    if user_points < amount:
        conn.close()
        return False, "Pontos insuficientes"
    
    # Check if match is still open for betting
    c.execute("SELECT status FROM matches WHERE id = ?", (match_id,))
    match_status = c.fetchone()[0]
    
    if match_status != 'upcoming' and match_status != 'live':
        conn.close()
        return False, "Apostas fechadas para este jogo"
    
    # Update user points
    c.execute("UPDATE users SET points = points - ? WHERE username = ?", (amount, username))
    
    # Record the bet
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
    INSERT INTO bets (user_id, match_id, bet_type, amount, status, timestamp, custom_bet_id, player_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (username, match_id, bet_type, amount, 'pending', timestamp, custom_bet_id, player_id))
    
    conn.commit()
    conn.close()
    return True, "Aposta realizada com sucesso!"

# Admin functions
def add_match(team1_id, team2_id, date, time):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute('''
    INSERT INTO matches (team1_id, team2_id, date, time, status)
    VALUES (?, ?, ?, ?, ?)
    ''', (team1_id, team2_id, date, time, 'upcoming'))
    
    match_id = c.lastrowid
    
    # Generate random odds (slightly favoring team1 for this example)
    team1_win = round(random.uniform(1.5, 3.0), 2)
    draw = round(random.uniform(2.0, 4.0), 2)
    team2_win = round(random.uniform(1.8, 3.5), 2)
    
    c.execute('''
    INSERT INTO odds (match_id, team1_win, draw, team2_win)
    VALUES (?, ?, ?, ?)
    ''', (match_id, team1_win, draw, team2_win))
    
    conn.commit()
    conn.close()
    return True

def update_match_result(match_id, team1_score, team2_score):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Update match status and scores
    c.execute('''
    UPDATE matches 
    SET status = 'completed', team1_score = ?, team2_score = ?
    WHERE id = ?
    ''', (team1_score, team2_score, match_id))
    
    # Determine match result
    if team1_score > team2_score:
        result = 'team1_win'
    elif team1_score < team2_score:
        result = 'team2_win'
    else:
        result = 'draw'
    
    # Get all standard bets for this match
    c.execute('''
    SELECT id, user_id, bet_type, amount FROM bets 
    WHERE match_id = ? AND status = 'pending' AND custom_bet_id IS NULL
    ''', (match_id,))
    bets = c.fetchall()
    
    # Get odds for this match
    c.execute('''
    SELECT team1_win, draw, team2_win FROM odds
    WHERE match_id = ?
    ''', (match_id,))
    odds = c.fetchone()
    
    # Process standard bets
    for bet_id, user_id, bet_type, amount in bets:
        if bet_type == result:
            # Winning bet - user gets back stake + winnings based on odds
            odds_value = odds[0] if bet_type == 'team1_win' else odds[1] if bet_type == 'draw' else odds[2]
            winnings = int(amount * odds_value)
            c.execute("UPDATE users SET points = points + ? WHERE username = ?", (winnings + amount, user_id))
            c.execute("UPDATE bets SET status = 'won' WHERE id = ?", (bet_id,))
        else:
            # Losing bet - user already lost stake when placing bet, just update status
            c.execute("UPDATE bets SET status = 'lost' WHERE id = ?", (bet_id,))
    
    conn.commit()
    conn.close()
    return True

def set_match_live(match_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("UPDATE matches SET status = 'live' WHERE id = ?", (match_id,))
    conn.commit()
    conn.close()
    return True

def add_team(name):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO teams (name) VALUES (?)", (name,))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def add_player(name, team_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO players (name, team_id) VALUES (?, ?)", (name, team_id))
        conn.commit()
        conn.close()
        return True
    except:
        conn.close()
        return False

def add_custom_bet(match_id, description, odds, player_id=None):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    try:
        c.execute('''
        INSERT INTO custom_bets (match_id, description, odds, player_id, status)
        VALUES (?, ?, ?, ?, ?)
        ''', (match_id, description, odds, player_id, 'pending'))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(e)
        conn.close()
        return False

def update_custom_bet_result(custom_bet_id, result):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Update custom bet status and result
    c.execute('''
    UPDATE custom_bets 
    SET status = 'completed', result = ?
    WHERE id = ?
    ''', (result, custom_bet_id))
    
    # Get all bets for this custom bet
    c.execute('''
    SELECT id, user_id, amount FROM bets 
    WHERE custom_bet_id = ? AND status = 'pending'
    ''', (custom_bet_id,))
    bets = c.fetchall()
    
    # Get custom bet odds
    c.execute('''
    SELECT odds FROM custom_bets
    WHERE id = ?
    ''', (custom_bet_id,))
    odds = c.fetchone()[0]
    
    # Process bets
    for bet_id, user_id, amount in bets:
        if result == 'yes':
            # Winning bet
            winnings = int(amount * odds)
            c.execute("UPDATE users SET points = points + ? WHERE username = ?", (winnings + amount, user_id))
            c.execute("UPDATE bets SET status = 'won' WHERE id = ?", (bet_id,))
        else:
            # Losing bet
            c.execute("UPDATE bets SET status = 'lost' WHERE id = ?", (bet_id,))
    
    conn.commit()
    conn.close()
    return True

def get_all_teams():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM teams ORDER BY name")
    teams = [dict(row) for row in c.fetchall()]
    conn.close()
    return teams

def get_all_players():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM players ORDER BY name")
    players = [dict(row) for row in c.fetchall()]
    conn.close()
    return players

def get_team_players(team_id):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM players WHERE team_id = ? ORDER BY name", (team_id,))
    players = [dict(row) for row in c.fetchall()]
    conn.close()
    return players

def get_match_players(match_id):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
    SELECT p.* FROM players p
    JOIN matches m ON (p.team_id = m.team1_id OR p.team_id = m.team2_id)
    WHERE m.id = ?
    ORDER BY p.name
    ''', (match_id,))
    players = [dict(row) for row in c.fetchall()]
    conn.close()
    return players

def get_all_users():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT username, points, is_admin FROM users ORDER BY points DESC")
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users

def update_user_points(username, points):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("UPDATE users SET points = ? WHERE username = ?", (points, username))
    conn.commit()
    conn.close()
    return True

def update_user(username, new_username=None, new_points=None, is_admin=None):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    if new_username and new_username != username:
        # Check if new username already exists
        c.execute("SELECT * FROM users WHERE username = ?", (new_username,))
        if c.fetchone():
            conn.close()
            return False, "Nome de usuário já existe."
        
        # Update username in users table
        c.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, username))
        
        # Update username in bets table
        c.execute("UPDATE bets SET user_id = ? WHERE user_id = ?", (new_username, username))
        
        username = new_username
    
    if new_points is not None:
        c.execute("UPDATE users SET points = ? WHERE username = ?", (new_points, username))
    
    if is_admin is not None:
        c.execute("UPDATE users SET is_admin = ? WHERE username = ?", (1 if is_admin else 0, username))
    
    conn.commit()
    conn.close()
    return True, "Usuário atualizado com sucesso!"

def delete_user(username):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Delete user's bets first
    c.execute("DELETE FROM bets WHERE user_id = ?", (username,))
    
    # Delete user
    c.execute("DELETE FROM users WHERE username = ?", (username,))
    
    conn.commit()
    conn.close()
    return True

# Page setup
def main():
    st.set_page_config(
        page_title="GuimaBet",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize database
    init_db()
    
    # Custom CSS
    st.markdown("""
    <style>
    .main {
        background-color: #121212;
        color: white;
    }
    .stButton>button {
        background-color: #4CAF50;
        color: white;
        border: none;
        width: 100%;
    }
    .stTextInput>div>div>input, .stSelectbox>div>div>select {
        color: white;
        background-color: #333;
    }
    .bet-card {
        background-color: #222;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
    }
    .match-card {
        background-color: #1E1E1E;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        border-left: 4px solid #4CAF50;
    }
    .live-indicator {
        background-color: #FF4136;
        color: white;
        padding: 3px 8px;
        border-radius: 5px;
        font-size: 12px;
        animation: blink 1s infinite;
    }
    @keyframes blink {
        0% {opacity: 1;}
        50% {opacity: 0.5;}
        100% {opacity: 1;}
    }
    .odds-button {
        background-color: #2C2C2C;
        border: 1px solid #4CAF50;
        color: white;
        padding: 10px;
        text-align: center;
        border-radius: 5px;
        cursor: pointer;
        margin: 5px;
        transition: all 0.3s;
    }
    .odds-button:hover {
        background-color: #4CAF50;
    }
    .header {
        padding: 20px;
        text-align: center;
        background: linear-gradient(135deg, #4CAF50, #2E7D32);
        color: white;
        font-size: 25px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False
    if 'selected_match' not in st.session_state:
        st.session_state.selected_match = None
    if 'bet_amount' not in st.session_state:
        st.session_state.bet_amount = 10
    if 'bet_type' not in st.session_state:
        st.session_state.bet_type = None
    if 'custom_bet_id' not in st.session_state:
        st.session_state.custom_bet_id = None
    
    # Title
    st.markdown('<div class="header"><h1 style="color: white;"> GuimaBet</h1><p>Apostas no Futebol do Recreio do CIB</p></div>', unsafe_allow_html=True)
    
    # If not logged in, show login/register page
    if not st.session_state.logged_in:
        login_register_page()
    else:
        # Sidebar for navigation
        with st.sidebar:
            st.write(f"Bem-vindo, **{st.session_state.username}**!")
            
            # Get user points
            conn = sqlite3.connect('guimabet.db')
            c = conn.cursor()
            c.execute("SELECT points FROM users WHERE username = ?", (st.session_state.username,))
            user_points = c.fetchone()[0]
            conn.close()
            
            st.write(f"Seus pontos: **{user_points}**")
            
            st.subheader("Menu")
            
            if st.button(" Início"):
                st.session_state.page = "home"
            
            if st.button(" Histórico de Apostas"):
                st.session_state.page = "bet_history"
            
            if st.button(" Ranking"):
                st.session_state.page = "ranking"
            
            if st.session_state.is_admin:
                st.subheader("Admin Menu")
                
                if st.button(" Painel de Admin"):
                    st.session_state.page = "admin"
            
            if st.button(" Sair"):
                st.session_state.logged_in = False
                st.session_state.username = ""
                st.session_state.is_admin = False
                st.experimental_rerun()
        
        # Default page
        if 'page' not in st.session_state:
            st.session_state.page = "home"
        
        # Page router
        if st.session_state.page == "home":
            home_page()
        elif st.session_state.page == "bet_history":
            bet_history_page()
        elif st.session_state.page == "ranking":
            ranking_page()
        elif st.session_state.page == "admin" and st.session_state.is_admin:
            admin_page()

# Login/Register page
def login_register_page():
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Login")
        login_username = st.text_input("Usuário", key="login_username")
        login_password = st.text_input("Senha", type="password", key="login_password")
        
        if st.button("Entrar"):
            if not login_username or not login_password:
                st.error("Por favor, preencha todos os campos.")
            else:
                user = login(login_username, login_password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = login_username
                    st.session_state.is_admin = (user[3] == 1)  # Check if user is admin
                    st.experimental_rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
    
    with col2:
        st.subheader("Registrar")
        reg_username = st.text_input("Usuário", key="reg_username")
        reg_password = st.text_input("Senha", type="password", key="reg_password")
        reg_password_confirm = st.text_input("Confirmar Senha", type="password", key="reg_password_confirm")
        
        if st.button("Registrar"):
            if not reg_username or not reg_password or not reg_password_confirm:
                st.error("Por favor, preencha todos os campos.")
            elif reg_password != reg_password_confirm:
                st.error("As senhas não coincidem.")
            else:
                if register(reg_username, reg_password):
                    st.success("Registro bem-sucedido! Você pode fazer login agora.")
                else:
                    st.error("Nome de usuário já existe.")

# Home page - Upcoming matches and betting
def home_page():
    st.subheader("Jogos Disponíveis para Apostas")
    
    upcoming_matches = get_upcoming_matches()
    
    if not upcoming_matches:
        st.info("Não há jogos programados no momento.")
    else:
        for match in upcoming_matches:
            team1 = get_team_name(match['team1_id'])
            team2 = get_team_name(match['team2_id'])
            
            with st.container():
                st.markdown(f"""
                <div class="match-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3>{team1} vs {team2}</h3>
                            <p>Data: {match['date']} • Hora: {match['time']}</p>
                        </div>
                        <div>
                            {'<span class="live-indicator">AO VIVO</span>' if match['status'] == 'live' else ''}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if st.button(f"{team1} Vence (Odds: {match['team1_win']})", key=f"team1_{match['id']}"):
                        st.session_state.selected_match = match
                        st.session_state.bet_type = "team1_win"
                
                with col2:
                    if st.button(f"Empate (Odds: {match['draw']})", key=f"draw_{match['id']}"):
                        st.session_state.selected_match = match
                        st.session_state.bet_type = "draw"
                
                with col3:
                    if st.button(f"{team2} Vence (Odds: {match['team2_win']})", key=f"team2_{match['id']}"):
                        st.session_state.selected_match = match
                        st.session_state.bet_type = "team2_win"
                
                # Custom bets for this match
                custom_bets = get_custom_bets(match['id'])
                if custom_bets:
                    st.write("Apostas Personalizadas:")
                    for custom_bet in custom_bets:
                        player_info = ""
                        if custom_bet['player_id']:
                            player_info = f" - {get_player_name(custom_bet['player_id'])}"
                        
                        if st.button(f"{custom_bet['description']}{player_info} (Odds: {custom_bet['odds']})", key=f"custom_{custom_bet['id']}"):
                            st.session_state.selected_match = match
                            st.session_state.bet_type = "custom"
                            st.session_state.custom_bet_id = custom_bet['id']
        
        # If a match is selected, show betting form
        if st.session_state.selected_match:
            match = st.session_state.selected_match
            team1 = get_team_name(match['team1_id'])
            team2 = get_team_name(match['team2_id'])
            
            st.markdown("---")
            st.subheader("Fazer Aposta")
            
            if st.session_state.bet_type == "team1_win":
                bet_text = f"Aposta: {team1} vence"
                odds = match['team1_win']
            elif st.session_state.bet_type == "draw":
                bet_text = "Aposta: Empate"
                odds = match['draw']
            elif st.session_state.bet_type == "team2_win":
                bet_text = f"Aposta: {team2} vence"
                odds = match['team2_win']
            else:  # Custom bet
                custom_bet = next((cb for cb in get_custom_bets() if cb['id'] == st.session_state.custom_bet_id), None)
                if custom_bet:
                    bet_description = custom_bet['description']
                    player_info = ""
                    if custom_bet['player_id']:
                        player_info = f" - {get_player_name(custom_bet['player_id'])}"
                    
                    bet_text = f"Aposta Personalizada: {bet_description}{player_info}"
                    odds = custom_bet['odds']
                else:
                    st.error("Aposta personalizada não encontrada.")
                    st.session_state.selected_match = None
                    st.session_state.bet_type = None
                    st.session_state.custom_bet_id = None
                    st.experimental_rerun()
            
            st.write(f"{team1} vs {team2}")
            st.write(bet_text)
            st.write(f"Odds: {odds}")
            
            # Get user points
            conn = sqlite3.connect('guimabet.db')
            c = conn.cursor()
            c.execute("SELECT points FROM users WHERE username = ?", (st.session_state.username,))
            user_points = c.fetchone()[0]
            conn.close()
            
            st.write(f"Seus pontos: {user_points}")
            
            amount = st.number_input("Valor da aposta", min_value=10, max_value=user_points, value=10, step=10)
            potential_win = int(amount * odds)
            
            st.write(f"Ganho potencial: {potential_win} pontos")
            
            if st.button("Confirmar Aposta"):
                if st.session_state.bet_type == "custom":
                    success, message = place_bet(
                        st.session_state.username, 
                        match['id'], 
                        st.session_state.bet_type, 
                        amount, 
                        st.session_state.custom_bet_id,
                        custom_bet.get('player_id')
                    )
                else:
                    success, message = place_bet(st.session_state.username, match['id'], st.session_state.bet_type, amount)
                
                if success:
                    st.success(message)
                    st.session_state.selected_match = None
                    st.session_state.bet_type = None
                    st.session_state.custom_bet_id = None
                    st.experimental_rerun()
                else:
                    st.error(message)
            
            if st.button("Cancelar"):
                st.session_state.selected_match = None
                st.session_state.bet_type = None
                st.session_state.custom_bet_id = None
                st.experimental_rerun()

# Bet history page
def bet_history_page():
    st.subheader("Seu Histórico de Apostas")
    
    bets = get_user_bets(st.session_state.username)
    
    if not bets:
        st.info("Você ainda não fez nenhuma aposta.")
    else:
        for bet in bets:
            team1 = get_team_name(bet['team1_id'])
            team2 = get_team_name(bet['team2_id'])
            
            # Determine bet description
            if bet['custom_bet_id']:
                conn = sqlite3.connect('guimabet.db')
                c = conn.cursor()
                c.execute("SELECT description, player_id FROM custom_bets WHERE id = ?", (bet['custom_bet_id'],))
                custom_bet = c.fetchone()
                conn.close()
                
                if custom_bet:
                    bet_description = custom_bet['description']
                    if custom_bet['player_id']:
                        bet_description += f" - {get_player_name(custom_bet['player_id'])}"
                else:
                    bet_description = "Aposta Personalizada"
            else:
                if bet['bet_type'] == 'team1_win':
                    bet_description = f"Vitória de {team1}"
                elif bet['bet_type'] == 'team2_win':
                    bet_description = f"Vitória de {team2}"
                else:
                    bet_description = "Empate"
            
            # Determine status text and color
            if bet['status'] == 'pending':
                status_text = "Pendente"
                status_color = "orange"
            elif bet['status'] == 'won':
                status_text = "Ganhou"
                status_color = "green"
            else:
                status_text = "Perdeu"
                status_color = "red"
            
            # Format match result if available
            match_result = ""
            if bet['match_status'] == 'completed':
                match_result = f"Resultado: {team1} {bet['team1_score']} x {bet['team2_score']} {team2}"
            
            st.markdown(f"""
            <div class="bet-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <h4>{team1} vs {team2}</h4>
                        <p>Data: {bet['date']} • Aposta: {bet_description}</p>
                        <p>Valor: {bet['amount']} pontos • Data da aposta: {bet['timestamp']}</p>
                        <p>{match_result}</p>
                    </div>
                    <div>
                        <span style="background-color: {status_color}; color: white; padding: 5px 10px; border-radius: 5px;">{status_text}</span>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)

# Ranking page
def ranking_page():
    st.subheader("Ranking de Usuários")
    
    users = get_all_users()
    
    # Create a pandas DataFrame
    df = pd.DataFrame(users)
    df.columns = ['Usuário', 'Pontos', 'Admin']
    df = df.drop(columns=['Admin'])
    
    # Add rank column
    df.insert(0, 'Posição', range(1, len(df) + 1))
    
    st.table(df)

# Admin page
def admin_page():
    st.subheader("Painel de Administração")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Gerenciar Jogos", "Adicionar Jogos", "Gerenciar Usuários", "Jogadores", "Times"])
    
    with tab1:
        st.subheader("Gerenciar Jogos")
        
        upcoming_matches = get_upcoming_matches()
        completed_matches = get_match_history()
        
        st.write("Jogos Próximos e Ao Vivo")
        if not upcoming_matches:
            st.info("Não há jogos próximos.")
        else:
            for match in upcoming_matches:
                team1 = get_team_name(match['team1_id'])
                team2 = get_team_name(match['team2_id'])
                
                with st.container():
                    st.markdown(f"""
                    <div class="match-card">
                        <h4>{team1} vs {team2}</h4>
                        <p>Data: {match['date']} • Hora: {match['time']}</p>
                        <p>Status: {match['status']}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if match['status'] == 'upcoming':
                            if st.button("Definir como Ao Vivo", key=f"live_{match['id']}"):
                                set_match_live(match['id'])
                                st.success("Jogo definido como Ao Vivo!")
                                st.experimental_rerun()
                    
                    with col2:
                        if st.button("Atualizar Resultado", key=f"result_{match['id']}"):
                            st.session_state.update_match = match['id']
                    
                    if 'update_match' in st.session_state and st.session_state.update_match == match['id']:
                        st.subheader("Atualizar Resultado")
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            team1_score = st.number_input(f"Placar {team1}", min_value=0, value=0, key=f"score1_{match['id']}")
                        
                        with col2:
                            team2_score = st.number_input(f"Placar {team2}", min_value=0, value=0, key=f"score2_{match['id']}")
                        
                        if st.button("Salvar Resultado"):
                            update_match_result(match['id'], team1_score, team2_score)
                            st.success("Resultado atualizado com sucesso!")
                            if 'update_match' in st.session_state:
                                del st.session_state.update_match
                            st.experimental_rerun()
                        
                        if st.button("Cancelar", key=f"cancel_update_{match['id']}"):
                            if 'update_match' in st.session_state:
                                del st.session_state.update_match
                            st.experimental_rerun()
        
        st.markdown("---")
        st.write("Jogos Finalizados")
        
        if not completed_matches:
            st.info("Não há jogos finalizados.")
        else:
            for match in completed_matches:
                team1 = get_team_name(match['team1_id'])
                team2 = get_team_name(match['team2_id'])
                
                st.markdown(f"""
                <div class="match-card">
                    <h4>{team1} {match['team1_score']} x {match['team2_score']} {team2}</h4>
                    <p>Data: {match['date']} • Hora: {match['time']}</p>
                </div>
                """, unsafe_allow_html=True)
    
    with tab2:
        st.subheader("Adicionar Novo Jogo")
        
        teams = get_all_teams()
        team_options = {team['id']: team['name'] for team in teams}
        
        col1, col2 = st.columns(2)
        
        with col1:
            team1_id = st.selectbox("Time 1", options=list(team_options.keys()), format_func=lambda x: team_options[x], key="add_team1")
        
        with col2:
            team2_id = st.selectbox("Time 2", options=list(team_options.keys()), format_func=lambda x: team_options[x], key="add_team2")
        
        col1, col2 = st.columns(2)
        
        with col1:
            match_date = st.date_input("Data", key="add_date")
        
        with col2:
            match_time = st.time_input("Hora", key="add_time")
        
        if st.button("Adicionar Jogo"):
            if team1_id == team2_id:
                st.error("Por favor, selecione times diferentes.")
            else:
                date_str = match_date.strftime("%Y-%m-%d")
                time_str = match_time.strftime("%H:%M")
                add_match(team1_id, team2_id, date_str, time_str)
                st.success("Jogo adicionado com sucesso!")
    
    with tab3:
        st.subheader("Gerenciar Usuários")
        
        users = get_all_users()
        
        for user in users:
            with st.expander(f"Usuário: {user['username']}", expanded=False):
                with st.form(key=f"user_form_{user['username']}"):
                    new_username = st.text_input("Nome de Usuário", value=user['username'])
                    new_points = st.number_input("Pontos", min_value=0, value=user['points'], step=10)
                    is_admin = st.checkbox("Administrador", value=user['is_admin'] == 1)
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        update_button = st.form_submit_button("Atualizar Usuário")
                    with col2:
                        delete_button = st.form_submit_button("Excluir Usuário", help="Esta ação não pode ser desfeita")
                
                if update_button:
                    success, message = update_user(user['username'], new_username, new_points, is_admin)
                    if success:
                        st.success(message)
                        st.experimental_rerun()
                    else:
                        st.error(message)
                
                if delete_button:
                    if user['username'] == 'admin':
                        st.error("Não é possível excluir o usuário administrador padrão.")
                    else:
                        if st.button(f"Confirmar exclusão de {user['username']}?", key=f"confirm_delete_{user['username']}"):
                            delete_user(user['username'])
                            st.success(f"Usuário {user['username']} excluído com sucesso!")
                            st.experimental_rerun()
        
        st.markdown("---")
        st.subheader("Adicionar Novo Usuário")
        
        with st.form(key="add_user_form"):
            new_user_username = st.text_input("Nome de Usuário", key="new_user_username")
            new_user_password = st.text_input("Senha", type="password", key="new_user_password")
            new_user_points = st.number_input("Pontos Iniciais", min_value=0, value=100, step=10, key="new_user_points")
            new_user_admin = st.checkbox("Administrador", value=False, key="new_user_admin")
            
            submit_button = st.form_submit_button("Adicionar Usuário")
        
        if submit_button:
            if not new_user_username or not new_user_password:
                st.error("Por favor, preencha todos os campos.")
            else:
                conn = sqlite3.connect('guimabet.db')
                c = conn.cursor()
                try:
                    hashed_password = hashlib.sha256(new_user_password.encode()).hexdigest()
                    c.execute("INSERT INTO users (username, password, points, is_admin) VALUES (?, ?, ?, ?)",
                             (new_user_username, hashed_password, new_user_points, 1 if new_user_admin else 0))
                    conn.commit()
                    conn.close()
                    st.success("Usuário adicionado com sucesso!")
                    st.experimental_rerun()
                except:
                    conn.close()
                    st.error("Nome de usuário já existe.")
    
    with tab4:
        st.subheader("Jogadores")
        
        st.write("Adicionar Novo Jogador")
        
        player_name = st.text_input("Nome do Jogador", key="player_name")
        
        teams = get_all_teams()
        team_options = {team['id']: team['name'] for team in teams}
        
        player_team_id = st.selectbox("Time", options=list(team_options.keys()), format_func=lambda x: team_options[x], key="player_team")
        
        if st.button("Adicionar Jogador"):
            if not player_name or not player_team_id:
                st.error("Por favor, preencha todos os campos.")
            else:
                if add_player(player_name, player_team_id):
                    st.success("Jogador adicionado com sucesso!")
                    st.experimental_rerun()
                else:
                    st.error("Erro ao adicionar jogador.")
        
        st.markdown("---")
        
        st.write("Jogadores Cadastrados")
        
        players = get_all_players()
        if not players:
            st.info("Não há jogadores cadastrados.")
        else:
            df = pd.DataFrame([(player['name'], get_team_name(player['team_id'])) for player in players], columns=['Nome', 'Time'])
            st.table(df)
    
    with tab5:
        st.subheader("Times")
        
        st.write("Adicionar Novo Time")
        
        team_name = st.text_input("Nome do Time", key="team_name")
        
        if st.button("Adicionar Time"):
            if not team_name:
                st.error("Por favor, insira um nome para o time.")
            else:
                if add_team(team_name):
                    st.success("Time adicionado com sucesso!")
                    st.experimental_rerun()
                else:
                    st.error("Erro ao adicionar time.")
        
        st.markdown("---")
        
        st.write("Times Cadastrados")
        
        teams = get_all_teams()
        if not teams:
            st.info("Não há times cadastrados.")
        else:
            for team in teams:
                st.write(f"• {team['name']}")

if __name__ == "__main__":
    main()
