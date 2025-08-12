import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib

def init_db():
    """Inicializa o banco de dados com todas as tabelas necessárias"""
    conn = sqlite3.connect('primabet.db')
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
        status TEXT DEFAULT 'active',
        created_by TEXT,
        created_at TEXT,
        result TEXT DEFAULT 'pending',
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
        status TEXT DEFAULT 'pending',
        admin_response TEXT,
        created_at TEXT,
        reviewed_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users (username),
        FOREIGN KEY (match_id) REFERENCES matches (id)
    )
    ''')

    # Tabela principal de apostas dos usuários
    c.execute('''
    CREATE TABLE IF NOT EXISTS bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        match_id INTEGER,
        amount REAL,
        odds REAL,
        status TEXT DEFAULT 'pending',
        timestamp TEXT,
        match_odds_id INTEGER,
        custom_bet_id INTEGER,
        bet_type TEXT DEFAULT 'regular',
        bet_description TEXT,
        FOREIGN KEY (user_id) REFERENCES users (username),
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (match_odds_id) REFERENCES match_odds (id),
        FOREIGN KEY (custom_bet_id) REFERENCES custom_bets (id)
    )
    ''')

    # Categorias de odds
    c.execute("INSERT OR IGNORE INTO odds_categories (name, description) VALUES ('Resultado', 'Vitória, Empate ou Derrota')")
    c.execute("INSERT OR IGNORE INTO odds_categories (name, description) VALUES ('Gols', 'Apostas relacionadas a gols')")
    c.execute("INSERT OR IGNORE INTO odds_categories (name, description) VALUES ('Jogadores', 'Apostas em desempenho de jogadores')")
    
    # Templates de odds
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (1, 'Vitória Time Casa', 'Time da casa vence', 'home_win', 2.5, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (1, 'Empate', 'Partida termina empatada', 'draw', 3.2, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (1, 'Vitória Time Visitante', 'Time visitante vence', 'away_win', 2.8, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (2, 'Mais de 2.5 Gols', 'Partida com mais de 2.5 gols', 'over_2_5', 1.8, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (3, 'Jogador marca gol', 'Jogador específico marca gol', 'player_goal', 3.5, 1)")
    
    # Admin user
    admin_password = hashlib.sha256("admin123".encode()).hexdigest()
    c.execute("INSERT OR IGNORE INTO users (username, password, points, is_admin) VALUES ('admin', ?, 10000, 1)", (admin_password,))

    conn.commit()
    conn.close()

def db_connect():
    """Conecta ao banco de dados"""
    conn = sqlite3.connect('primabet.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_user(username, password):
    """Faz login do usuário"""
    conn = db_connect()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password)).fetchone()
    conn.close()
    return user

def register_user(username, password):
    """Registra um novo usuário"""
    if not username or not password: 
        return False, "Usuário e senha não podem ser vazios."
    conn = db_connect()
    try:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        return True, "Conta criada com sucesso! Faça o login."
    except sqlite3.IntegrityError: 
        return False, "Este nome de usuário já existe."
    finally: 
        conn.close()

def get_user_points(username):
    """Obtém os pontos do usuário"""
    conn = db_connect()
    points = conn.execute("SELECT points FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return points['points'] if points else 0

def update_user_points(username, points):
    """Atualiza os pontos do usuário"""
    conn = db_connect()
    conn.execute("UPDATE users SET points = ? WHERE username = ?", (points, username))
    conn.commit()
    conn.close()

def get_team_name(team_id):
    """Obtém o nome do time"""
    conn = db_connect()
    name = conn.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
    conn.close()
    return name['name'] if name else "Desconhecido"

def get_all_teams():
    """Obtém todos os times"""
    conn = db_connect()
    teams = [dict(row) for row in conn.execute("SELECT id, name FROM teams").fetchall()]
    conn.close()
    return teams

def get_player_name(player_id):
    """Obtém o nome do jogador"""
    conn = db_connect()
    name = conn.execute("SELECT name FROM players WHERE id = ?", (player_id,)).fetchone()
    conn.close()
    return name['name'] if name else "Desconhecido"

def get_all_players():
    """Obtém todos os jogadores"""
    conn = db_connect()
    players = [dict(row) for row in conn.execute("SELECT id, name, team_id FROM players").fetchall()]
    conn.close()
    return players

def get_players_by_team(team_id):
    """Obtém jogadores de um time específico"""
    conn = db_connect()
    players = [dict(row) for row in conn.execute("SELECT id, name FROM players WHERE team_id = ?", (team_id,)).fetchall()]
    conn.close()
    return players

def get_upcoming_matches_with_names():
    """Obtém partidas futuras com nomes dos times"""
    conn = db_connect()
    matches = [dict(row) for row in conn.execute("""
        SELECT m.id, m.date, m.time, t1.name as team1_name, t2.name as team2_name,
               m.team1_id, m.team2_id, m.status
        FROM matches m 
        JOIN teams t1 ON m.team1_id = t1.id 
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.status = 'upcoming' ORDER BY m.date, m.time
    """).fetchall()]
    conn.close()
    return matches

def get_match_by_id(match_id):
    """Obtém uma partida pelo ID"""
    conn = db_connect()
    match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
    conn.close()
    return dict(match) if match else None

def get_match_odds(match_id):
    """Obtém odds de uma partida"""
    conn = db_connect()
    odds = [dict(row) for row in conn.execute("""
        SELECT mo.id, mo.odds_value, ot.name as template_name, ot.description, 
               mo.player_id, oc.name as category_name
        FROM match_odds mo 
        JOIN odds_templates ot ON mo.template_id = ot.id
        JOIN odds_categories oc ON ot.category_id = oc.id
        WHERE mo.match_id = ? AND mo.is_active = 1
    """, (match_id,)).fetchall()]
    conn.close()
    return odds

def get_custom_bets(match_id):
    """Obtém apostas personalizadas de uma partida"""
    conn = db_connect()
    custom_bets = [dict(row) for row in conn.execute("""
        SELECT cb.id, cb.description, cb.odds, cb.player_id, cb.status
        FROM custom_bets cb
        WHERE cb.match_id = ? AND cb.status = 'active'
    """, (match_id,)).fetchall()]
    conn.close()
    return custom_bets

def add_custom_bet(match_id, description, odds, player_id=None, created_by='admin'):
    """Adiciona uma aposta personalizada"""
    conn = db_connect()
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO custom_bets (match_id, description, odds, player_id, created_by, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (match_id, description, odds, player_id, created_by, now))
        conn.commit()
        return True, "Aposta personalizada criada com sucesso!"
    except Exception as e:
        return False, f"Erro ao criar aposta personalizada: {e}"
    finally:
        conn.close()

def place_bet(username, match_id, match_odds_id=None, custom_bet_id=None, amount=None):
    """Realiza uma aposta"""
    if amount is None or amount <= 0: 
        return False, "O valor da aposta deve ser maior que zero."
    
    conn = db_connect()
    try:
        user_row = conn.execute("SELECT points FROM users WHERE username = ?", (username,)).fetchone()
        if user_row is None: 
            return False, "Erro: Usuário não encontrado."
        
        user_points = user_row['points']
        if user_points < amount: 
            return False, "Pontos insuficientes."
        
        if match_odds_id:
            # Aposta regular
            odd_info = conn.execute("SELECT odds_value FROM match_odds WHERE id = ?", (match_odds_id,)).fetchone()
            if not odd_info: 
                return False, "Odd não encontrada."
            odds_value = odd_info['odds_value']
            bet_type = 'regular'
            bet_description = None
        elif custom_bet_id:
            # Aposta personalizada
            custom_bet_info = conn.execute("SELECT odds, description FROM custom_bets WHERE id = ? AND status = 'active'", (custom_bet_id,)).fetchone()
            if not custom_bet_info:
                return False, "Aposta personalizada não encontrada ou inativa."
            odds_value = custom_bet_info['odds']
            bet_type = 'custom'
            bet_description = custom_bet_info['description']
        else:
            return False, "Tipo de aposta inválido."
        
        conn.execute("UPDATE users SET points = points - ? WHERE username = ?", (amount, username))
        conn.execute("""
            INSERT INTO bets (user_id, match_id, amount, odds, match_odds_id, custom_bet_id, 
                             bet_type, bet_description, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (username, match_id, amount, odds_value, match_odds_id, custom_bet_id, 
              bet_type, bet_description, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        return True, "Aposta realizada com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, f"Erro interno ao realizar aposta: {e}"
    finally: 
        conn.close()

def get_user_bets(username):
    """Busca o histórico de apostas de um usuário"""
    conn = db_connect()
    bets = [dict(row) for row in conn.execute("""
        SELECT 
            b.amount, b.odds, b.status, b.timestamp, b.bet_type, b.bet_description,
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

def get_odds_categories():
    """Obtém todas as categorias de odds"""
    conn = db_connect()
    categories = [dict(row) for row in conn.execute("SELECT * FROM odds_categories").fetchall()]
    conn.close()
    return categories

def get_odds_templates(category_id=None):
    """Obtém templates de odds"""
    conn = db_connect()
    if category_id:
        templates = [dict(row) for row in conn.execute("SELECT * FROM odds_templates WHERE category_id = ?", (category_id,)).fetchall()]
    else:
        templates = [dict(row) for row in conn.execute("SELECT * FROM odds_templates").fetchall()]
    conn.close()
    return templates

def add_team(name):
    """Adiciona um novo time"""
    conn = db_connect()
    try:
        conn.execute("INSERT INTO teams (name) VALUES (?)", (name,))
        conn.commit()
        return True, "Time adicionado com sucesso!"
    except sqlite3.IntegrityError:
        return False, "Este time já existe."
    finally:
        conn.close()

def add_player(name, team_id):
    """Adiciona um novo jogador"""
    conn = db_connect()
    try:
        conn.execute("INSERT INTO players (name, team_id) VALUES (?, ?)", (name, team_id))
        conn.commit()
        return True, "Jogador adicionado com sucesso!"
    except Exception as e:
        return False, f"Erro ao adicionar jogador: {e}"
    finally:
        conn.close()

def add_match(team1_id, team2_id, date, time):
    """Adiciona uma nova partida"""
    conn = db_connect()
    try:
        conn.execute("INSERT INTO matches (team1_id, team2_id, date, time) VALUES (?, ?, ?, ?)", 
                    (team1_id, team2_id, date, time))
        match_id = conn.lastrowid
        
        # Adicionar odds padrão para a partida
        templates = get_odds_templates()
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        for template in templates:
            if not template['requires_player']:
                conn.execute("""
                    INSERT INTO match_odds (match_id, template_id, odds_value, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (match_id, template['id'], template['default_odds'], now, now))
        
        conn.commit()
        return True, "Partida adicionada com sucesso!"
    except Exception as e:
        return False, f"Erro ao adicionar partida: {e}"
    finally:
        conn.close()

# INTERFACE DO STREAMLIT
def main():
    st.set_page_config(
        page_title="PrimaBet - Casa de Apostas",
        page_icon="⚽",
        layout="wide"
    )
    
    # Inicializar banco de dados
    init_db()
    
    # Inicializar session state
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
    if 'username' not in st.session_state:
        st.session_state.username = ""
    if 'is_admin' not in st.session_state:
        st.session_state.is_admin = False
    
    # Título principal
    st.title("⚽ PrimaBet - Casa de Apostas")
    
    # Se não estiver logado, mostrar tela de login/registro
    if not st.session_state.logged_in:
        show_login_page()
    else:
        # Mostrar interface principal
        show_main_interface()

def show_login_page():
    """Mostra a página de login/registro"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Acesso ao Sistema")
        
        tab1, tab2 = st.tabs(["Login", "Registro"])
        
        with tab1:
            with st.form("login_form"):
                st.markdown("#### Fazer Login")
                username = st.text_input("Usuário")
                password = st.text_input("Senha", type="password")
                submit_login = st.form_submit_button("Entrar")
                
                if submit_login:
                    if username and password:
                        user = login_user(username, password)
                        if user:
                            st.session_state.logged_in = True
                            st.session_state.username = username
                            st.session_state.is_admin = bool(user['is_admin'])
                            st.success("Login realizado com sucesso!")
                            st.rerun()
                        else:
                            st.error("Usuário ou senha incorretos!")
                    else:
                        st.error("Por favor, preencha todos os campos!")
        
        with tab2:
            with st.form("register_form"):
                st.markdown("#### Criar Conta")
                new_username = st.text_input("Novo Usuário")
                new_password = st.text_input("Nova Senha", type="password")
                confirm_password = st.text_input("Confirmar Senha", type="password")
                submit_register = st.form_submit_button("Registrar")
                
                if submit_register:
                    if new_username and new_password and confirm_password:
                        if new_password == confirm_password:
                            success, message = register_user(new_username, new_password)
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
                        else:
                            st.error("As senhas não coincidem!")
                    else:
                        st.error("Por favor, preencha todos os campos!")
        
        # Informações de demo
        st.markdown("---")
        st.info("**Demo:** Use admin/admin123 para acessar como administrador")

def show_main_interface():
    """Mostra a interface principal do sistema"""
    # Sidebar com informações do usuário
    with st.sidebar:
        st.markdown(f"### 👤 Bem-vindo, {st.session_state.username}!")
        
        # Mostrar pontos do usuário
        user_points = get_user_points(st.session_state.username)
        st.metric("💰 Seus Pontos", f"{user_points:,.0f}")
        
        st.markdown("---")
        
        # Menu de navegação
        if st.session_state.is_admin:
            menu_options = ["🏠 Dashboard", "🎯 Apostas", "📊 Histórico", "⚙️ Admin"]
        else:
            menu_options = ["🏠 Dashboard", "🎯 Apostas", "📊 Histórico"]
        
        selected_page = st.selectbox("Navegação", menu_options)
        
        st.markdown("---")
        
        if st.button("🚪 Logout"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.session_state.is_admin = False
            st.rerun()
    
    # Conteúdo principal baseado na página selecionada
    if selected_page == "🏠 Dashboard":
        show_dashboard()
    elif selected_page == "🎯 Apostas":
        show_betting_page()
    elif selected_page == "📊 Histórico":
        show_history_page()
    elif selected_page == "⚙️ Admin" and st.session_state.is_admin:
        show_admin_page()

def show_dashboard():
    """Mostra o dashboard principal"""
    st.markdown("## 🏠 Dashboard")
    
    # Estatísticas do usuário
    col1, col2, col3, col4 = st.columns(4)
    
    user_bets = get_user_bets(st.session_state.username)
    total_bets = len(user_bets)
    total_amount = sum(bet['amount'] for bet in user_bets)
    pending_bets = len([bet for bet in user_bets if bet['status'] == 'pending'])
    
    with col1:
        st.metric("🎯 Total de Apostas", total_bets)
    with col2:
        st.metric("💸 Total Apostado", f"{total_amount:,.0f}")
    with col3:
        st.metric("⏳ Apostas Pendentes", pending_bets)
    with col4:
        st.metric("💰 Pontos Atuais", f"{get_user_points(st.session_state.username):,.0f}")
    
    st.markdown("---")
    
    # Próximas partidas
    st.markdown("### ⚽ Próximas Partidas")
    matches = get_upcoming_matches_with_names()
    
    if matches:
        for match in matches[:5]:  # Mostrar apenas as próximas 5
            col1, col2, col3 = st.columns([2, 1, 2])
            
            with col1:
                st.markdown(f"**{match['team1_name']}**")
            with col2:
                st.markdown(f"**VS**")
                st.caption(f"{match['date']} {match['time']}")
            with col3:
                st.markdown(f"**{match['team2_name']}**")
            
            st.markdown("---")
    else:
        st.info("Nenhuma partida agendada no momento.")

def show_betting_page():
    """Mostra a página de apostas"""
    st.markdown("## 🎯 Apostas")
    
    matches = get_upcoming_matches_with_names()
    
    if not matches:
        st.info("Nenhuma partida disponível para apostas no momento.")
        return
    
    # Seletor de partida
    match_options = [f"{match['team1_name']} vs {match['team2_name']} - {match['date']} {match['time']}" 
                    for match in matches]
    selected_match_idx = st.selectbox("Selecione uma partida:", range(len(match_options)), 
                                     format_func=lambda x: match_options[x])
    
    if selected_match_idx is not None:
        selected_match = matches[selected_match_idx]
        match_id = selected_match['id']
        
        st.markdown(f"### {selected_match['team1_name']} vs {selected_match['team2_name']}")
        st.caption(f"📅 {selected_match['date']} ⏰ {selected_match['time']}")
        
        # Obter odds da partida
        odds = get_match_odds(match_id)
        custom_bets = get_custom_bets(match_id)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Odds Regulares")
            if odds:
                for odd in odds:
                    with st.expander(f"{odd['template_name']} - {odd['odds_value']:.2f}x"):
                        st.write(odd['description'])
                        
                        if odd['player_id']:
                            player_name = get_player_name(odd['player_id'])
                            st.write(f"Jogador: {player_name}")
                        
                        amount = st.number_input(f"Valor da aposta (ID: {odd['id']})", 
                                               min_value=1, max_value=get_user_points(st.session_state.username),
                                               key=f"regular_{odd['id']}")
                        
                        if st.button(f"Apostar", key=f"bet_regular_{odd['id']}"):
                            success, message = place_bet(st.session_state.username, match_id, 
                                                       match_odds_id=odd['id'], amount=amount)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
            else:
                st.info("Nenhuma odd disponível para esta partida.")
        
        with col2:
            st.markdown("#### 🎲 Apostas Personalizadas")
            if custom_bets:
                for custom_bet in custom_bets:
                    with st.expander(f"{custom_bet['description']} - {custom_bet['odds']:.2f}x"):
                        if custom_bet['player_id']:
                            player_name = get_player_name(custom_bet['player_id'])
                            st.write(f"Jogador: {player_name}")
                        
                        amount = st.number_input(f"Valor da aposta (ID: {custom_bet['id']})", 
                                               min_value=1, max_value=get_user_points(st.session_state.username),
                                               key=f"custom_{custom_bet['id']}")
                        
                        if st.button(f"Apostar", key=f"bet_custom_{custom_bet['id']}"):
                            success, message = place_bet(st.session_state.username, match_id, 
                                                       custom_bet_id=custom_bet['id'], amount=amount)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
            else:
                st.info("Nenhuma aposta personalizada disponível.")

def show_history_page():
    """Mostra o histórico de apostas do usuário"""
    st.markdown("## 📊 Histórico de Apostas")
    
    user_bets = get_user_bets(st.session_state.username)
    
    if not user_bets:
        st.info("Você ainda não fez nenhuma aposta.")
        return
    
    # Criar DataFrame para exibição
    df_data = []
    for bet in user_bets:
        df_data.append({
            'Data': bet['timestamp'],
            'Partida': f"{bet['team1_name']} vs {bet['team2_name']}",
            'Tipo': bet['bet_type'].title(),
            'Aposta': bet['bet_name'] if bet['bet_name'] else bet['bet_description'],
            'Valor': f"{bet['amount']:.0f}",
            'Odd': f"{bet['odds']:.2f}x",
            'Retorno Potencial': f"{bet['amount'] * bet['odds']:.0f}",
            'Status': bet['status'].title()
        })
    
    df = pd.DataFrame(df_data)
    st.dataframe(df, use_container_width=True)
    
    # Estatísticas
    st.markdown("### 📈 Estatísticas")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        total_apostado = sum(bet['amount'] for bet in user_bets)
        st.metric("💸 Total Apostado", f"{total_apostado:,.0f}")
    
    with col2:
        apostas_pendentes = len([bet for bet in user_bets if bet['status'] == 'pending'])
        st.metric("⏳ Apostas Pendentes", apostas_pendentes)
    
    with col3:
        retorno_potencial = sum(bet['amount'] * bet['odds'] for bet in user_bets if bet['status'] == 'pending')
        st.metric("🎯 Retorno Potencial", f"{retorno_potencial:,.0f}")

def show_admin_page():
    """Mostra o painel administrativo"""
    st.markdown("## ⚙️ Painel Administrativo")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Times", "Jogadores", "Partidas", "Apostas Personalizadas"])
    
    with tab1:
        st.markdown("### Gerenciar Times")
        
        # Adicionar novo time
        with st.form("add_team"):
            st.markdown("#### Adicionar Novo Time")
            team_name = st.text_input("Nome do Time")
            if st.form_submit_button("Adicionar Time"):
                if team_name:
                    success, message = add_team(team_name)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)
                else:
                    st.error("Por favor, insira o nome do time.")
        
        # Listar times existentes
        st.markdown("#### Times Cadastrados")
        teams = get_all_teams()
        if teams:
            df_teams = pd.DataFrame(teams)
            st.dataframe(df_teams, use_container_width=True)
        else:
            st.info("Nenhum time cadastrado.")
    
    with tab2:
        st.markdown("### Gerenciar Jogadores")
        
        # Adicionar novo jogador
        with st.form("add_player"):
            st.markdown("#### Adicionar Novo Jogador")
            player_name = st.text_input("Nome do Jogador")
            teams = get_all_teams()
            if teams:
                team_options = {team['name']: team['id'] for team in teams}
                selected_team = st.selectbox("Time", list(team_options.keys()))
                
                if st.form_submit_button("Adicionar Jogador"):
                    if player_name and selected_team:
                        team_id = team_options[selected_team]
                        success, message = add_player(player_name, team_id)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        st.error("Por favor, preencha todos os campos.")
            else:
                st.warning("Cadastre pelo menos um time antes de adicionar jogadores.")
        
        # Listar jogadores existentes
        st.markdown("#### Jogadores Cadastrados")
        players = get_all_players()
        if players:
            for player in players:
                player['team_name'] = get_team_name(player['team_id'])
            df_players = pd.DataFrame(players)
            st.dataframe(df_players[['name', 'team_name']], use_container_width=True)
        else:
            st.info("Nenhum jogador cadastrado.")
    
    with tab3:
        st.markdown("### Gerenciar Partidas")
        
        # Adicionar nova partida
        with st.form("add_match"):
            st.markdown("#### Adicionar Nova Partida")
            teams = get_all_teams()
            if len(teams) >= 2:
                team_options = {team['name']: team['id'] for team in teams}
                team1 = st.selectbox("Time Casa", list(team_options.keys()))
                team2 = st.selectbox("Time Visitante", list(team_options.keys()))
                
                col1, col2 = st.columns(2)
                with col1:
                    match_date = st.date_input("Data da Partida")
                with col2:
                    match_time = st.time_input("Horário da Partida")
                
                if st.form_submit_button("Adicionar Partida"):
                    if team1 != team2:
                        team1_id = team_options[team1]
                        team2_id = team_options[team2]
                        success, message = add_match(team1_id, team2_id, str(match_date), str(match_time))
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        st.error("Selecione times diferentes.")
            else:
                st.warning("Cadastre pelo menos dois times antes de criar partidas.")
        
        # Listar partidas existentes
        st.markdown("#### Partidas Cadastradas")
        matches = get_upcoming_matches_with_names()
        if matches:
            df_matches = pd.DataFrame(matches)
            st.dataframe(df_matches[['team1_name', 'team2_name', 'date', 'time', 'status']], 
                        use_container_width=True)
        else:
            st.info("Nenhuma partida cadastrada.")
    
    with tab4:
        st.markdown("### Apostas Personalizadas")
        
        # Adicionar aposta personalizada
        with st.form("add_custom_bet"):
            st.markdown("#### Criar Aposta Personalizada")
            matches = get_upcoming_matches_with_names()
            if matches:
                match_options = {f"{match['team1_name']} vs {match['team2_name']}": match['id'] 
                               for match in matches}
                selected_match = st.selectbox("Partida", list(match_options.keys()))
                
                description = st.text_input("Descrição da Aposta")
                odds = st.number_input("Odd", min_value=1.01, value=2.0, step=0.01)
                
                # Opção de jogador (opcional)
                include_player = st.checkbox("Incluir jogador específico?")
                player_id = None
                if include_player:
                    players = get_all_players()
                    if players:
                        player_options = {f"{player['name']} ({get_team_name(player['team_id'])})": player['id'] 
                                        for player in players}
                        selected_player = st.selectbox("Jogador", list(player_options.keys()))
                        player_id = player_options[selected_player]
                
                if st.form_submit_button("Criar Aposta Personalizada"):
                    if description and selected_match:
                        match_id = match_options[selected_match]
                        success, message = add_custom_bet(match_id, description, odds, player_id, 
                                                         st.session_state.username)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
                    else:
                        st.error("Por favor, preencha todos os campos obrigatórios.")
            else:
                st.warning("Cadastre pelo menos uma partida antes de criar apostas personalizadas.")

if __name__ == "__main__":
    main()

