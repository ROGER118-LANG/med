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
        conn.commit()
        return True, "Partida adicionada com sucesso!"
    except Exception as e:
        return False, f"Erro ao adicionar partida: {e}"
    finally:
        conn.close()

def add_match_odds(match_id, template_id, odds_value, player_id=None):
    """Adiciona odds para uma partida"""
    conn = db_connect()
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            INSERT INTO match_odds (match_id, template_id, odds_value, player_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (match_id, template_id, odds_value, player_id, now, now))
        conn.commit()
        return True, "Odds adicionadas com sucesso!"
    except Exception as e:
        return False, f"Erro ao adicionar odds: {e}"
    finally:
        conn.close()

def admin_panel():
    """Painel administrativo"""
    st.title("🔧 Painel Administrativo")
    
    admin_tabs = st.tabs(["Times", "Jogadores", "Partidas", "Odds", "Apostas Personalizadas", "Usuários"])
    
    with admin_tabs[0]:  # Times
        st.header("Gerenciar Times")
        
        # Adicionar novo time
        with st.form("add_team_form"):
            team_name = st.text_input("Nome do Time")
            if st.form_submit_button("Adicionar Time"):
                if team_name:
                    success, message = add_team(team_name)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Nome do time não pode estar vazio")
        
        # Listar times existentes
        st.subheader("Times Cadastrados")
        teams = get_all_teams()
        if teams:
            for team in teams:
                st.write(f"- {team['name']}")
        else:
            st.info("Nenhum time cadastrado")
    
    with admin_tabs[1]:  # Jogadores
        st.header("Gerenciar Jogadores")
        
        # Adicionar novo jogador
        teams = get_all_teams()
        if teams:
            with st.form("add_player_form"):
                player_name = st.text_input("Nome do Jogador")
                team_options = {team['name']: team['id'] for team in teams}
                selected_team = st.selectbox("Time", options=list(team_options.keys()))
                
                if st.form_submit_button("Adicionar Jogador"):
                    if player_name and selected_team:
                        team_id = team_options[selected_team]
                        success, message = add_player(player_name, team_id)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Nome do jogador e time são obrigatórios")
        else:
            st.warning("Cadastre pelo menos um time antes de adicionar jogadores")
        
        # Listar jogadores
        st.subheader("Jogadores Cadastrados")
        players = get_all_players()
        if players:
            for player in players:
                team_name = get_team_name(player['team_id'])
                st.write(f"- {player['name']} ({team_name})")
        else:
            st.info("Nenhum jogador cadastrado")
    
    with admin_tabs[2]:  # Partidas
        st.header("Gerenciar Partidas")
        
        # Adicionar nova partida
        teams = get_all_teams()
        if len(teams) >= 2:
            with st.form("add_match_form"):
                team_options = {team['name']: team['id'] for team in teams}
                team1 = st.selectbox("Time Casa", options=list(team_options.keys()))
                team2 = st.selectbox("Time Visitante", options=list(team_options.keys()))
                match_date = st.date_input("Data da Partida", value=datetime.date.today() + datetime.timedelta(days=1))
                match_time = st.time_input("Horário", value=datetime.time(20, 0))
                
                if st.form_submit_button("Adicionar Partida"):
                    if team1 != team2:
                        team1_id = team_options[team1]
                        team2_id = team_options[team2]
                        date_str = match_date.strftime("%Y-%m-%d")
                        time_str = match_time.strftime("%H:%M")
                        
                        success, message = add_match(team1_id, team2_id, date_str, time_str)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Um time não pode jogar contra si mesmo")
        else:
            st.warning("Cadastre pelo menos 2 times antes de criar partidas")
        
        # Listar partidas
        st.subheader("Partidas Cadastradas")
        matches = get_upcoming_matches_with_names()
        if matches:
            for match in matches:
                st.write(f"- {match['team1_name']} vs {match['team2_name']} - {match['date']} {match['time']}")
        else:
            st.info("Nenhuma partida cadastrada")
    
    with admin_tabs[3]:  # Odds
        st.header("Gerenciar Odds")
        
        matches = get_upcoming_matches_with_names()
        templates = get_odds_templates()
        
        if matches and templates:
            with st.form("add_odds_form"):
                # Selecionar partida
                match_options = {f"{m['team1_name']} vs {m['team2_name']} - {m['date']}": m['id'] for m in matches}
                selected_match = st.selectbox("Partida", options=list(match_options.keys()))
                
                # Selecionar template
                template_options = {f"{t['name']} - {t['description']}": t['id'] for t in templates}
                selected_template = st.selectbox("Tipo de Aposta", options=list(template_options.keys()))
                
                # Valor das odds
                odds_value = st.number_input("Valor das Odds", min_value=1.01, value=2.0, step=0.1)
                
                # Jogador (se necessário)
                template_id = template_options[selected_template]
                template_info = next(t for t in templates if t['id'] == template_id)
                player_id = None
                
                if template_info['requires_player']:
                    match_id = match_options[selected_match]
                    match_info = get_match_by_id(match_id)
                    team1_players = get_players_by_team(match_info['team1_id'])
                    team2_players = get_players_by_team(match_info['team2_id'])
                    all_players = team1_players + team2_players
                    
                    if all_players:
                        player_options = {p['name']: p['id'] for p in all_players}
                        selected_player = st.selectbox("Jogador", options=list(player_options.keys()))
                        player_id = player_options[selected_player]
                    else:
                        st.warning("Cadastre jogadores para os times desta partida")
                
                if st.form_submit_button("Adicionar Odds"):
                    match_id = match_options[selected_match]
                    success, message = add_match_odds(match_id, template_id, odds_value, player_id)
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
        else:
            if not matches:
                st.warning("Cadastre partidas antes de adicionar odds")
            if not templates:
                st.warning("Nenhum template de odds disponível")

    with admin_tabs[4]:  # Apostas Personalizadas
        st.header("Gerenciar Apostas Personalizadas")
        st.markdown("*Crie apostas únicas como 'Defende gol de pênalti', 'Recebe cartão amarelo', etc.*")
        
        matches = get_upcoming_matches_with_names()
        
        if matches:
            with st.form("add_custom_bet_form"):
                # Selecionar partida
                match_options = {f"{m['team1_name']} vs {m['team2_name']} - {m['date']}": m['id'] for m in matches}
                selected_match = st.selectbox("Partida", options=list(match_options.keys()))
                
                # Descrição da aposta personalizada
                bet_description = st.text_input(
                    "Descrição da Aposta", 
                    placeholder="Ex: Jogador defende gol de pênalti, Recebe cartão vermelho, etc."
                )
                
                # Valor das odds
                odds_value = st.number_input("Valor das Odds", min_value=1.01, value=3.0, step=0.1)
                
                # Opção de jogador específico
                match_id = match_options[list(match_options.keys())[0]] if match_options else None
                player_id = None
                
                if match_id:
                    match_info = get_match_by_id(match_id)
                    team1_players = get_players_by_team(match_info['team1_id'])
                    team2_players = get_players_by_team(match_info['team2_id'])
                    all_players = team1_players + team2_players
                    
                    if all_players:
                        include_player = st.checkbox("Esta aposta é específica para um jogador?")
                        if include_player:
                            player_options = {p['name']: p['id'] for p in all_players}
                            selected_player = st.selectbox("Jogador", options=list(player_options.keys()))
                            player_id = player_options[selected_player]
                
                if st.form_submit_button("Criar Aposta Personalizada"):
                    if bet_description.strip():
                        match_id = match_options[selected_match]
                        success, message = add_custom_bet(match_id, bet_description, odds_value, player_id, st.session_state.username)
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                    else:
                        st.error("Descrição da aposta é obrigatória")
        else:
            st.warning("Cadastre partidas antes de criar apostas personalizadas")
        
        # Listar apostas personalizadas existentes
        st.subheader("Apostas Personalizadas Ativas")
        if matches:
            conn = db_connect()
            custom_bets = [dict(row) for row in conn.execute("""
                SELECT cb.description, cb.odds, cb.player_id, 
                       t1.name as team1_name, t2.name as team2_name, m.date, m.time
                FROM custom_bets cb
                JOIN matches m ON cb.match_id = m.id
                JOIN teams t1 ON m.team1_id = t1.id
                JOIN teams t2 ON m.team2_id = t2.id
                WHERE cb.status = 'active' AND m.status = 'upcoming'
                ORDER BY m.date, m.time
            """).fetchall()]
            conn.close()
            
            if custom_bets:
                for bet in custom_bets:
                    player_info = ""
                    if bet['player_id']:
                        player_name = get_player_name(bet['player_id'])
                        player_info = f" - {player_name}"
                    
                    st.write(f"🎯 **{bet['description']}**{player_info}")
                    st.write(f"   📊 Odds: {bet['odds']:.2f} | ⚽ {bet['team1_name']} vs {bet['team2_name']} - {bet['date']}")
                    st.write("---")
            else:
                st.info("Nenhuma aposta personalizada ativa")
    
    with admin_tabs[5]:  # Usuários
        st.header("Gerenciar Usuários")
        
        conn = db_connect()
        users = [dict(row) for row in conn.execute("SELECT username, points, is_admin FROM users ORDER BY username").fetchall()]
        conn.close()
        
        if users:
            df_users = pd.DataFrame(users)
            df_users['Tipo'] = df_users['is_admin'].apply(lambda x: 'Admin' if x else 'Usuário')
            st.dataframe(df_users[['username', 'points', 'Tipo']], use_container_width=True)
        else:
            st.info("Nenhum usuário cadastrado")

# Interface do usuário
def login_page():
    """Página de login"""
    st.title("🎯 Bem-vindo ao PrimaBet!")
    st.markdown("---")
    
    tab1, tab2 = st.tabs(["🔑 Entrar", "📝 Registrar"])
    
    with tab1:
        st.subheader("Entre na sua conta")
        with st.form("login_form"):
            username = st.text_input("👤 Usuário")
            password = st.text_input("🔒 Senha", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                user = login_user(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = user['username']
                    st.session_state.is_admin = bool(user['is_admin'])
                    st.success("Login bem-sucedido!")
                    st.rerun()
                else: 
                    st.error("Usuário ou senha inválidos.")
    
    with tab2:
        st.subheader("Crie sua conta")
        with st.form("register_form"):
            new_username = st.text_input("👤 Escolha um nome de usuário")
            new_password = st.text_input("🔒 Crie uma senha", type="password")
            confirm_password = st.text_input("🔒 Confirme a senha", type="password")
            if st.form_submit_button("Registrar", use_container_width=True):
                if new_password != confirm_password:
                    st.error("As senhas não coincidem!")
                elif len(new_password) < 4:
                    st.error("A senha deve ter pelo menos 4 caracteres!")
                else:
                    success, message = register_user(new_username, new_password)
                    if success: 
                        st.success(message)
                    else: 
                        st.error(message)

def main_dashboard():
    """Dashboard principal"""
    # Sidebar
    st.sidebar.title(f"👋 Olá, {st.session_state.username}!")
    current_points = get_user_points(st.session_state.username)
    st.sidebar.metric("💰 Seus Pontos", current_points)
    
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        for key in list(st.session_state.keys()): 
            del st.session_state[key]
        st.rerun()

    # Navigation
    pages = ["🎯 Apostar", "📊 Minhas Apostas"]
    if st.session_state.get('is_admin', False): 
        pages.append("🔧 Painel Admin")
    
    selection = st.sidebar.radio("🧭 Navegação", pages)

    # Content
    if selection == "🎯 Apostar": 
        betting_page()
    elif selection == "📊 Minhas Apostas": 
        my_bets_page()
    elif selection == "🔧 Painel Admin":
        admin_panel()

def betting_page():
    """Página de apostas"""
    st.title("⚽ Partidas Disponíveis")
    
    matches = get_upcoming_matches_with_names()
    if not matches:
        st.info("🤷‍♂️ Nenhuma partida futura disponível no momento.")
        return
    
    for match in matches:
        with st.expander(f"🏆 {match['team1_name']} vs {match['team2_name']} - {match['date']} {match['time']}"):
            
            # Tabs para diferentes tipos de apostas
            bet_tabs = st.tabs(["🎲 Odds Regulares", "✨ Apostas Personalizadas"])
            
            with bet_tabs[0]:  # Odds regulares
                odds = get_match_odds(match['id'])
                if not odds:
                    st.write("📋 Odds para esta partida ainda não foram definidas.")
                else:
                    st.markdown("### 🎲 Opções de Aposta")
                    
                    with st.form(f"bet_form_{match['id']}"):
                        # Organizar odds por categoria
                        odds_by_category = {}
                        for odd in odds:
                            category = odd['category_name']
                            if category not in odds_by_category:
                                odds_by_category[category] = []
                            odds_by_category[category].append(odd)
                        
                        # Criar opções de seleção
                        odds_options = {}
                        for category, category_odds in odds_by_category.items():
                            st.markdown(f"**{category}**")
                            for odd in category_odds:
                                display_name = f"{odd['template_name']}"
                                if odd['player_id']:
                                    player_name = get_player_name(odd['player_id'])
                                    display_name += f" - {player_name}"
                                display_name += f" (Odds: {odd['odds_value']:.2f})"
                                odds_options[display_name] = odd['id']
                        
                        if odds_options:
                            selected_odd_str = st.selectbox("Escolha sua aposta:", options=list(odds_options.keys()))
                            amount = st.number_input("💰 Valor da aposta (pontos)", min_value=1, value=10, step=1)
                            
                            col1, col2 = st.columns(2)
                            selected_odd_id = odds_options[selected_odd_str]
                            selected_odd = next(o for o in odds if o['id'] == selected_odd_id)
                            potential_win = amount * selected_odd['odds_value']
                            
                            col1.metric("Aposta", f"{amount} pts")
                            col2.metric("Ganho Potencial", f"{potential_win:.0f} pts")
                            
                            if st.form_submit_button("🚀 Fazer Aposta", use_container_width=True):
                                success, message = place_bet(st.session_state.username, match['id'], match_odds_id=selected_odd_id, amount=amount)
                                if success:
                                    st.success(message)
                                    st.balloons()
                                    st.rerun()
                                else: 
                                    st.error(message)
            
            with bet_tabs[1]:  # Apostas personalizadas
                custom_bets = get_custom_bets(match['id'])
                if not custom_bets:
                    st.write("✨ Nenhuma aposta personalizada disponível para esta partida.")
                else:
                    st.markdown("### ✨ Apostas Personalizadas")
                    st.caption("*Apostas únicas criadas pelo administrador*")
                    
                    with st.form(f"custom_bet_form_{match['id']}"):
                        # Criar opções de apostas personalizadas
                        custom_options = {}
                        for custom_bet in custom_bets:
                            display_name = custom_bet['description']
                            if custom_bet['player_id']:
                                player_name = get_player_name(custom_bet['player_id'])
                                display_name += f" - {player_name}"
                            display_name += f" (Odds: {custom_bet['odds']:.2f})"
                            custom_options[display_name] = custom_bet['id']
