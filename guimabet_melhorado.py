import sqlite3
import pandas as pd
import datetime
import hashlib
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
    
    # Create odds categories table
    c.execute('''
    CREATE TABLE IF NOT EXISTS odds_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,
        description TEXT,
        is_active INTEGER DEFAULT 1
    )
    ''')
    
    # Create odds templates table
    c.execute('''
    CREATE TABLE IF NOT EXISTS odds_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER,
        name TEXT,
        description TEXT,
        bet_type TEXT,
        default_odds REAL,
        is_active INTEGER DEFAULT 1,
        requires_player INTEGER DEFAULT 0,
        FOREIGN KEY (category_id) REFERENCES odds_categories (id)
    )
    ''')
    
    # Create match odds table (replaces old odds table)
    c.execute('''
    CREATE TABLE IF NOT EXISTS match_odds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        template_id INTEGER,
        odds_value REAL,
        is_active INTEGER DEFAULT 1,
        player_id INTEGER DEFAULT NULL,
        created_at TEXT,
        updated_at TEXT,
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (template_id) REFERENCES odds_templates (id),
        FOREIGN KEY (player_id) REFERENCES players (id)
    )
    ''')
    
    # Create legacy odds table for backward compatibility
    c.execute('''
    CREATE TABLE IF NOT EXISTS odds (
        match_id INTEGER,
        team1_win REAL,
        draw REAL,
        team2_win REAL,
        FOREIGN KEY (match_id) REFERENCES matches (id)
    )
    ''')
    
    # Create bets table (updated)
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
        match_odds_id INTEGER DEFAULT NULL,
        potential_winnings REAL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (username),
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (custom_bet_id) REFERENCES custom_bets (id),
        FOREIGN KEY (player_id) REFERENCES players (id),
        FOREIGN KEY (match_odds_id) REFERENCES match_odds (id)
    )
    ''')
    
    # Create custom bets table (updated)
    c.execute('''
    CREATE TABLE IF NOT EXISTS custom_bets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_id INTEGER,
        description TEXT,
        odds REAL,
        player_id INTEGER DEFAULT NULL,
        status TEXT DEFAULT 'pending',
        result TEXT DEFAULT NULL,
        created_by TEXT DEFAULT 'admin',
        created_at TEXT,
        FOREIGN KEY (match_id) REFERENCES matches (id),
        FOREIGN KEY (player_id) REFERENCES players (id)
    )
    ''')
    
    # Create custom bet proposals table
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
    
    # Create odds history table for tracking changes
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
    
    # Insert default odds categories
    default_categories = [
        ("Resultado", "Apostas no resultado final da partida"),
        ("Gols", "Apostas relacionadas a gols"),
        ("Jogadores", "Apostas específicas de jogadores"),
        ("Especiais", "Apostas especiais e eventos específicos")
    ]
    
    for name, desc in default_categories:
        c.execute("SELECT * FROM odds_categories WHERE name = ?", (name,))
        if not c.fetchone():
            c.execute("INSERT INTO odds_categories (name, description) VALUES (?, ?)", (name, desc))
    
    # Insert default odds templates
    c.execute("SELECT COUNT(*) FROM odds_templates")
    if c.fetchone()[0] == 0:
        # Get category IDs
        c.execute("SELECT id FROM odds_categories WHERE name = 'Resultado'")
        resultado_cat = c.fetchone()[0]
        c.execute("SELECT id FROM odds_categories WHERE name = 'Gols'")
        gols_cat = c.fetchone()[0]
        c.execute("SELECT id FROM odds_categories WHERE name = 'Jogadores'")
        jogadores_cat = c.fetchone()[0]
        c.execute("SELECT id FROM odds_categories WHERE name = 'Especiais'")
        especiais_cat = c.fetchone()[0]
        
        default_templates = [
            # Resultado
            (resultado_cat, "Vitória Time 1", "Time da casa vence", "team1_win", 2.0, 1, 0),
            (resultado_cat, "Empate", "Partida termina empatada", "draw", 3.0, 1, 0),
            (resultado_cat, "Vitória Time 2", "Time visitante vence", "team2_win", 2.5, 1, 0),
            (resultado_cat, "Dupla Chance 1X", "Time 1 vence ou empata", "double_1x", 1.3, 1, 0),
            (resultado_cat, "Dupla Chance X2", "Empate ou Time 2 vence", "double_x2", 1.4, 1, 0),
            (resultado_cat, "Dupla Chance 12", "Time 1 ou Time 2 vence", "double_12", 1.2, 1, 0),
            
            # Gols
            (gols_cat, "Mais de 2.5 Gols", "Total de gols maior que 2.5", "over_2_5", 1.8, 1, 0),
            (gols_cat, "Menos de 2.5 Gols", "Total de gols menor que 2.5", "under_2_5", 2.0, 1, 0),
            (gols_cat, "Ambos Marcam - Sim", "Ambos os times marcam", "both_score_yes", 1.7, 1, 0),
            (gols_cat, "Ambos Marcam - Não", "Pelo menos um time não marca", "both_score_no", 2.1, 1, 0),
            (gols_cat, "Mais de 3.5 Gols", "Total de gols maior que 3.5", "over_3_5", 2.5, 1, 0),
            (gols_cat, "Menos de 1.5 Gols", "Total de gols menor que 1.5", "under_1_5", 3.0, 1, 0),
            
            # Jogadores
            (jogadores_cat, "Jogador Marca Gol", "Jogador específico marca pelo menos 1 gol", "player_scores", 3.0, 1, 1),
            (jogadores_cat, "Artilheiro da Partida", "Jogador é o artilheiro da partida", "top_scorer", 5.0, 1, 1),
            (jogadores_cat, "Jogador Recebe Cartão", "Jogador recebe cartão amarelo ou vermelho", "player_card", 4.0, 1, 1),
            
            # Especiais
            (especiais_cat, "Primeiro Gol - Time 1", "Time 1 marca o primeiro gol", "first_goal_team1", 1.9, 1, 0),
            (especiais_cat, "Primeiro Gol - Time 2", "Time 2 marca o primeiro gol", "first_goal_team2", 2.1, 1, 0),
            (especiais_cat, "Sem Gols no 1º Tempo", "Primeiro tempo termina 0-0", "ht_no_goals", 3.5, 1, 0),
            (especiais_cat, "Mais de 5 Escanteios", "Total de escanteios maior que 5", "over_5_corners", 2.2, 1, 0)
        ]
        
        for template in default_templates:
            c.execute('''
            INSERT INTO odds_templates (category_id, name, description, bet_type, default_odds, is_active, requires_player)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', template)
    
    conn.commit()
    conn.close()

# Authentication functions
def login(username, password):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password))
    user = c.fetchone()
    conn.close()
    return user

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

# User management functions
def get_all_users():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT username, points, is_admin FROM users ORDER BY points DESC")
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users

def update_user(username, new_username=None, new_points=None, is_admin=None):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    if new_username and new_username != username:
        c.execute("SELECT * FROM users WHERE username = ?", (new_username,))
        if c.fetchone():
            conn.close()
            return False, "Nome de usuário já existe."
        
        c.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, username))
        c.execute("UPDATE bets SET user_id = ? WHERE user_id = ?", (new_username, username))
        username = new_username
    
    if new_points is not None:
        c.execute("UPDATE users SET points = ? WHERE username = ?", (new_points, username))
    
    if is_admin is not None:
        c.execute("UPDATE users SET is_admin = ? WHERE username = ?", (1 if is_admin else 0, username))
    
    conn.commit()
    conn.close()
    return True, "Usuário atualizado com sucesso!"

# Team and player functions
def get_team_name(team_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT name FROM teams WHERE id = ?", (team_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "Unknown Team"

def get_player_name(player_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT name FROM players WHERE id = ?", (player_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else "Unknown Player"

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

# Match functions
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

def add_match(team1_id, team2_id, date, time):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute('''
    INSERT INTO matches (team1_id, team2_id, date, time, status)
    VALUES (?, ?, ?, ?, ?)
    ''', (team1_id, team2_id, date, time, 'upcoming'))
    
    match_id = c.lastrowid
    
    # Create legacy odds for backward compatibility
    team1_win = round(random.uniform(1.5, 3.0), 2)
    draw = round(random.uniform(2.0, 4.0), 2)
    team2_win = round(random.uniform(1.8, 3.5), 2)
    
    c.execute('''
    INSERT INTO odds (match_id, team1_win, draw, team2_win)
    VALUES (?, ?, ?, ?)
    ''', (match_id, team1_win, draw, team2_win))
    
    conn.commit()
    conn.close()
    
    # Create enhanced odds
    create_match_odds(match_id)
    
    return True

def set_match_live(match_id):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("UPDATE matches SET status = 'live' WHERE id = ?", (match_id,))
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
    
    # Process all bets for this match
    process_match_bets(match_id, team1_score, team2_score)
    
    conn.commit()
    conn.close()
    return True

# Odds management functions
def get_odds_categories():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM odds_categories WHERE is_active = 1 ORDER BY name")
    categories = [dict(row) for row in c.fetchall()]
    conn.close()
    return categories

def get_odds_templates(category_id=None):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if category_id:
        c.execute('''
        SELECT ot.*, oc.name as category_name 
        FROM odds_templates ot
        JOIN odds_categories oc ON ot.category_id = oc.id
        WHERE ot.category_id = ? AND ot.is_active = 1
        ORDER BY ot.name
        ''', (category_id,))
    else:
        c.execute('''
        SELECT ot.*, oc.name as category_name 
        FROM odds_templates ot
        JOIN odds_categories oc ON ot.category_id = oc.id
        WHERE ot.is_active = 1
        ORDER BY oc.name, ot.name
        ''')
    
    templates = [dict(row) for row in c.fetchall()]
    conn.close()
    return templates

def get_match_odds(match_id):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
    SELECT mo.*, ot.name as template_name, ot.description, ot.bet_type, ot.requires_player,
           oc.name as category_name, p.name as player_name
    FROM match_odds mo
    JOIN odds_templates ot ON mo.template_id = ot.id
    JOIN odds_categories oc ON ot.category_id = oc.id
    LEFT JOIN players p ON mo.player_id = p.id
    WHERE mo.match_id = ? AND mo.is_active = 1
    ORDER BY oc.name, ot.name, p.name
    ''', (match_id,))
    odds = [dict(row) for row in c.fetchall()]
    conn.close()
    return odds

def create_match_odds(match_id, admin_user="admin"):
    """Create default odds for a match based on templates"""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Get all active templates
    templates = get_odds_templates()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    for template in templates:
        if template['requires_player']:
            # Create odds for each player in the match
            players = get_match_players(match_id)
            for player in players:
                # Add some randomness to player odds
                odds_value = template['default_odds'] + random.uniform(-0.5, 0.5)
                odds_value = max(1.1, round(odds_value, 2))  # Minimum odds of 1.1
                
                c.execute('''
                INSERT INTO match_odds (match_id, template_id, odds_value, player_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''', (match_id, template['id'], odds_value, player['id'], current_time, current_time))
        else:
            # Create general odds with some randomness
            odds_value = template['default_odds'] + random.uniform(-0.3, 0.3)
            odds_value = max(1.1, round(odds_value, 2))  # Minimum odds of 1.1
            
            c.execute('''
            INSERT INTO match_odds (match_id, template_id, odds_value, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (match_id, template['id'], odds_value, current_time, current_time))
    
    conn.commit()
    conn.close()
    return True

def update_match_odds(match_odds_id, new_odds, admin_user, reason=""):
    """Update specific match odds and log the change"""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Get current odds value
    c.execute("SELECT odds_value FROM match_odds WHERE id = ?", (match_odds_id,))
    old_value = c.fetchone()[0]
    
    # Update odds
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
    UPDATE match_odds 
    SET odds_value = ?, updated_at = ?
    WHERE id = ?
    ''', (new_odds, current_time, match_odds_id))
    
    # Log the change
    c.execute('''
    INSERT INTO odds_history (match_odds_id, old_value, new_value, changed_by, changed_at, reason)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (match_odds_id, old_value, new_odds, admin_user, current_time, reason))
    
    conn.commit()
    conn.close()
    return True

def add_custom_odds_template(category_id, name, description, bet_type, default_odds, requires_player=False):
    """Add a new odds template"""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    try:
        c.execute('''
        INSERT INTO odds_templates (category_id, name, description, bet_type, default_odds, requires_player)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (category_id, name, description, bet_type, default_odds, 1 if requires_player else 0))
        
        conn.commit()
        conn.close()
        return True, "Template criado com sucesso!"
    except Exception as e:
        conn.close()
        return False, f"Erro ao criar template: {str(e)}"

# Custom bets functions
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

def add_custom_bet(match_id, description, odds, player_id=None):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    try:
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute('''
        INSERT INTO custom_bets (match_id, description, odds, player_id, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (match_id, description, odds, player_id, 'pending', current_time))
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
            c.execute("UPDATE users SET points = points + ? WHERE username = ?", (winnings, user_id))
            c.execute("UPDATE bets SET status = 'won' WHERE id = ?", (bet_id,))
        else:
            # Losing bet
            c.execute("UPDATE bets SET status = 'lost' WHERE id = ?", (bet_id,))
    
    conn.commit()
    conn.close()
    return True

# Custom bet proposals functions
def get_custom_bet_proposals(status=None):
    """Get custom bet proposals for admin review"""
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    if status:
        c.execute('''
        SELECT cbp.*, u.username, m.team1_id, m.team2_id, m.date, m.time
        FROM custom_bet_proposals cbp
        JOIN users u ON cbp.user_id = u.username
        JOIN matches m ON cbp.match_id = m.id
        WHERE cbp.status = ?
        ORDER BY cbp.created_at DESC
        ''', (status,))
    else:
        c.execute('''
        SELECT cbp.*, u.username, m.team1_id, m.team2_id, m.date, m.time
        FROM custom_bet_proposals cbp
        JOIN users u ON cbp.user_id = u.username
        JOIN matches m ON cbp.match_id = m.id
        ORDER BY cbp.created_at DESC
        ''')
    
    proposals = [dict(row) for row in c.fetchall()]
    conn.close()
    return proposals

def add_custom_bet_proposal(user_id, match_id, description, proposed_odds):
    """User proposes a custom bet"""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        c.execute('''
        INSERT INTO custom_bet_proposals (user_id, match_id, description, proposed_odds, created_at)
        VALUES (?, ?, ?, ?, ?)
        ''', (user_id, match_id, description, proposed_odds, current_time))
        
        conn.commit()
        conn.close()
        return True, "Proposta de aposta enviada para análise!"
    except Exception as e:
        conn.close()
        return False, f"Erro ao enviar proposta: {str(e)}"

def review_custom_bet_proposal(proposal_id, admin_user, action, response="", final_odds=None):
    """Admin reviews and approves/rejects custom bet proposal"""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if action == "approve":
        # Get proposal details
        c.execute("SELECT * FROM custom_bet_proposals WHERE id = ?", (proposal_id,))
        proposal = c.fetchone()
        
        if proposal:
            # Create custom bet
            odds_to_use = final_odds if final_odds else proposal[4]  # proposed_odds
            c.execute('''
            INSERT INTO custom_bets (match_id, description, odds, created_by, created_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (proposal[2], proposal[3], odds_to_use, admin_user, current_time))
            
            # Update proposal status
            c.execute('''
            UPDATE custom_bet_proposals 
            SET status = 'approved', admin_response = ?, reviewed_at = ?
            WHERE id = ?
            ''', (response, current_time, proposal_id))
        
    elif action == "reject":
        c.execute('''
        UPDATE custom_bet_proposals 
        SET status = 'rejected', admin_response = ?, reviewed_at = ?
        WHERE id = ?
        ''', (response, current_time, proposal_id))
    
    conn.commit()
    conn.close()
    return True

# Betting functions
def place_enhanced_bet(username, match_id, bet_type, amount, match_odds_id=None, custom_bet_id=None, player_id=None):
    """Enhanced betting function with better odds tracking"""
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
    
    if match_status not in ['upcoming', 'live']:
        conn.close()
        return False, "Apostas fechadas para este jogo"
    
    # Calculate potential winnings
    potential_winnings = 0
    if match_odds_id:
        c.execute("SELECT odds_value FROM match_odds WHERE id = ?", (match_odds_id,))
        odds = c.fetchone()[0]
        potential_winnings = amount * odds
    elif custom_bet_id:
        c.execute("SELECT odds FROM custom_bets WHERE id = ?", (custom_bet_id,))
        odds = c.fetchone()[0]
        potential_winnings = amount * odds
    
    # Update user points
    c.execute("UPDATE users SET points = points - ? WHERE username = ?", (amount, username))
    
    # Record the bet
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
    INSERT INTO bets (user_id, match_id, bet_type, amount, status, timestamp, 
                     custom_bet_id, player_id, match_odds_id, potential_winnings)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (username, match_id, bet_type, amount, 'pending', timestamp, 
          custom_bet_id, player_id, match_odds_id, potential_winnings))
    
    conn.commit()
    conn.close()
    return True, "Aposta realizada com sucesso!"

def get_user_bets(username):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
    SELECT b.id, b.match_id, b.bet_type, b.amount, b.status, b.timestamp, b.custom_bet_id, 
           b.player_id, b.match_odds_id, b.potential_winnings,
           m.team1_id, m.team2_id, m.date, m.time, m.status as match_status, m.team1_score, m.team2_score
    FROM bets b
    JOIN matches m ON b.match_id = m.id
    WHERE b.user_id = ?
    ORDER BY b.timestamp DESC
    ''', (username,))
    bets = [dict(row) for row in c.fetchall()]
    conn.close()
    return bets

# Legacy function for backward compatibility
def place_bet(username, match_id, bet_type, amount, custom_bet_id=None, player_id=None):
    """Legacy function for backward compatibility"""
    return place_enhanced_bet(username, match_id, bet_type, amount, 
                            custom_bet_id=custom_bet_id, player_id=player_id)

# Bet processing function
def process_match_bets(match_id, team1_score, team2_score):
    """Process all bets when match is completed"""
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    
    # Determine match result
    if team1_score > team2_score:
        match_result = 'team1_win'
    elif team1_score < team2_score:
        match_result = 'team2_win'
    else:
        match_result = 'draw'
    
    total_goals = team1_score + team2_score
    both_scored = team1_score > 0 and team2_score > 0
    
    # Get all pending bets for this match
    c.execute('''
    SELECT b.*, mo.bet_type as enhanced_bet_type, mo.odds_value, mo.player_id as odds_player_id
    FROM bets b
    LEFT JOIN match_odds mo ON b.match_odds_id = mo.id
    WHERE b.match_id = ? AND b.status = 'pending'
    ''', (match_id,))
    
    bets = c.fetchall()
    
    for bet in bets:
        bet_id, user_id, match_id, bet_type, amount, status, timestamp, custom_bet_id, player_id, match_odds_id, potential_winnings = bet[:11]
        
        won = False
        
        if match_odds_id:  # Enhanced bet
            enhanced_bet_type = bet[11]  # enhanced_bet_type
            odds_value = bet[12]  # odds_value
            
            # Check if bet won based on bet type
            if enhanced_bet_type == 'team1_win' and match_result == 'team1_win':
                won = True
            elif enhanced_bet_type == 'team2_win' and match_result == 'team2_win':
                won = True
            elif enhanced_bet_type == 'draw' and match_result == 'draw':
                won = True
            elif enhanced_bet_type == 'double_1x' and match_result in ['team1_win', 'draw']:
                won = True
            elif enhanced_bet_type == 'double_x2' and match_result in ['draw', 'team2_win']:
                won = True
            elif enhanced_bet_type == 'double_12' and match_result in ['team1_win', 'team2_win']:
                won = True
            elif enhanced_bet_type == 'over_2_5' and total_goals > 2.5:
                won = True
            elif enhanced_bet_type == 'under_2_5' and total_goals < 2.5:
                won = True
            elif enhanced_bet_type == 'over_3_5' and total_goals > 3.5:
                won = True
            elif enhanced_bet_type == 'under_1_5' and total_goals < 1.5:
                won = True
            elif enhanced_bet_type == 'both_score_yes' and both_scored:
                won = True
            elif enhanced_bet_type == 'both_score_no' and not both_scored:
                won = True
            elif enhanced_bet_type == 'first_goal_team1' and team1_score > 0:
                won = True  # Simplified logic
            elif enhanced_bet_type == 'first_goal_team2' and team2_score > 0:
                won = True  # Simplified logic
            # Add more bet type logic as needed
            
            if won:
                winnings = int(amount * odds_value)
                c.execute("UPDATE users SET points = points + ? WHERE username = ?", (winnings, user_id))
                c.execute("UPDATE bets SET status = 'won' WHERE id = ?", (bet_id,))
            else:
                c.execute("UPDATE bets SET status = 'lost' WHERE id = ?", (bet_id,))
                
        elif custom_bet_id is None:  # Legacy bet
            # Process legacy bets
            c.execute("SELECT team1_win, draw, team2_win FROM odds WHERE match_id = ?", (match_id,))
            odds = c.fetchone()
            
            if bet_type == match_result:
                odds_value = odds[0] if bet_type == 'team1_win' else odds[1] if bet_type == 'draw' else odds[2]
                winnings = int(amount * odds_value)
                c.execute("UPDATE users SET points = points + ? WHERE username = ?", (winnings, user_id))
                c.execute("UPDATE bets SET status = 'won' WHERE id = ?", (bet_id,))
            else:
                c.execute("UPDATE bets SET status = 'lost' WHERE id = ?", (bet_id,))
    
    conn.commit()
