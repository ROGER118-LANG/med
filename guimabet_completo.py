import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib

def init_db():
    """Inicializa o banco de dados com todas as tabelas necessárias"""
    conn = sqlite3.connect("primabet.db")
    c = conn.cursor()
    print("Conectado ao banco de dados. Criando/Verificando tabelas...")

    # Tabela de usuários
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        username TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        points INTEGER DEFAULT 100,
        is_admin INTEGER DEFAULT 0
    )
    """)

    # Tabela de times
    c.execute("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL
    )
    """)

    # Tabela de jogadores
    c.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        team_id INTEGER,
        FOREIGN KEY (team_id) REFERENCES teams (id) ON DELETE CASCADE
    )
    """)

    # Tabela de partidas
    c.execute("""
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
    """)

    # Tabela de categorias de odds
    c.execute("""
    CREATE TABLE IF NOT EXISTS odds_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        description TEXT,
        is_active INTEGER DEFAULT 1
    )
    """)

    # Tabela de templates de odds
    c.execute("""
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
    """)

    # Tabela de odds por partida
    c.execute("""
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
    """)
    
    # Tabela de histórico de odds
    c.execute("""
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
    """)

    # Tabela de apostas personalizadas
    c.execute("""
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
    """)

    # Tabela de propostas de apostas
    c.execute("""
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
    """)

    # Tabela principal de apostas dos usuários
    c.execute("""
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
    """)

    # Categorias de odds
    c.execute("INSERT OR IGNORE INTO odds_categories (name, description) VALUES ('Resultado', 'Vitória, Empate ou Derrota')")
    c.execute("INSERT OR IGNORE INTO odds_categories (name, description) VALUES ('Gols', 'Apostas relacionadas a gols')")
    c.execute("INSERT OR IGNORE INTO odds_categories (name, description) VALUES ('Jogadores', 'Apostas em desempenho de jogadores')")
    
    # Templates de odds
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (1, 'Vitória Time Casa', 'Time da casa vence', 'home_win', 2.5, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (1, 'Empate', 'Partida termina empatada', 'draw', 3.2, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (1, 'Vitória Time Visitante', 'Time visitante vence', 'away_win', 2.8, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (2, 'Mais de 2.5 Gols', 'Partida com mais de 2.5 gols', 'over_2_5', 1.8, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (2, 'Menos de 2.5 Gols', 'Partida com menos de 2.5 gols', 'under_2_5', 2.1, 0)")
    c.execute("INSERT OR IGNORE INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player) VALUES (2, 'Ambos marcam', 'Ambos os times marcam gol', 'both_teams_score', 1.9, 0)")
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

def get_finished_matches():
    """Obtém partidas finalizadas com nomes dos times"""
    conn = db_connect()
    matches = [dict(row) for row in conn.execute("""
        SELECT m.id, m.date, m.time, t1.name as team1_name, t2.name as team2_name,
               m.team1_score, m.team2_score, m.status
        FROM matches m 
        JOIN teams t1 ON m.team1_id = t1.id 
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.status = 'finished' ORDER BY m.date DESC, m.time DESC
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

def get_odds_templates(conn):
    """Obtém templates de odds usando a conexão fornecida"""
    templates = [dict(row) for row in conn.execute("SELECT * FROM odds_templates").fetchall()]
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
        cursor = conn.cursor()
        cursor.execute("INSERT INTO matches (team1_id, team2_id, date, time) VALUES (?, ?, ?, ?)", 
                    (team1_id, team2_id, date, time))
        match_id = cursor.lastrowid
        
        # Adicionar odds padrão para a partida
        templates = get_odds_templates(conn)
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
        conn.rollback()
        return False, f"Erro ao adicionar partida: {e}"
    finally:
        conn.close()

# ===== NOVAS FUNCIONALIDADES PARA RESULTADOS =====

def update_match_result(match_id, team1_score, team2_score):
    """Atualiza o resultado de uma partida e seu status para 'finished'"""
    conn = db_connect()
    try:
        conn.execute("""
            UPDATE matches
            SET team1_score = ?, team2_score = ?, status = 'finished'
            WHERE id = ?
        """, (team1_score, team2_score, match_id))
        conn.commit()
        return True, "Resultado da partida atualizado com sucesso!"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao atualizar resultado da partida: {e}"
    finally:
        conn.close()

def finalize_match_and_distribute_points(match_id):
    """Finaliza uma partida e distribui pontos para os apostadores"""
    conn = db_connect()
    try:
        # Buscar informações da partida
        match = conn.execute("""
            SELECT team1_score, team2_score, status 
            FROM matches WHERE id = ?
        """, (match_id,)).fetchone()
        
        if not match or match['status'] != 'finished':
            return False, "Partida não encontrada ou não finalizada"
        
        team1_score = match['team1_score']
        team2_score = match['team2_score']
        total_gols = team1_score + team2_score
        
        # Determinar resultado da partida
        if team1_score > team2_score:
            match_result = 'home_win'
        elif team2_score > team1_score:
            match_result = 'away_win'
        else:
            match_result = 'draw'
        
        # Buscar todas as apostas pendentes para esta partida
        bets = conn.execute("""
            SELECT b.id, b.user_id, b.amount, b.odds, b.bet_type, 
                   b.match_odds_id, b.custom_bet_id, b.bet_description,
                   mo.template_id, ot.bet_type as odds_bet_type,
                   cb.description as custom_description, cb.result as custom_result
            FROM bets b
            LEFT JOIN match_odds mo ON b.match_odds_id = mo.id
            LEFT JOIN odds_templates ot ON mo.template_id = ot.id
            LEFT JOIN custom_bets cb ON b.custom_bet_id = cb.id
            WHERE b.match_id = ? AND b.status = 'pending'
        """, (match_id,)).fetchall()
        
        processed_bets = 0
        winning_bets = 0
        total_winnings = 0
        
        for bet in bets:
            bet_won = False
            
            if bet['bet_type'] == 'regular':
                # Apostas regulares baseadas em templates
                odds_bet_type = bet['odds_bet_type']
                
                if odds_bet_type == 'home_win' and match_result == 'home_win':
                    bet_won = True
                elif odds_bet_type == 'away_win' and match_result == 'away_win':
                    bet_won = True
                elif odds_bet_type == 'draw' and match_result == 'draw':
                    bet_won = True
                elif odds_bet_type == 'over_2_5' and total_gols > 2.5:
                    bet_won = True
                elif odds_bet_type == 'under_2_5' and total_gols < 2.5:
                    bet_won = True
                elif odds_bet_type == 'both_teams_score':
                    bet_won = team1_score > 0 and team2_score > 0
                # Adicionar mais tipos conforme necessário
                
            elif bet['bet_type'] == 'custom':
                # Para apostas personalizadas, verificar se o admin definiu o resultado
                if bet['custom_result'] == 'won':
                    bet_won = True
                elif bet['custom_result'] == 'lost':
                    bet_won = False
                else:
                    # Se não foi definido, marcar como perdida por padrão
                    bet_won = False
            
            # Atualizar status da aposta e pontos do usuário
            if bet_won:
                winnings = bet['amount'] * bet['odds']
                conn.execute("""
                    UPDATE users SET points = points + ? WHERE username = ?
                """, (winnings, bet['user_id']))
                conn.execute("""
                    UPDATE bets SET status = 'won' WHERE id = ?
                """, (bet['id'],))
                winning_bets += 1
                total_winnings += winnings
            else:
                conn.execute("""
                    UPDATE bets SET status = 'lost' WHERE id = ?
                """, (bet['id'],))
            
            processed_bets += 1
        
        conn.commit()
        return True, f"{processed_bets} apostas processadas, {winning_bets} vencedoras, {total_winnings:.2f} pontos distribuídos"
        
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao finalizar partida: {e}"
    finally:
        conn.close()

def process_custom_bet_result(custom_bet_id, result):
    """Processa o resultado de uma aposta personalizada"""
    conn = db_connect()
    try:
        conn.execute("""
            UPDATE custom_bets SET result = ? WHERE id = ?
        """, (result, custom_bet_id))
        conn.commit()
        return True, "Resultado da aposta personalizada atualizado"
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao atualizar aposta personalizada: {e}"
    finally:
        conn.close()

def get_match_statistics(match_id):
    """Obtém estatísticas de uma partida finalizada"""
    conn = db_connect()
    try:
        # Informações básicas da partida
        match_info = conn.execute("""
            SELECT m.*, t1.name as team1_name, t2.name as team2_name
            FROM matches m
            JOIN teams t1 ON m.team1_id = t1.id
            JOIN teams t2 ON m.team2_id = t2.id
            WHERE m.id = ?
        """, (match_id,)).fetchone()
        
        if not match_info:
            return None
        
        # Estatísticas das apostas
        bet_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_bets,
                SUM(amount) as total_amount,
                COUNT(CASE WHEN status = 'won' THEN 1 END) as winning_bets,
                COUNT(CASE WHEN status = 'lost' THEN 1 END) as losing_bets,
                SUM(CASE WHEN status = 'won' THEN amount * odds ELSE 0 END) as total_winnings
            FROM bets
            WHERE match_id = ?
        """, (match_id,)).fetchone()
        
        return {
            'match': dict(match_info),
            'stats': dict(bet_stats)
        }
        
    except Exception as e:
        return None
    finally:
        conn.close()

# ===== INTERFACES ADMIN PARA RESULTADOS =====

def admin_manage_match_results():
    """Interface para o admin gerenciar resultados das partidas"""
    st.subheader("🏆 Gerenciar Resultados das Partidas")
    
    # Tabs para organizar melhor
    tab1, tab2, tab3 = st.tabs(["Inserir Resultados", "Partidas Finalizadas", "Apostas Personalizadas"])
    
    with tab1:
        st.write("### Partidas Pendentes")
        upcoming_matches = get_upcoming_matches_with_names()
        
        if not upcoming_matches:
            st.info("Não há partidas pendentes no momento.")
        else:
            for match in upcoming_matches:
                with st.expander(f"{match['team1_name']} vs {match['team2_name']} - {match['date']} {match['time']}"):
                    col1, col2, col3 = st.columns([2, 2, 1])
                    
                    with col1:
                        team1_score = st.number_input(
                            f"Gols {match['team1_name']}", 
                            min_value=0, 
                            max_value=20, 
                            value=0,
                            key=f"team1_score_{match['id']}"
                        )
                    
                    with col2:
                        team2_score = st.number_input(
                            f"Gols {match['team2_name']}", 
                            min_value=0, 
                            max_value=20, 
                            value=0,
                            key=f"team2_score_{match['id']}"
                        )
                    
                    with col3:
                        if st.button("Finalizar", key=f"finalize_{match['id']}"):
                            # Atualizar resultado da partida
                            success, message = update_match_result(match['id'], team1_score, team2_score)
                            
                            if success:
                                # Processar apostas e distribuir pontos
                                success_points, message_points = finalize_match_and_distribute_points(match['id'])
                                
                                if success_points:
                                    st.success(f"✅ {message} {message_points}")
                                    st.rerun()
                                else:
                                    st.error(f"❌ Resultado salvo, mas erro ao processar apostas: {message_points}")
                            else:
                                st.error(f"❌ {message}")
    
    with tab2:
        st.write("### Partidas Finalizadas")
        finished_matches = get_finished_matches()
        
        if not finished_matches:
            st.info("Nenhuma partida finalizada ainda.")
        else:
            for match in finished_matches:
                result_text = f"{match['team1_name']} {match['team1_score']} x {match['team2_score']} {match['team2_name']}"
                
                with st.expander(f"🏁 {result_text} - {match['date']} {match['time']}"):
                    # Mostrar estatísticas da partida
                    stats = get_match_statistics(match['id'])
                    if stats:
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total de Apostas", stats['stats']['total_bets'] or 0)
                        with col2:
                            st.metric("Apostas Vencedoras", stats['stats']['winning_bets'] or 0)
                        with col3:
                            st.metric("Valor Total Apostado", f"{stats['stats']['total_amount'] or 0:.2f}")
                        with col4:
                            st.metric("Prêmios Distribuídos", f"{stats['stats']['total_winnings'] or 0:.2f}")
    
    with tab3:
        admin_manage_custom_bet_results()

def admin_manage_custom_bet_results():
    """Interface para o admin definir resultados de apostas personalizadas"""
    st.write("### Gerenciar Resultados de Apostas Personalizadas")
    
    # Buscar partidas finalizadas com apostas personalizadas pendentes
    conn = db_connect()
    pending_custom_bets = conn.execute("""
        SELECT DISTINCT cb.id, cb.description, cb.match_id, 
               m.team1_score, m.team2_score,
               t1.name as team1_name, t2.name as team2_name,
               cb.result
        FROM custom_bets cb
        JOIN matches m ON cb.match_id = m.id
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.status = 'finished' AND cb.result = 'pending'
    """).fetchall()
    conn.close()
    
    if not pending_custom_bets:
        st.info("Não há apostas personalizadas pendentes de resultado.")
        return
    
    for custom_bet in pending_custom_bets:
        with st.expander(f"Aposta: {custom_bet['description']}"):
            st.write(f"**Partida:** {custom_bet['team1_name']} {custom_bet['team1_score']} x {custom_bet['team2_score']} {custom_bet['team2_name']}")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("✅ Venceu", key=f"won_{custom_bet['id']}"):
                    success, message = process_custom_bet_result(custom_bet['id'], 'won')
                    if success:
                        st.success("Aposta marcada como vencedora!")
                        st.rerun()
                    else:
                        st.error(f"Erro: {message}")
            
            with col2:
                if st.button("❌ Perdeu", key=f"lost_{custom_bet['id']}"):
                    success, message = process_custom_bet_result(custom_bet['id'], 'lost')
                    if success:
                        st.success("Aposta marcada como perdedora!")
                        st.rerun()
                    else:
                        st.error(f"Erro: {message}")
            
            with col3:
                if st.button("🔄 Cancelar", key=f"void_{custom_bet['id']}"):
                    success, message = process_custom_bet_result(custom_bet['id'], 'void')
                    if success:
                        st.success("Aposta cancelada!")
                        st.rerun()
                    else:
                        st.error(f"Erro: {message}")

# ===== INTERFACES ADMIN AUXILIARES =====

def admin_manage_teams():
    """Gerenciar times"""
    st.subheader("⚽ Gerenciar Times")
    
    # Adicionar novo time
    with st.expander("Adicionar Novo Time"):
        team_name = st.text_input("Nome do Time")
        if st.button("Adicionar Time"):
            if team_name:
                success, message = add_team(team_name)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.error("Por favor, insira o nome do time.")
    
    # Listar times existentes
    st.write("### Times Cadastrados")
    teams = get_all_teams()
    if teams:
        for team in teams:
            st.write(f"• {team['name']}")
    else:
        st.info("Nenhum time cadastrado ainda.")

def admin_manage_players():
    """Gerenciar jogadores"""
    st.subheader("👤 Gerenciar Jogadores")
    
    teams = get_all_teams()
    if not teams:
        st.warning("Cadastre pelo menos um time antes de adicionar jogadores.")
        return
    
    # Adicionar novo jogador
    with st.expander("Adicionar Novo Jogador"):
        player_name = st.text_input("Nome do Jogador")
        team_options = {team['name']: team['id'] for team in teams}
        selected_team = st.selectbox("Time", list(team_options.keys()))
        
        if st.button("Adicionar Jogador"):
            if player_name and selected_team:
                team_id = team_options[selected_team]
                success, message = add_player(player_name, team_id)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.error("Por favor, preencha todos os campos.")
    
    # Listar jogadores por time
    st.write("### Jogadores por Time")
    for team in teams:
        players = get_players_by_team(team['id'])
        if players:
            st.write(f"**{team['name']}:**")
            for player in players:
                st.write(f"  • {player['name']}")
        else:
            st.write(f"**{team['name']}:** Nenhum jogador cadastrado")

def admin_manage_matches():
    """Gerenciar partidas"""
    st.subheader("⚽ Gerenciar Partidas")
    
    teams = get_all_teams()
    if len(teams) < 2:
        st.warning("Cadastre pelo menos dois times antes de criar partidas.")
        return
    
    # Adicionar nova partida
    with st.expander("Adicionar Nova Partida"):
        team_options = {team['name']: team['id'] for team in teams}
        
        col1, col2 = st.columns(2)
        with col1:
            team1 = st.selectbox("Time da Casa", list(team_options.keys()), key="team1")
        with col2:
            team2 = st.selectbox("Time Visitante", list(team_options.keys()), key="team2")
        
        col3, col4 = st.columns(2)
        with col3:
            match_date = st.date_input("Data da Partida")
        with col4:
            match_time = st.time_input("Horário da Partida")
        
        if st.button("Criar Partida"):
            if team1 != team2:
                team1_id = team_options[team1]
                team2_id = team_options[team2]
                date_str = match_date.strftime("%Y-%m-%d")
                time_str = match_time.strftime("%H:%M")
                
                success, message = add_match(team1_id, team2_id, date_str, time_str)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.error("Selecione times diferentes para a partida.")
    
    # Listar partidas existentes
    st.write("### Partidas Cadastradas")
    upcoming_matches = get_upcoming_matches_with_names()
    if upcoming_matches:
        for match in upcoming_matches:
            st.write(f"🏟️ {match['team1_name']} vs {match['team2_name']} - {match['date']} {match['time']}")
    else:
        st.info("Nenhuma partida cadastrada ainda.")

def admin_manage_custom_bets():
    """Gerenciar apostas personalizadas"""
    st.subheader("🎯 Apostas Personalizadas")
    
    upcoming_matches = get_upcoming_matches_with_names()
    if not upcoming_matches:
        st.warning("Não há partidas disponíveis para criar apostas personalizadas.")
        return
    
    # Criar nova aposta personalizada
    with st.expander("Criar Nova Aposta Personalizada"):
        match_options = {f"{m['team1_name']} vs {m['team2_name']} - {m['date']}": m['id'] for m in upcoming_matches}
        selected_match = st.selectbox("Partida", list(match_options.keys()))
        
        bet_description = st.text_area("Descrição da Aposta")
        bet_odds = st.number_input("Odds", min_value=1.01, max_value=50.0, value=2.0, step=0.1)
        
        # Opção para apostas relacionadas a jogadores
        include_player = st.checkbox("Aposta relacionada a jogador específico")
        player_id = None
        
        if include_player:
            match_id = match_options[selected_match]
            match_info = get_match_by_id(match_id)
            
            # Buscar jogadores dos dois times
            team1_players = get_players_by_team(match_info['team1_id'])
            team2_players = get_players_by_team(match_info['team2_id'])
            all_players = team1_players + team2_players
            
            if all_players:
                player_options = {f"{p['name']}": p['id'] for p in all_players}
                selected_player = st.selectbox("Jogador", list(player_options.keys()))
                player_id = player_options[selected_player]
            else:
                st.warning("Nenhum jogador cadastrado para os times desta partida.")
        
        if st.button("Criar Aposta Personalizada"):
            if bet_description and selected_match:
                match_id = match_options[selected_match]
                success, message = add_custom_bet(match_id, bet_description, bet_odds, player_id)
                if success:
                    st.success(message)
                else:
                    st.error(message)
            else:
                st.error("Por favor, preencha todos os campos obrigatórios.")

def admin_panel():
    """Painel administrativo completo"""
    st.title("🔧 Painel Administrativo")
    
    # Menu de navegação do admin
    admin_option = st.selectbox(
        "Escolha uma opção:",
        ["Gerenciar Times", "Gerenciar Jogadores", "Gerenciar Partidas", "Gerenciar Resultados", "Apostas Personalizadas"]
    )
    
    if admin_option == "Gerenciar Times":
        admin_manage_teams()
    elif admin_option == "Gerenciar Jogadores":
        admin_manage_players()
    elif admin_option == "Gerenciar Partidas":
        admin_manage_matches()
    elif admin_option == "Gerenciar Resultados":
        admin_manage_match_results()  # Nova função
    elif admin_option == "Apostas Personalizadas":
        admin_manage_custom_bets()

# ===== INTERFACE PRINCIPAL =====

def main():
    """Função principal do aplicativo"""
    st.set_page_config(page_title="PrimaBet", page_icon="🎯", layout="wide")
    
    # Inicializar banco de dados
    init_db()
    
    # Verificar se o usuário está logado
    if 'user' not in st.session_state:
        st.session_state.user = None
    
    if st.session_state.user is None:
        # Tela de login/registro
        st.title("🎯 PrimaBet - Sistema de Apostas")
        
        tab1, tab2 = st.tabs(["Login", "Registrar"])
        
        with tab1:
            st.subheader("Fazer Login")
            username = st.text_input("Usuário", key="login_user")
            password = st.text_input("Senha", type="password", key="login_pass")
            
            if st.button("Entrar"):
                user = login_user(username, password)
                if user:
                    st.session_state.user = dict(user)
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha incorretos.")
        
        with tab2:
            st.subheader("Criar Conta")
            new_username = st.text_input("Usuário", key="reg_user")
            new_password = st.text_input("Senha", type="password", key="reg_pass")
            
            if st.button("Registrar"):
                success, message = register_user(new_username, new_password)
                if success:
                    st.success(message)
                else:
                    st.error(message)
    
    else:
        # Usuário logado
        user = st.session_state.user
        
        # Sidebar com informações do usuário
        with st.sidebar:
            st.write(f"👤 **{user['username']}**")
            current_points = get_user_points(user['username'])
            st.write(f"💎 **{current_points} pontos**")
            
            if st.button("Logout"):
                st.session_state.user = None
                st.rerun()
        
        # Interface principal baseada no tipo de usuário
        if user['is_admin']:
            admin_panel()
        else:
            # Interface do usuário comum
            st.title("🎯 PrimaBet")
            
            # Menu do usuário
            user_option = st.selectbox(
                "Escolha uma opção:",
                ["Ver Partidas", "Minhas Apostas", "Histórico"]
            )
            
            if user_option == "Ver Partidas":
                st.subheader("⚽ Partidas Disponíveis")
                matches = get_upcoming_matches_with_names()
                
                if not matches:
                    st.info("Não há partidas disponíveis no momento.")
                else:
                    for match in matches:
                        with st.expander(f"{match['team1_name']} vs {match['team2_name']} - {match['date']} {match['time']}"):
                            # Mostrar odds da partida
                            odds = get_match_odds(match['id'])
                            custom_bets = get_custom_bets(match['id'])
                            
                            if odds or custom_bets:
                                st.write("**Odds Disponíveis:**")
                                
                                # Odds regulares
                                for odd in odds:
                                    col1, col2, col3 = st.columns([3, 1, 1])
                                    with col1:
                                        st.write(f"{odd['template_name']}: {odd['description']}")
                                    with col2:
                                        st.write(f"**{odd['odds_value']:.2f}**")
                                    with col3:
                                        amount = st.number_input(
                                            "Valor", 
                                            min_value=1, 
                                            max_value=current_points, 
                                            value=10,
                                            key=f"amount_{odd['id']}"
                                        )
                                        if st.button("Apostar", key=f"bet_{odd['id']}"):
                                            success, message = place_bet(
                                                user['username'], 
                                                match['id'], 
                                                match_odds_id=odd['id'], 
                                                amount=amount
                                            )
                                            if success:
                                                st.success(message)
                                                st.rerun()
                                            else:
                                                st.error(message)
                                
                                # Apostas personalizadas
                                if custom_bets:
                                    st.write("**Apostas Especiais:**")
                                    for custom_bet in custom_bets:
                                        col1, col2, col3 = st.columns([3, 1, 1])
                                        with col1:
                                            st.write(custom_bet['description'])
                                        with col2:
                                            st.write(f"**{custom_bet['odds']:.2f}**")
                                        with col3:
                                            amount = st.number_input(
                                                "Valor", 
                                                min_value=1, 
                                                max_value=current_points, 
                                                value=10,
                                                key=f"custom_amount_{custom_bet['id']}"
                                            )
                                            if st.button("Apostar", key=f"custom_bet_{custom_bet['id']}"):
                                                success, message = place_bet(
                                                    user['username'], 
                                                    match['id'], 
                                                    custom_bet_id=custom_bet['id'], 
                                                    amount=amount
                                                )
                                                if success:
                                                    st.success(message)
                                                    st.rerun()
                                                else:
                                                    st.error(message)
                            else:
                                st.info("Nenhuma odd disponível para esta partida.")
            
            elif user_option == "Minhas Apostas":
                st.subheader("💰 Minhas Apostas Ativas")
                bets = get_user_bets(user['username'])
                
                if not bets:
                    st.info("Você ainda não fez nenhuma aposta.")
                else:
                    # Filtrar apostas pendentes
                    pending_bets = [bet for bet in bets if bet['status'] == 'pending']
                    
                    if pending_bets:
                        for bet in pending_bets:
                            bet_name = bet['bet_name'] if bet['bet_name'] else bet['bet_description']
                            potential_win = bet['amount'] * bet['odds']
                            
                            st.write(f"🎯 **{bet['team1_name']} vs {bet['team2_name']}**")
                            st.write(f"   Aposta: {bet_name}")
                            st.write(f"   Valor: {bet['amount']} pontos | Odd: {bet['odds']:.2f} | Ganho potencial: {potential_win:.2f}")
                            st.write(f"   Status: {bet['status']} | Data: {bet['timestamp']}")
                            st.write("---")
                    else:
                        st.info("Você não tem apostas pendentes.")
            
            elif user_option == "Histórico":
                st.subheader("📊 Histórico de Apostas")
                bets = get_user_bets(user['username'])
                
                if not bets:
                    st.info("Você ainda não fez nenhuma aposta.")
                else:
                    # Estatísticas gerais
                    total_bets = len(bets)
                    won_bets = len([bet for bet in bets if bet['status'] == 'won'])
                    lost_bets = len([bet for bet in bets if bet['status'] == 'lost'])
                    pending_bets = len([bet for bet in bets if bet['status'] == 'pending'])
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Total", total_bets)
                    with col2:
                        st.metric("Vencidas", won_bets)
                    with col3:
                        st.metric("Perdidas", lost_bets)
                    with col4:
                        st.metric("Pendentes", pending_bets)
                    
                    # Lista de apostas
                    st.write("### Todas as Apostas")
                    for bet in bets:
                        bet_name = bet['bet_name'] if bet['bet_name'] else bet['bet_description']
                        
                        if bet['status'] == 'won':
                            status_icon = "✅"
                            status_color = "green"
                        elif bet['status'] == 'lost':
                            status_icon = "❌"
                            status_color = "red"
                        else:
                            status_icon = "⏳"
                            status_color = "orange"
                        
                        st.write(f"{status_icon} **{bet['team1_name']} vs {bet['team2_name']}** - {bet_name}")
                        st.write(f"   Valor: {bet['amount']} | Odd: {bet['odds']:.2f} | Status: :{status_color}[{bet['status']}] | {bet['timestamp']}")

if __name__ == "__main__":
    main()

