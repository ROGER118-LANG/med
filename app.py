import streamlit as st
import pandas as pd
import datetime
import uuid
import json
import os
from streamlit_option_menu import option_menu
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import base64
import io

# Page configuration
st.set_page_config(
    page_title="Matheuzinho League - Copa Sub-13 de Futsal",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better aesthetics
st.markdown("""
<style>
    .main .block-container {padding-top: 2rem; padding-bottom: 2rem;}
    h1, h2, h3 {color: #1a2a3a; margin-bottom: 1rem;}
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.6rem 1.2rem;
        transition: all 0.3s;
    }
    .stButton > button:hover {background-color: #3e9142;}
    .css-1aumxhk {background-color: #1e3a5f;}
    .stat-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .matches-card {
        border: 1px solid #eee;
        border-radius: 8px;
        padding: 1rem;
        margin-bottom: 1rem;
        background-color: white;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .highlighted {background-color: #e8f5e9 !important;}
    .sidebar .sidebar-content {background-color: #1a2a3a;}
    
    /* League Logo styling */
    .logo-container {
        text-align: center;
        padding: 1rem;
        background-color: #1a2a3a;
        border-radius: 10px;
        margin-bottom: 1.5rem;
    }
    .logo-title {color: white; margin-bottom: 0;}
    .logo-subtitle {color: #4CAF50; margin-top: 0;}
    
    /* Form styling */
    .form-container {
        background-color: white;
        padding: 2rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state for database storage
if 'db' not in st.session_state:
    # Check if we have a saved database
    if os.path.exists('database.json'):
        with open('database.json', 'r') as f:
            st.session_state.db = json.load(f)
    else:
        # Initialize empty database
        st.session_state.db = {
            'users': [
                {
                    'id': 'admin',
                    'username': 'admin',
                    'password': '2312',
                    'type': 'admin',
                    'name': 'Administrador'
                }
            ],
            'teams': [],
            'players': [],
            'matches': [],
            'bets': [],
            'userBets': [],
            'goals': []
        }

# Function to save database
def save_database():
    with open('database.json', 'w') as f:
        json.dump(st.session_state.db, f)

# Initialize session states
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_type = None
    st.session_state.user_team = None

# Navigation state
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# Helper functions
def get_team_by_id(team_id):
    teams = st.session_state.db['teams']
    for team in teams:
        if team['id'] == team_id:
            return team
    return {'name': 'Time Desconhecido'}

def get_player_by_id(player_id):
    players = st.session_state.db['players']
    for player in players:
        if player['id'] == player_id:
            return player
    return None

def get_match_by_id(match_id):
    matches = st.session_state.db['matches']
    for match in matches:
        if match['id'] == match_id:
            return match
    return None

def get_match_name(match_id):
    match = get_match_by_id(match_id)
    if match:
        return f"{match['teamA']} vs {match['teamB']}"
    return 'Jogo Desconhecido'

def get_bet_by_id(bet_id):
    bets = st.session_state.db['bets']
    for bet in bets:
        if bet['id'] == bet_id:
            return bet
    return None

def get_team_players(team_id):
    if not team_id:
        return []
    return [p for p in st.session_state.db['players'] if p['teamId'] == team_id]

def get_player_goals(player_id):
    goals = [g for g in st.session_state.db['goals'] 
             if g['playerId'] == player_id and (g['type'] == 'normal' or g['type'] == 'penalty')]
    return len(goals)

def format_date(date_string):
    try:
        date = datetime.datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        # Check if date is valid
        if isinstance(date, datetime.datetime):
            return date.strftime('%d/%m/%Y')
        else:
            return 'Data Inválida'
    except:
        return 'Data Inválida'

def get_sorted_teams():
    teams = st.session_state.db['teams']
    return sorted(teams, key=lambda x: (
        -x['points'],
        -(x['goalsFor'] - x['goalsAgainst']),
        -x['goalsFor']
    ))

def get_team_position(team_id):
    sorted_teams = get_sorted_teams()
    for i, team in enumerate(sorted_teams):
        if team['id'] == team_id:
            return i + 1
    return 0

def get_upcoming_matches():
    matches = st.session_state.db['matches']
    return [m for m in matches if not m.get('played', False) and not m.get('cancelled', False)]

def get_completed_matches():
    matches = st.session_state.db['matches']
    return [m for m in matches if m.get('played', False)]

def get_scorers():
    if not st.session_state.db['goals']:
        return []
        
    player_goals = {}
    
    for goal in st.session_state.db['goals']:
        player = get_player_by_id(goal['playerId'])
        if not player:
            continue
            
        if player['id'] not in player_goals:
            team = get_team_by_id(player['teamId'])
            player_goals[player['id']] = {
                'id': player['id'],
                'name': player['name'],
                'teamId': player['teamId'],
                'team': team['name'] if team else 'Desconhecido',
                'goals': {
                    'normal': 0,
                    'penalty': 0,
                    'own': 0,
                    'total': 0
                }
            }
            
        if goal['type'] == 'normal':
            player_goals[player['id']]['goals']['normal'] += 1
            player_goals[player['id']]['goals']['total'] += 1
        elif goal['type'] == 'penalty':
            player_goals[player['id']]['goals']['penalty'] += 1
            player_goals[player['id']]['goals']['total'] += 1
        elif goal['type'] == 'own':
            player_goals[player['id']]['goals']['own'] += 1
            # Own goals don't count for total
    
    # Convert to list and sort
    scorers_list = list(player_goals.values())
    scorers_list.sort(key=lambda x: (
        -x['goals']['total'],
        -x['goals']['normal'],
        -x['goals']['penalty']
    ))
    
    return scorers_list

def get_active_bets():
    return [b for b in st.session_state.db['bets'] if b.get('status') == 'active']

def get_completed_bets():
    return [b for b in st.session_state.db['bets'] 
            if b.get('status') == 'completed' or b.get('status') == 'cancelled']

def login(username, password):
    users = st.session_state.db['users']
    for user in users:
        if user['username'] == username and user['password'] == password:
            st.session_state.logged_in = True
            st.session_state.current_user = user
            st.session_state.user_type = user['type']
            
            if user['type'] == 'team':
                st.session_state.user_team = get_team_by_id(user['teamId'])
            
            return True
    return False

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_type = None
    st.session_state.user_team = None

# Updated UI Components with modern streamlit widgets
def render_sidebar():
    with st.sidebar:
        # Logo
        st.markdown("""
        <div class="logo-container">
            <h2 class="logo-title">MATHEUZINHO</h2>
            <h3 class="logo-subtitle">LEAGUE</h3>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation menu
        if st.session_state.logged_in:
            # User info
            st.markdown(f"**Olá, {st.session_state.current_user['name']}!**")
            st.markdown(f"Tipo: {st.session_state.user_type.capitalize()}")
            
            # Sidebar menu - different options based on user type
            if st.session_state.user_type == 'admin':
                selected = option_menu(
                    "Menu Principal", 
                    ["Início", "Classificação", "Artilharia", "Jogos", "Dashboard", "Times", "Resultados", "Apostas", "Configurações", "Sair"],
                    icons=['house', 'trophy', 'star', 'calendar2', 'speedometer2', 'people', 'clipboard-check', 'currency-exchange', 'gear', 'box-arrow-right'],
                    menu_icon="cast", default_index=0
                )
            elif st.session_state.user_type == 'team':
                selected = option_menu(
                    "Menu Principal", 
                    ["Início", "Classificação", "Artilharia", "Jogos", "Meu Time", "Jogadores", "Estatísticas", "Sair"],
                    icons=['house', 'trophy', 'star', 'calendar2', 'shield', 'person-badge', 'graph-up', 'box-arrow-right'],
                    menu_icon="cast", default_index=0
                )
            else:  # fan
                selected = option_menu(
                    "Menu Principal", 
                    ["Início", "Classificação", "Artilharia", "Jogos", "Minhas Apostas", "Sair"],
                    icons=['house', 'trophy', 'star', 'calendar2', 'cash-coin', 'box-arrow-right'],
                    menu_icon="cast", default_index=0
                )
            
            # Handle menu selection
            if selected == "Sair":
                logout()
                st.rerun()
            else:
                page_mapping = {
                    "Início": "home",
                    "Classificação": "classification",
                    "Artilharia": "topScorers",
                    "Jogos": "matches",
                    "Dashboard": "dashboard",
                    "Times": "teams",
                    "Resultados": "results",
                    "Apostas": "betting",
                    "Configurações": "settings",
                    "Meu Time": "my_team",
                    "Jogadores": "players",
                    "Estatísticas": "stats",
                    "Minhas Apostas": "my_bets"
                }
                st.session_state.page = page_mapping.get(selected, "home")
        else:
            # Login/Register options
            selected = option_menu(
                "Menu Principal", 
                ["Início", "Classificação", "Artilharia", "Jogos", "Login", "Cadastro"],
                icons=['house', 'trophy', 'star', 'calendar2', 'box-arrow-in-right', 'person-plus'],
                menu_icon="cast", default_index=0
            )
            
            # Handle selection
            page_mapping = {
                "Início": "home",
                "Classificação": "classification",
                "Artilharia": "topScorers",
                "Jogos": "matches",
                "Login": "login",
                "Cadastro": "register_choice"
            }
            st.session_state.page = page_mapping.get(selected, "home")

# Add new enhanced rendering functions for each page
def render_home():
    # Create a more visually appealing home page
    st.title("Copa Sub-13 de Futsal")
    
    # Hero section with columns
    col1, col2 = st.columns([3, 2])
    
    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #1a2a3a 0%, #2c3e50 100%); padding: 2rem; border-radius: 10px; color: white;">
            <h2 style="color: white;">Condomínio Terrara</h2>
            <p style="font-size: 1.2rem;">A melhor competição de futsal para jovens talentos!</p>
            <p>Uma oportunidade única para jovens atletas mostrarem seu potencial e desenvolverem suas habilidades em um ambiente competitivo e saudável.</p>
        </div>
        """, unsafe_allow_html=True)
        
        if not st.session_state.logged_in:
            st.write("### Participe!")
            reg_col1, reg_col2 = st.columns(2)
            with reg_col1:
                if st.button("Cadastrar Time", use_container_width=True):
                    st.session_state.page = 'register_team'
                    st.rerun()
            with reg_col2:
                if st.button("Cadastro de Torcedor", use_container_width=True):
                    st.session_state.page = 'register_fan'
                    st.rerun()
    
    with col2:
        # Next matches highlight
        st.markdown("""
        <h3 style="color: #4CAF50;">Próximos Jogos</h3>
        """, unsafe_allow_html=True)
        
        upcoming = get_upcoming_matches()
        if upcoming:
            for i, match in enumerate(upcoming[:3]):
                st.markdown(f"""
                <div class="matches-card {'highlighted' if i == 0 else ''}">
                    <strong>{match['teamA']} vs {match['teamB']}</strong><br>
                    <small>Data: {match['date']}</small>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Não há jogos agendados no momento.")
    
    # League statistics
    st.markdown("---")
    st.subheader("Estatísticas da Liga")
    
    stats_col1, stats_col2, stats_col3, stats_col4 = st.columns(4)
    with stats_col1:
        st.markdown("""
        <div class="stat-card">
            <h4 style="margin-top:0">Times</h4>
            <h2 style="color:#4CAF50; margin-bottom:0">{}</h2>
        </div>
        """.format(len(st.session_state.db['teams'])), unsafe_allow_html=True)
    
    with stats_col2:
        st.markdown("""
        <div class="stat-card">
            <h4 style="margin-top:0">Jogadores</h4>
            <h2 style="color:#4CAF50; margin-bottom:0">{}</h2>
        </div>
        """.format(len(st.session_state.db['players'])), unsafe_allow_html=True)
    
    with stats_col3:
        st.markdown("""
        <div class="stat-card">
            <h4 style="margin-top:0">Jogos Realizados</h4>
            <h2 style="color:#4CAF50; margin-bottom:0">{}</h2>
        </div>
        """.format(len(get_completed_matches())), unsafe_allow_html=True)
    
    with stats_col4:
        # Total goals
        total_goals = len(st.session_state.db['goals'])
        st.markdown("""
        <div class="stat-card">
            <h4 style="margin-top:0">Gols Marcados</h4>
            <h2 style="color:#4CAF50; margin-bottom:0">{}</h2>
        </div>
        """.format(total_goals), unsafe_allow_html=True)
    
    # Top scorers & classification preview
    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Artilheiros")
        scorers = get_scorers()[:5]  # Top 5
        if scorers:
            scorers_df = pd.DataFrame([
                {"Pos": i+1, "Jogador": s['name'], "Time": s['team'], "Gols": s['goals']['total']}
                for i, s in enumerate(scorers)
            ])
            st.table(scorers_df)
        else:
            st.info("Nenhum gol registrado ainda.")
    
    with col2:
        st.subheader("Classificação")
        teams = get_sorted_teams()[:5]  # Top 5
        if teams:
            teams_df = pd.DataFrame([
                {"Pos": i+1, "Time": t['name'], "Pts": t['points'], "J": t['games'], "V": t['wins']}
                for i, t in enumerate(teams)
            ])
            st.table(teams_df)
        else:
            st.info("Nenhum time registrado ainda.")

def render_classification():
    st.title("Classificação")
    
    sorted_teams = get_sorted_teams()
    
    if sorted_teams:
        data = []
        for i, team in enumerate(sorted_teams):
            data.append({
                "Pos": i+1,
                "Time": team['name'],
                "P": team['points'],
                "J": team['games'],
                "V": team['wins'],
                "E": team['draws'],
                "D": team['losses'],
                "GP": team['goalsFor'],
                "GC": team['goalsAgainst'],
                "SG": team['goalsFor'] - team['goalsAgainst']
            })
        
        df = pd.DataFrame(data)
        st.table(df)
    else:
        st.write("Nenhum time cadastrado ainda.")

def render_top_scorers():
    st.title("Artilharia")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Gols Totais", "Gols Normais", "Gols de Pênalti", "Gols Contra"])
    
    scorers = get_scorers()
    
    with tab1:
        if scorers:
            data = []
            for i, player in enumerate(scorers):
                data.append({
                    "Pos": i+1,
                    "Jogador": player['name'],
                    "Time": player['team'],
                    "Gols": player['goals']['total'],
                    "Normais": player['goals']['normal'],
                    "Pênaltis": player['goals']['penalty'],
                    "Contra": player['goals']['own']
                })
            
            df = pd.DataFrame(data)
            st.table(df)
        else:
            st.write("Nenhum gol registrado ainda.")
    
    with tab2:
        if scorers:
            normal_scorers = sorted([p for p in scorers if p['goals']['normal'] > 0], 
                               key=lambda x: -x['goals']['normal'])
            
            data = []
            for i, player in enumerate(normal_scorers):
                data.append({
                    "Pos": i+1,
                    "Jogador": player['name'],
                    "Time": player['team'],
                    "Gols Normais": player['goals']['normal']
                })
            
            if data:
                df = pd.DataFrame(data)
                st.table(df)
            else:
                st.write("Nenhum gol normal registrado ainda.")
        else:
            st.write("Nenhum gol registrado ainda.")
    
    with tab3:
        if scorers:
            penalty_scorers = sorted([p for p in scorers if p['goals']['penalty'] > 0], 
                                key=lambda x: -x['goals']['penalty'])
            
            data = []
            for i, player in enumerate(penalty_scorers):
                data.append({
                    "Pos": i+1,
                    "Jogador": player['name'],
                    "Time": player['team'],
                    "Gols de Pênalti": player['goals']['penalty']
                })
            
            if data:
                df = pd.DataFrame(data)
                st.table(df)
            else:
                st.write("Nenhum gol de pênalti registrado ainda.")
        else:
            st.write("Nenhum gol registrado ainda.")
    
    with tab4:
        if scorers:
            own_scorers = sorted([p for p in scorers if p['goals']['own'] > 0], 
                           key=lambda x: -x['goals']['own'])
            
            data = []
            for i, player in enumerate(own_scorers):
                data.append({
                    "Pos": i+1,
                    "Jogador": player['name'],
                    "Time": player['team'],
                    "Gols Contra": player['goals']['own']
                })
            
            if data:
                df = pd.DataFrame(data)
                st.table(df)
            else:
                st.write("Nenhum gol contra registrado ainda.")
        else:
            st.write("Nenhum gol registrado ainda.")

def render_matches():
    st.title("Jogos")
    
    tab1, tab2 = st.tabs(["Próximos Jogos", "Resultados"])
    
    with tab1:
        upcoming = get_upcoming_matches()
        if upcoming:
            for match in upcoming:
                with st.expander(f"{match['teamA']} vs {match['teamB']} - {match['date']}"):
                    st.write(f"Data: {match['date']}")
                    
                    if st.session_state.user_type == 'fan':
                        if st.button("Apostar", key=f"bet_{match['id']}"):
                            # Show bet modal logic would go here
                            st.write("Funcionalidade de apostas em desenvolvimento")
        else:
            st.write("Não há jogos agendados no momento.")
    
    with tab2:
        completed = get_completed_matches()
        if completed:
            for match in completed:
                with st.expander(f"{match['teamA']} {match['scoreA']} x {match['scoreB']} {match['teamB']} - {match['date']}"):
                    st.write(f"Data: {match['date']}")
                    
                    # Show match goals
                    match_goals = [g for g in st.session_state.db['goals'] if g['matchId'] == match['id']]
                    if match_goals:
                        st.subheader("Gols:")
                        for goal in match_goals:
                            player = get_player_by_id(goal['playerId'])
                            team = get_team_by_id(goal['teamId'])
                            
                            if goal['type'] == 'own':
                                for_team = get_team_by_id(goal['forTeamId'])
                                st.write(f"{player['name']} ({team['name']}) - Gol contra para {for_team['name']}")
                            else:
                                st.write(f"{player['name']} ({team['name']}) - Gol {'de pênalti' if goal['type'] == 'penalty' else 'normal'}")
        else:
            st.write("Nenhum jogo realizado ainda.")

def render_login():
    st.title("Login")
    
    username = st.text_input("Usuário")
    password = st.text_input("Senha", type="password")
    
    if st.button("Entrar"):
        if login(username, password):
            st.session_state.page = 'dashboard'
            st.rerun()
        else:
            st.error("Usuário ou senha incorretos.")
    
    st.write("Ainda não tem conta?")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Cadastrar seu time"):
            st.session_state.page = 'register_team'
            st.rerun()
    
    with col2:
        if st.button("Seja um torcedor"):
            st.session_state.page = 'register_fan'
            st.rerun()

def render_register_team():
    st.title("Cadastrar Time")
    
    with st.form("team_registration_form"):
        team_name = st.text_input("Nome do Time", required=True)
        rep_name = st.text_input("Nome do Representante", required=True)
        rep_phone = st.text_input("Telefone do Representante", required=True)
        username = st.text_input("Nome de Usuário", required=True)
        password = st.text_input("Senha", type="password", required=True)
        
        # Player registration section
        st.subheader("Cadastro de Jogadores (Mínimo 5, Máximo 15)")
        
        num_players = st.slider("Número de Jogadores", min_value=5, max_value=15, value=5)
        
        players = []
        for i in range(num_players):
            st.markdown(f"#### Jogador {i+1}")
            col1, col2 = st.columns(2)
            with col1:
                player_name = st.text_input(f"Nome do Jogador {i+1}", key=f"player_name_{i}")
            with col2:
                player_birth = st.date_input(f"Data de Nascimento {i+1}", 
                                      value=datetime.date.today(), 
                                      key=f"player_birth_{i}")
            
            players.append({"name": player_name, "birthDate": player_birth})
        
        submit_button = st.form_submit_button("Cadastrar Time")
        
        if submit_button:
            # Check if username already exists
            if any(u['username'] == username for u in st.session_state.db['users']):
                st.error("Este nome de usuário já está em uso.")
            elif not team_name or not rep_name or not rep_phone or not username or not password:
                st.error("Todos os campos são obrigatórios.")
            elif any(not player["name"] for player in players):
                st.error("Os nomes de todos os jogadores são obrigatórios.")
            else:
                team_id = f"team_{len(st.session_state.db['teams']) + 1}"
                
                # Create team
                new_team = {
                    'id': team_id,
                    'name': team_name,
                    'representative': {
                        'name': rep_name,
                        'phone': rep_phone
                    },
                    'points': 0,
                    'games': 0,
                    'wins': 0,
                    'draws': 0,
                    'losses': 0,
                    'goalsFor': 0,
                    'goalsAgainst': 0
                }
                
                st.session_state.db['teams'].append(new_team)
                
                # Create user account
                new_user = {
                    'id': team_id,
                    'username': username,
                    'password': password,
                    'type': 'team',
                    'teamId': team_id,
                    'name': team_name
                }
                
                st.session_state.db['users'].append(new_user)
                
                # Register players
                for i, player in enumerate(players):
                    if player["name"]:  # Only add players with names
                        player_id = f"player_{team_id}_{i+1}"
                        
                        # Validate age for U-13
                        birth_date = player["birthDate"]
                        today = datetime.date.today()
                        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
                        
                        if age >= 13:
                            st.warning(f"Jogador {player['name']} tem {age} anos, acima do limite para Sub-13. Cadastrado, mas verifique.")
                        
                        new_player = {
                            'id': player_id,
                            'name': player["name"],
                            'teamId': team_id,
                            'birthDate': player["birthDate"].strftime('%Y-%m-%d')
                        }
                        
                        st.session_state.db['players'].append(new_player)
                
                # Save database
                save_database()
                
                # Auto login
                st.session_state.logged_in = True
                st.session_state.current_user = new_user
                st.session_state.user_type = 'team'
                st.session_state.user_team = new_team
                st.session_state.page = 'dashboard'
                
                st.success("Time cadastrado com sucesso!")
                st.rerun()

def render_register_fan():
    st.title("Cadastro de Torcedor")
    
    with st.form("fan_registration_form"):
        name = st.text_input("Nome Completo", required=True)
        username = st.text_input("Nome de Usuário", required=True)
        password = st.text_input("Senha", type="password", required=True)
        
        teams = st.session_state.db['teams']
        team_options = [team['name'] for team in teams]
        team_ids = [team['id'] for team in teams]
        
        if team_options:
            selected_team_idx = st.selectbox("Time Favorito", 
                                       options=range(len(team_options)),
                                       format_func=lambda x: team_options[x] if x < len(team_options) else "Selecione um time")
        else:
            st.warning("Não há times cadastrados. Seu time favorito será definido posteriormente.")
            selected_team_idx = -1
        
        submit_button = st.form_submit_button("Cadastrar como Torcedor")
        
        if submit_button:
            # Check if username already exists
            if any(u['username'] == username for u in st.session_state.db['users']):
                st.error("Este nome de usuário já está em uso.")
            elif not name or not username or not password:
                st.error("Nome, usuário e senha são obrigatórios.")
            else:
                fan_id = f"fan_{len([u for u in st.session_state.db['users'] if u['type'] == 'fan']) + 1}"
                
                # Create fan account
                new_fan = {
                    'id': fan_id,
                    'username': username,
                    'password': password,
                    'type': 'fan',
                    'name': name,
                    'favoriteTeamId': team_ids[selected_team_idx] if selected_team_idx >= 0 and selected_team_idx < len(team_ids) else None,
                    'points': 1000  # Starting with 1000 Terrara Coins
                }
                
                st.session_state.db['users'].append(new_fan)
                
                # Save database
                save_database()
                
                # Auto login
                st.session_state.logged_in = True
                st.session_state.current_user = new_fan
                st.session_state.user_type = 'fan'
                st.session_state.page = 'dashboard'
                
                st.success("Cadastro realizado com sucesso! Você recebeu 1000 Terrara Coins para começar suas apostas.")
                st.rerun()

def render_dashboard():
    st.title("Painel de Controle")
    
    if not st.session_state.logged_in:
        st.error("Você precisa estar logado para acessar esta página.")
        return
    
    tabs = []
    
    # All user types have overview
    tabs.append("Visão Geral")
    
    # Team specific tabs
    if st.session_state.user_type == 'team':
        tabs.extend(["Meu Time", "Jogadores"])
    
    # Admin specific tabs
    if st.session_state.user_type == 'admin':
        tabs.extend(["Times", "Resultados", "Apostas"])
    
    # Fan specific tabs
    if st.session_state.user_type == 'fan':
        tabs.append("Minhas Apostas")
    
    selected_tab = st.tabs(tabs)
    
    # Overview Tab
    with selected_tab[0]:
        st.header(f"Bem-vindo ao seu Painel, {st.session_state.current_user['name']}")
        
        if st.session_state.user_type == 'team':
            team = st.session_state.user_team
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Jogadores Registrados", 
                          f"{len(get_team_players(team['id']))} / 15")
            
            with col2:
                next_match = next((m for m in get_upcoming_matches() 
                                if m['teamAId'] == team['id'] or m['teamBId'] == team['id']), None)
                if next_match:
                    st.metric("Próximo Jogo", 
                              f"{next_match['teamA']} vs {next_match['teamB']}",
                              next_match['date'])
                else:
                    st.metric("Próximo Jogo", "Nenhum jogo agendado")
            
            with col3:
                st.metric("Posição na Tabela", f"{get_team_position(team['id'])}º")
        
        elif st.session_state.user_type == 'admin':
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total de Times", len(st.session_state.db['teams']))
            
            with col2:
                st.metric("Total de Jogadores", len(st.session_state.db['players']))
            
            with col3:
                st.metric("Jogos Realizados", len(get_completed_matches()))
            
            with col4:
                st.metric("Apostas Ativas", len(get_active_bets()))
        
        elif st.session_state.user_type == 'fan':
            user = st.session_state.current_user
            user_bets = [ub for ub in st.session_state.db['userBets'] if ub['userId'] == user['id']]
            won_bets = [ub for ub in user_bets if 
                       get_bet_by_id(ub['betId']) and get_bet_by_id(ub['betId']).get('result')]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Pontos Disponíveis", user['points'])
            
            with col2:
                st.metric("Apostas Realizadas", len(user_bets))
            
            with col3:
                st.metric("Apostas Ganhas", len(won_bets))
    
    # Team Management Tab
    if st.session_state.user_type == 'team' and len(tabs) > 1:
        with selected_tab[1]:
            st.header("Gerenciar Time")
            
            team = st.session_state.user_team
            
            team_name = st.text_input("Nome do Time", value=team['name'])
            rep_name = st.text_input("Nome do Representante", value=team['representative']['name'])
            rep_phone = st.text_input("Telefone do Representante", value=team['representative']['phone'])
            
            if st.button("Atualizar Informações"):
                team['name'] = team_name
                team['representative']['name'] = rep_name
                team['representative']['phone'] = rep_phone
                
                # Update user name if it's tied to the team
                if st.session_state.current_user and st.session_state.current_user['teamId'] == team['id']:
                    st.session_state.current_user['name'] = team_name
                
                # Save database
                save_database()
                
                st.success("Informações atualizadas com sucesso!")
    
    # Players Management Tab
    if st.session_state.user_type == 'team' and len(tabs) > 2:
        with selected_tab[2]:
            st.header("Gerenciar Jogadores")
            
            team = st.session_state.user_team
            team_players = get_team_players(team['id'])
            
            st.subheader(f"Jogadores Registrados ({len(team_players)}/15)")
            
            if team_players:
                player_data = []
                for player in team_players:
                    player_data.append({
                        "ID": player['id'],
                        "Nome": player['name'],
                        "Data Nascimento": player['birthDate'],
                        "Gols": get_player_goals(player['id'])
                    })
                
                df = pd.DataFrame(player_data)
                player_table = st.dataframe(df)
                
                # Edit and Remove functionality
                selected_player_id = st.selectbox("Selecione um jogador para editar ou remover", 
                                       options=[p['id'] for p in team_players],
                                       format_func=lambda x: next((p['name'] for p in team_players if p['id'] == x), ""))
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if selected_player_id:
                        selected_player = next((p for p in team_players if p['id'] == selected_player_id), None)
                        
                        if selected_player:
                            edit_name = st.text_input("Nome do Jogador", value=selected_player['name'])
                            edit_birth = st.date_input("Data de Nascimento", 
                                                 value=datetime.datetime.strptime(selected_player['birthDate'], '%Y-%m-%d').date() 
                                                 if selected_player['birthDate'] else datetime.date.today())
                            
                            if st.button("Salvar Alterações"):
                                # Find player index in database
                                player_index = next((i for i, p in enumerate(st.session_state.db['players']) 
                                              if p['id'] == selected_player_id), None)
                                
                                if player_index is not None:
                                    st.session_state.db['players'][player_index]['name'] = edit_name
                                    st.session_state.db['players'][player_index]['birthDate'] = edit_birth.strftime('%Y-%m-%d')
                                    
                                    # Save database
                                    save_database()
                                    
                                    st.success("Jogador atualizado com sucesso!")
                                    st.rerun()
                
                with col2:
                    if selected_player_id and st.button("Remover Jogador", type="primary"):
                        # Confirm removal
                        if st.checkbox("Confirma a remoção deste jogador?"):
                            # Find player index in database
                            st.session_state.db['players'] = [p for p in st.session_state.db['players'] if p['id'] != selected_player_id]
                            
                            # Save database
                            save_database()
                            
                            st.success("Jogador removido com sucesso!")
                            st.rerun()
            
            # Add player form
            if len(team_players) < 15:
                st.subheader("Adicionar Jogador")
                
                new_player_name = st.text_input("Nome Completo", key="new_player_name")
                new_player_birth = st.date_input("Data de Nascimento", 
                                           value=datetime.date.today())
                
                if st.button("Adicionar Jogador"):
                    # Validate birth date for sub-13 category
                    today = datetime.date.today()
                    age = today.year - new_player_birth.year - ((today.month, today.day) < (new_player_birth.month, new_player_birth.day))
                    
                    if age >= 13:
                        st.error("O jogador deve ter menos de 13 anos para esta categoria.")
                    elif not new_player_name:
                        st.error("O nome do jogador é obrigatório.")
                    else:
                        player_id = f"player_{team['id']}_{str(uuid.uuid4())[:8]}"
                        
                        new_player = {
                            'id': player_id,
                            'name': new_player_name,
                            'teamId': team['id'],
                            'birthDate': new_player_birth.strftime('%Y-%m-%d')
                        }
                        
                        st.session_state.db['players'].append(new_player)
                        
                        # Save database
                        save_database()
                        
                        st.success("Jogador adicionado com sucesso!")
                        st.rerun()
            else:
                st.warning("Seu time já possui o máximo de 15 jogadores.")
    
    # Teams Management Tab (Admin)
    if st.session_state.user_type == 'admin' and "Times" in tabs:
        with selected_tab[tabs.index("Times")]:
            st.header("Gerenciar Times")
            
            teams = st.session_state.db['teams']
            
            if teams:
                team_data = []
                for team in teams:
                    team_data.append({
                        "ID": team['id'],
                        "Time": team['name'],
                        "Representante": team['representative']['name'],
                        "Contato": team['representative']['phone'],
                        "Jogadores": len(get_team_players(team['id'])),
                        "Pontos": team['points']
                    })
                
                df = pd.DataFrame(team_data)
                team_table = st.dataframe(df)
                
                # Team Actions
                selected_team_id = st.selectbox("Selecione um time", 
                                      options=[t['id'] for t in teams],
                                      format_func=lambda x: next((t['name'] for t in teams if t['id'] == x), ""))
                
                if selected_team_id:
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("Editar Time"):
                            selected_team = next((t for t in teams if t['id'] == selected_team_id), None)
                            
                            if selected_team:
                                edit_team_name = st.text_input("Nome do Time", value=selected_team['name'])
                                edit_rep_name = st.text_input("Nome do Representante", value=selected_team['representative']['name'])
                                edit_rep_phone = st.text_input("Telefone", value=selected_team['representative']['phone'])
                                
                                if st.button("Salvar Alterações do Time"):
                                    # Find team index in database
                                    team_index = next((i for i, t in enumerate(st.session_state.db['teams']) 
                                               if t['id'] == selected_team_id), None)
                                    
                                    if team_index is not None:
                                        st.session_state.db['teams'][team_index]['name'] = edit_team_name
                                        st.session_state.db['teams'][team_index]['representative']['name'] = edit_rep_name
                                        st.session_state.db['teams'][team_index]['representative']['phone'] = edit_rep_phone
                                        
                                        # Update user name if it's tied to the team
                                        team_user = next((u for u in st.session_state.db['users'] if u.get('teamId') == selected_team_id), None)
                                        if team_user:
                                            team_user['name'] = edit_team_name
                                        
                                        # Update match names
                                        for match in st.session_state.db['matches']:
                                            if match['teamAId'] == selected_team_id:
                                                match['teamA'] = edit_team_name
                                            elif match['teamBId'] == selected_team_id:
                                                match['teamB'] = edit_team_name
                                        
                                        # Save database
                                        save_database()
                                        
                                        st.success("Time atualizado com sucesso!")
                                        st.rerun()
                    
                    with col2:
                        if st.button("Ver Jogadores"):
                            selected_team = next((t for t in teams if t['id'] == selected_team_id), None)
                            team_players = get_team_players(selected_team_id)
                            
                            if selected_team and team_players:
                                st.subheader(f"Jogadores do {selected_team['name']}")
                                
                                player_data = []
                                for player in team_players:
                                    player_data.append({
                                        "Nome": player['name'],
                                        "Data Nascimento": player['birthDate'],
                                        "Gols": get_player_goals(player['id'])
                                    })
                                
                                df = pd.DataFrame(player_data)
                                st.dataframe(df)
                            elif selected_team:
                                st.info(f"O time {selected_team['name']} ainda não tem jogadores registrados.")
                    
                    with col3:
                        if st.button("Remover Time", type="primary"):
                            # Confirm removal
                            if st.checkbox("Confirma a remoção deste time? Esta ação não pode ser desfeita."):
                                # Find team index in database
                                team_index = next((i for i, t in enumerate(st.session_state.db['teams']) 
                                           if t['id'] == selected_team_id), None)
                                
                                if team_index is not None:
                                    # Remove team
                                    st.session_state.db['teams'].pop(team_index)
                                    
                                    # Remove team user account
                                    st.session_state.db['users'] = [u for u in st.session_state.db['users'] 
                                                              if not u.get('teamId') == selected_team_id]
                                    
                                    # Remove team players
                                    st.session_state.db['players'] = [p for p in st.session_state.db['players'] 
                                                               if p['teamId'] != selected_team_id]
                                    
                                    # Cancel future matches for this team
                                    for match in st.session_state.db['matches']:
                                        if (match['teamAId'] == selected_team_id or match['teamBId'] == selected_team_id) and not match.get('played', False):
                                            match['cancelled'] = True
                                    
                                    # Save database
                                    save_database()
                                    
                                    st.success("Time removido com sucesso!")
                                    st.rerun()
                
                # Add new team
                st.subheader("Adicionar Novo Time")
                
                new_team_name = st.text_input("Nome do Time", key="new_team_name")
                new_rep_name = st.text_input("Nome do Representante", key="new_rep_name")
                new_rep_phone = st.text_input("Telefone", key="new_rep_phone")
                new_username = st.text_input("Nome de Usuário", key="new_username")
                new_password = st.text_input("Senha", type="password", key="new_password")
                
                if st.button("Adicionar Time"):
                    # Check if username already exists
                    if any(u['username'] == new_username for u in st.session_state.db['users']):
                        st.error("Este nome de usuário já está em uso.")
                    elif not new_team_name or not new_rep_name or not new_rep_phone or not new_username or not new_password:
                        st.error("Todos os campos são obrigatórios.")
                    else:
                        team_id = f"team_{len(st.session_state.db['teams']) + 1}"
                        
                        # Create team
                        new_team = {
                            'id': team_id,
                            'name': new_team_name,
                            'representative': {
                                'name': new_rep_name,
                                'phone': new_rep_phone
                            },
                            'points': 0,
                            'games': 0,
                            'wins': 0,
                            'draws': 0,
                            'losses': 0,
                            'goalsFor': 0,
                            'goalsAgainst': 0
                        }
                        
                        st.session_state.db['teams'].append(new_team)
                        
                        # Create user account
                        new_user = {
                            'id': team_id,
                            'username': new_username,
                            'password': new_password,
                            'type': 'team',
                            'teamId': team_id,
                            'name': new_team_name
                        }
                        
                        st.session_state.db['users'].append(new_user)
                        
                        # Save database
                        save_database()
                        
                        st.success("Time adicionado com sucesso!")
                        st.rerun()
            else:
                st.info("Nenhum time cadastrado ainda.")
                
                # Add new team form here
    
    # Results Management Tab (Admin)
    if st.session_state.user_type == 'admin' and "Resultados" in tabs:
        with selected_tab[tabs.index("Resultados")]:
            st.header("Gerenciar Resultados")
            
            subtab1, subtab2, subtab3 = st.tabs(["Próximos Jogos", "Jogos Completos", "Agendar Jogo"])
            
            with subtab1:
                upcoming = get_upcoming_matches()
                
                if upcoming:
                    for match in upcoming:
                        with st.expander(f"{match['teamA']} vs {match['teamB']} - {match['date']}"):
                            st.write(f"Data: {match['date']}")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("Adicionar Resultado", key=f"add_result_{match['id']}"):
                                    st.session_state.selected_match = match
                                    
                                    score_a = st.number_input(f"Gols {match['teamA']}", min_value=0, value=0, key=f"score_a_{match['id']}")
                                    score_b = st.number_input(f"Gols {match['teamB']}", min_value=0, value=0, key=f"score_b_{match['id']}")
                                    
                                    # Goals for team A
                                    st.subheader(f"Gols de {match['teamA']}")
                                    team_a_players = get_team_players(match['teamAId'])
                                    
                                    goals_a = []
                                    for i in range(score_a):
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            player_a = st.selectbox(f"Jogador {i+1}", 
                                                           options=[p['id'] for p in team_a_players],
                                                           format_func=lambda x: next((p['name'] for p in team_a_players if p['id'] == x), ""),
                                                           key=f"player_a_{match['id']}_{i}")
                                        with col2:
                                            goal_type_a = st.selectbox(f"Tipo de Gol {i+1}", 
                                                              options=["normal", "penalty"],
                                                              format_func=lambda x: "Gol normal" if x == "normal" else "Pênalti",
                                                              key=f"goal_type_a_{match['id']}_{i}")
                                        
                                        goals_a.append({"playerId": player_a, "type": goal_type_a})
                                    
                                    # Goals for team B
                                    st.subheader(f"Gols de {match['teamB']}")
                                    team_b_players = get_team_players(match['teamBId'])
                                    
                                    goals_b = []
                                    for i in range(score_b):
                                        col1, col2 = st.columns(2)
                                        with col1:
                                            player_b = st.selectbox(f"Jogador {i+1}", 
                                                           options=[p['id'] for p in team_b_players],
                                                           format_func=lambda x: next((p['name'] for p in team_b_players if p['id'] == x), ""),
                                                           key=f"player_b_{match['id']}_{i}")
                                        with col2:
                                            goal_type_b = st.selectbox(f"Tipo de Gol {i+1}", 
                                                              options=["normal", "penalty"],
                                                              format_func=lambda x: "Gol normal" if x == "normal" else "Pênalti",
                                                              key=f"goal_type_b_{match['id']}_{i}")
                                        
                                        goals_b.append({"playerId": player_b, "type": goal_type_b})
                                    
                                    # Own goals
                                    st.subheader("Gols Contra")
                                    add_own_goal = st.checkbox("Adicionar gol contra", key=f"add_own_goal_{match['id']}")
                                    
                                    own_goals = []
                                    if add_own_goal:
                                        all_players = team_a_players + team_b_players
                                        
                                        own_goal_count = st.number_input("Número de gols contra", min_value=1, value=1, key=f"own_goal_count_{match['id']}")
                                        
                                        for i in range(own_goal_count):
                                            col1, col2 = st.columns(2)
                                            with col1:
                                                player_own = st.selectbox(f"Jogador (gol contra) {i+1}", 
                                                               options=[p['id'] for p in all_players],
                                                               format_func=lambda x: next((p['name'] for p in all_players if p['id'] == x), ""),
                                                               key=f"player_own_{match['id']}_{i}")
                                            with col2:
                                                for_team = st.selectbox(f"Gol para {i+1}", 
                                                             options=[match['teamAId'], match['teamBId']],
                                                             format_func=lambda x: match['teamA'] if x == match['teamAId'] else match['teamB'],
                                                             key=f"for_team_{match['id']}_{i}")
                                            
                                            own_goals.append({"playerId": player_own, "forTeam": for_team})
                                    
                                    if st.button("Salvar Resultado", key=f"save_result_{match['id']}"):
                                        # Find match in database
                                        match_index = next((i for i, m in enumerate(st.session_state.db['matches']) 
                                                    if m['id'] == match['id']), None)
                                        
                                        if match_index is not None:
                                            # Update match data
                                            st.session_state.db['matches'][match_index]['scoreA'] = score_a
                                            st.session_state.db['matches'][match_index]['scoreB'] = score_b
                                            st.session_state.db['matches'][match_index]['played'] = True
                                            
                                            # Update team stats
                                            team_a = next((t for t in st.session_state.db['teams'] if t['id'] == match['teamAId']), None)
                                            team_b = next((t for t in st.session_state.db['teams'] if t['id'] == match['teamBId']), None)
                                            
                                            if team_a and team_b:
                                                team_a['games'] += 1
                                                team_b['games'] += 1
                                                
                                                team_a['goalsFor'] += score_a
                                                team_a['goalsAgainst'] += score_b
                                                
                                                team_b['goalsFor'] += score_b
                                                team_b['goalsAgainst'] += score_a
                                                
                                                if score_a > score_b:
                                                    team_a['wins'] += 1
                                                    team_b['losses'] += 1
                                                    team_a['points'] += 3
                                                elif score_a < score_b:
                                                    team_b['wins'] += 1
                                                    team_a['losses'] += 1
                                                    team_b['points'] += 3
                                                else:
                                                    team_a['draws'] += 1
                                                    team_b['draws'] += 1
                                                    team_a['points'] += 1
                                                    team_b['points'] += 1
                                            
                                            # Add goals
                                            # Remove existing goals for this match first
                                            st.session_state.db['goals'] = [g for g in st.session_state.db['goals'] if g['matchId'] != match['id']]
                                            
                                            # Add team A goals
                                            for i, goal in enumerate(goals_a):
                                                if goal['playerId']:
                                                    st.session_state.db['goals'].append({
                                                        'id': f"goal_{match['id']}_A_{i}",
                                                        'matchId': match['id'],
                                                        'playerId': goal['playerId'],
                                                        'teamId': match['teamAId'],
                                                        'type': goal['type']
                                                    })
                                            
                                            # Add team B goals
                                            for i, goal in enumerate(goals_b):
                                                if goal['playerId']:
                                                    st.session_state.db['goals'].append({
                                                        'id': f"goal_{match['id']}_B_{i}",
                                                        'matchId': match['id'],
                                                        'playerId': goal['playerId'],
                                                        'teamId': match['teamBId'],
                                                        'type': goal['type']
                                                    })
                                            
                                            # Add own goals
                                            for i, goal in enumerate(own_goals):
                                                if goal['playerId']:
                                                    player = get_player_by_id(goal['playerId'])
                                                    if player:
                                                        st.session_state.db['goals'].append({
                                                            'id': f"owngoal_{match['id']}_{i}",
                                                            'matchId': match['id'],
                                                            'playerId': goal['playerId'],
                                                            'teamId': player['teamId'],
                                                            'type': 'own',
                                                            'forTeamId': goal['forTeam']
                                                        })
                                            
                                            # Save database
                                            save_database()
                                            
                                            st.success("Resultado registrado com sucesso!")
                                            st.rerun()
                            
                            with col2:
                                if st.button("Cancelar Jogo", key=f"cancel_{match['id']}"):
                                    if st.checkbox(f"Confirma o cancelamento do jogo {match['teamA']} vs {match['teamB']}?"):
                                        # Find match index in database
                                        st.session_state.db['matches'] = [m for m in st.session_state.db['matches'] if m['id'] != match['id']]
                                        
                                        # Save database
                                        save_database()
                                        
                                        st.success("Jogo cancelado com sucesso!")
                                        st.rerun()
                else:
                    st.info("Não há jogos agendados no momento.")
            
            with subtab2:
                completed = get_completed_matches()
                
                if completed:
                    for match in completed:
                        with st.expander(f"{match['teamA']} {match['scoreA']} x {match['scoreB']} {match['teamB']} - {match['date']}"):
                            st.write(f"Data: {match['date']}")
                            
                            # Show match goals
                            match_goals = [g for g in st.session_state.db['goals'] if g['matchId'] == match['id']]
                            if match_goals:
                                st.subheader("Gols:")
                                for goal in match_goals:
                                    player = get_player_by_id(goal['playerId'])
                                    team = get_team_by_id(goal['teamId'])
                                    
                                    if goal['type'] == 'own':
                                        for_team = get_team_by_id(goal['forTeamId'])
                                        st.write(f"{player['name']} ({team['name']}) - Gol contra para {for_team['name']}")
                                    else:
                                        st.write(f"{player['name']} ({team['name']}) - Gol {'de pênalti' if goal['type'] == 'penalty' else 'normal'}")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("Editar Resultado", key=f"edit_{match['id']}"):
                                    st.write("Funcionalidade em desenvolvimento - Próxima versão")
                else:
                    st.info("Nenhum jogo realizado ainda.")
            
            with subtab3:
                st.subheader("Agendar Novo Jogo")
                
                teams = st.session_state.db['teams']
                
                team_a_idx = st.selectbox("Time A", 
                                   options=range(len(teams)),
                                   format_func=lambda x: teams[x]['name'] if x < len(teams) else "Selecione um time")
                
                team_b_idx = st.selectbox("Time B", 
                                   options=range(len(teams)),
                                   format_func=lambda x: teams[x]['name'] if x < len(teams) else "Selecione um time")
                
                match_date = st.date_input("Data do Jogo", 
                                    value=datetime.date.today())
                
                match_time = st.time_input("Horário", 
                                    value=datetime.time(15, 0))
                
                if st.button("Agendar Jogo"):
                    if team_a_idx == team_b_idx:
                        st.error("Os times devem ser diferentes.")
                    elif team_a_idx >= len(teams) or team_b_idx >= len(teams):
                        st.error("Selecione times válidos.")
                    else:
                        team_a = teams[team_a_idx]
                        team_b = teams[team_b_idx]
                        
                        match_datetime = datetime.datetime.combine(match_date, match_time)
                        formatted_date = match_datetime.strftime('%d/%m/%Y %H:%M')
                        
                        new_match = {
                            'id': f"match_{len(st.session_state.db['matches']) + 1}",
                            'teamAId': team_a['id'],
                            'teamBId': team_b['id'],
                            'teamA': team_a['name'],
                            'teamB': team_b['name'],
                            'date': formatted_date,
                            'played': False
                        }
                        
                        st.session_state.db['matches'].append(new_match)
                        
                        # Save database
                        save_database()
                        
                        st.success("Jogo agendado com sucesso!")
                        st.rerun()

def render_register_choice():
    st.title("Escolha o tipo de cadastro")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Cadastrar Time", use_container_width=True):
            st.session_state.page = 'register_team'
            st.rerun()
    
    with col2:
        if st.button("Cadastro de Torcedor", use_container_width=True):
            st.session_state.page = 'register_fan'
            st.rerun()

def render_settings():
    st.title("Configurações")
    
    if not st.session_state.logged_in or st.session_state.user_type != 'admin':
        st.error("Acesso restrito ao administrador.")
        return
    
    st.subheader("Configurações do Sistema")
    
    # Backup and restore
    if st.button("Fazer Backup do Banco de Dados"):
        with open('database_backup.json', 'w') as f:
            json.dump(st.session_state.db, f)
        st.success("Backup realizado com sucesso!")
    
    # Reset database
    if st.button("Limpar todos os dados", type="primary"):
        if st.checkbox("Confirma que deseja limpar todos os dados? Esta ação não pode ser desfeita."):
            st.session_state.db = {
                'users': [
                    {
                        'id': 'admin',
                        'username': 'admin',
                        'password': '2312',
                        'type': 'admin',
                        'name': 'Administrador'
                    }
                ],
                'teams': [],
                'players': [],
                'matches': [],
                'bets': [],
                'userBets': [],
                'goals': []
            }
            save_database()
            st.success("Banco de dados limpo com sucesso!")
            st.rerun()

def render_betting():
    st.title("Gerenciar Apostas")
    
    if not st.session_state.logged_in or st.session_state.user_type != 'admin':
        st.error("Acesso restrito ao administrador.")
        return
    
    subtab1, subtab2, subtab3 = st.tabs(["Apostas Ativas", "Criar Aposta", "Histórico"])
    
    with subtab1:
        active_bets = get_active_bets()
        
        if active_bets:
            for bet in active_bets:
                with st.expander(bet['description']):
                    st.write(f"Odd: {bet['odd']}")
                    if bet.get('matchId'):
                        st.write(f"Jogo: {get_match_name(bet['matchId'])}")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        if st.button("Finalizar (Ganhou)", key=f"win_{bet['id']}"):
                            # Resolve bet as won
                            bet_index = next((i for i, b in enumerate(st.session_state.db['bets']) 
                                      if b['id'] == bet['id']), None)
                            
                            if bet_index is not None:
                                st.session_state.db['bets'][bet_index]['status'] = 'completed'
                                st.session_state.db['bets'][bet_index]['result'] = True
                                st.session_state.db['bets'][bet_index]['resolvedAt'] = datetime.datetime.now().isoformat()
                                
                                # Process payouts
                                bet_participants = [ub for ub in st.session_state.db['userBets'] if ub['betId'] == bet['id']]
                                
                                for user_bet in bet_participants:
                                    user_index = next((i for i, u in enumerate(st.session_state.db['users']) 
                                               if u['id'] == user_bet['userId']), None)
                                    
                                    if user_index is not None:
                                        winnings = int(user_bet['amount'] * bet['odd'])
                                        st.session_state.db['users'][user_index]['points'] += winnings
                                
                                save_database()
                                st.success("Aposta finalizada como ganha!")
                                st.rerun()
                    
                    with col2:
                        if st.button("Finalizar (Perdeu)", key=f"lose_{bet['id']}"):
                            # Resolve bet as lost
                            bet_index = next((i for i, b in enumerate(st.session_state.db['bets']) 
                                      if b['id'] == bet['id']), None)
                            
                            if bet_index is not None:
                                st.session_state.db['bets'][bet_index]['status'] = 'completed'
                                st.session_state.db['bets'][bet_index]['result'] = False
                                st.session_state.db['bets'][bet_index]['resolvedAt'] = datetime.datetime.now().isoformat()
                                
                                save_database()
                                st.success("Aposta finalizada como perdida!")
                                st.rerun()
                    
                    with col3:
                        if st.button("Editar", key=f"edit_{bet['id']}"):
                            new_odd = st.number_input(f"Nova odd para {bet['description']}", 
                                              min_value=1.0, value=float(bet['odd']), step=0.1)
                            
                            if st.button("Atualizar Odd"):
                                bet_index = next((i for i, b in enumerate(st.session_state.db['bets']) 
                                          if b['id'] == bet['id']), None)
                                
                                if bet_index is not None:
                                    st.session_state.db['bets'][bet_index]['odd'] = new_odd
                                    save_database()
                                    st.success("Odd atualizada com sucesso!")
                                    st.rerun()
        else:
            st.info("Não há apostas ativas no momento.")
    
    with subtab2:
        st.subheader("Criar Nova Aposta")
        
        bet_type = st.selectbox("Tipo de Aposta", 
                       options=["match", "team", "custom"],
                       format_func=lambda x: "Resultado de Jogo" if x == "match" else 
                                          "Time Específico" if x == "team" else "Personalizada")
        
        if bet_type == "match":
            upcoming = get_upcoming_matches()
            match_options = [m['id'] for m in upcoming]
            match_display = [f"{m['teamA']} vs {m['teamB']} ({m['date']})" for m in upcoming]
            
            if match_options:
                match_idx = st.selectbox("Jogo", 
                                options=range(len(match_options)),
                                format_func=lambda x: match_display[x] if x < len(match_display) else "Selecione um jogo")
                
                if match_idx < len(match_options):
                    match_id = match_options[match_idx]
                    match = get_match_by_id(match_id)
                    
                    outcome = st.selectbox("Resultado", 
                                  options=["teamA", "draw", "teamB"],
                                  format_func=lambda x: f"{match['teamA']} vence" if x == "teamA" else 
                                                     "Empate" if x == "draw" else f"{match['teamB']} vence")
                    
                    description = ""
                    if outcome == "teamA":
                        description = f"{match['teamA']} vence {match['teamB']}"
                    elif outcome == "draw":
                        description = f"Empate entre {match['teamA']} e {match['teamB']}"
                    else:
                        description = f"{match['teamB']} vence {match['teamA']}"
            else:
                st.warning("Não há jogos futuros para criar apostas.")
                match_id = None
                description = ""
        
        elif bet_type == "team":
            teams = st.session_state.db['teams']
            team_options = [t['id'] for t in teams]
            
            if team_options:
                team_idx = st.selectbox("Time", 
                                options=range(len(team_options)),
                                format_func=lambda x: next((t['name'] for t in teams if t['id'] == team_options[x]), "") 
                                         if x < len(team_options) else "Selecione um time")
                
                if team_idx < len(team_options):
                    team_id = team_options[team_idx]
                    team = get_team_by_id(team_id)
                    
                    custom_desc = st.text_input("Descrição da Aposta (Ex: Será campeão)")
                    description = f"{team['name']} {custom_desc}"
                    match_id = None
            else:
                st.warning("Não há times cadastrados para criar apostas.")
                description = ""
                match_id = None
        
        else:  # custom
            description = st.text_input("Descrição da Aposta (Ex: Haverá um gol contra na rodada)")
            match_id = None
        
        odd = st.number_input("Odd (multiplicador)", min_value=1.0, value=2.0, step=0.1)
        
        if st.button("Criar Aposta"):
            if not description:
                st.error("É necessário fornecer uma descrição para a aposta.")
            else:
                new_bet = {
                    'id': f"bet_{len(st.session_state.db['bets']) + 1}",
                    'description': description,
                    'odd': odd,
                    'matchId': match_id,
                    'status': 'active',
                    'createdAt': datetime.datetime.now().isoformat()
                }
                
                st.session_state.db['bets'].append(new_bet)
                save_database()
                
                st.success("Aposta criada com sucesso!")
                st.rerun()
    
    with subtab3:
        completed_bets = get_completed_bets()
        
        if completed_bets:
            bet_data = []
            for bet in completed_bets:
                participants = [ub for ub in st.session_state.db['userBets'] if ub['betId'] == bet['id']]
                total_amount = sum(ub['amount'] for ub in participants)
                
                bet_data.append({
                    "Descrição": bet['description'],
                    "Odd": bet['odd'],
                    "Status": bet['status'],
                    "Participantes": len(participants),
                    "Total Apostado": total_amount,
                    "Resultado": "Ganhou" if bet.get('result') else "Perdeu" if bet['status'] == 'completed' else "Cancelada"
                })
            
            df = pd.DataFrame(bet_data)
            st.dataframe(df)
        else:
            st.info("Não há histórico de apostas finalizadas.")

def render_teams():
    st.title("Gerenciar Times")
    
    if not st.session_state.logged_in or st.session_state.user_type != 'admin':
        st.error("Acesso restrito ao administrador.")
        return
    
    teams = st.session_state.db['teams']
    
    if teams:
        team_data = []
        for team in teams:
            team_data.append({
                "ID": team['id'],
                "Time": team['name'],
                "Representante": team['representative']['name'],
                "Contato": team['representative']['phone'],
                "Jogadores": len(get_team_players(team['id'])),
                "Pontos": team['points']
            })
        
        df = pd.DataFrame(team_data)
        st.dataframe(df)
        
        # Team Actions
        selected_team_id = st.selectbox("Selecione um time para gerenciar", 
                              options=[t['id'] for t in teams],
                              format_func=lambda x: next((t['name'] for t in teams if t['id'] == x), ""))
        
        if selected_team_id:
            tab1, tab2, tab3 = st.tabs(["Informações do Time", "Jogadores", "Estatísticas"])
            
            with tab1:
                selected_team = next((t for t in teams if t['id'] == selected_team_id), None)
                
                if selected_team:
                    with st.form("edit_team_form"):
                        edit_team_name = st.text_input("Nome do Time", value=selected_team['name'])
                        edit_rep_name = st.text_input("Nome do Representante", value=selected_team['representative']['name'])
                        edit_rep_phone = st.text_input("Telefone", value=selected_team['representative']['phone'])
                        
                        edit_submit = st.form_submit_button("Atualizar Informações")
                        
                        if edit_submit:
                            # Find team index in database
                            team_index = next((i for i, t in enumerate(st.session_state.db['teams']) 
                                       if t['id'] == selected_team_id), None)
                            
                            if team_index is not None:
                                st.session_state.db['teams'][team_index]['name'] = edit_team_name
                                st.session_state.db['teams'][team_index]['representative']['name'] = edit_rep_name
                                st.session_state.db['teams'][team_index]['representative']['phone'] = edit_rep_phone
                                
                                # Update user name if it's tied to the team
                                team_user = next((u for u in st.session_state.db['users'] if u.get('teamId') == selected_team_id), None)
                                if team_user:
                                    team_user['name'] = edit_team_name
                                
                                # Update match names
                                for match in st.session_state.db['matches']:
                                    if match['teamAId'] == selected_team_id:
                                        match['teamA'] = edit_team_name
                                    elif match['teamBId'] == selected_team_id:
                                        match['teamB'] = edit_team_name
                                
                                # Save database
                                save_database()
                                
                                st.success("Time atualizado com sucesso!")
                                st.rerun()
            
            with tab2:
                team_players = get_team_players(selected_team_id)
                
                if team_players:
                    player_data = []
                    for player in team_players:
                        player_data.append({
                            "ID": player['id'],
                            "Nome": player['name'],
                            "Data Nascimento": player['birthDate'],
                            "Idade": calculate_age(player['birthDate']),
                            "Gols": get_player_goals(player['id'])
                        })
                    
                    st.dataframe(player_data)
                    
                    # Edit player
                    st.subheader("Gerenciar Jogador")
                    
                    selected_player_id = st.selectbox("Selecione um jogador", 
                                             options=[p['id'] for p in team_players],
                                             format_func=lambda x: next((p['name'] for p in team_players if p['id'] == x), ""))
                    
                    if selected_player_id:
                        selected_player = next((p for p in team_players if p['id'] == selected_player_id), None)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            with st.form("edit_player_form"):
                                edit_player_name = st.text_input("Nome do Jogador", value=selected_player['name'])
                                edit_player_birth = st.date_input("Data de Nascimento", 
                                                          value=datetime.datetime.strptime(selected_player['birthDate'], '%Y-%m-%d').date())
                                
                                edit_player_submit = st.form_submit_button("Atualizar Jogador")
                                
                                if edit_player_submit:
                                    # Find player index in database
                                    player_index = next((i for i, p in enumerate(st.session_state.db['players']) 
                                                 if p['id'] == selected_player_id), None)
                                    
                                    if player_index is not None:
                                        st.session_state.db['players'][player_index]['name'] = edit_player_name
                                        st.session_state.db['players'][player_index]['birthDate'] = edit_player_birth.strftime('%Y-%m-%d')
                                        
                                        # Save database
                                        save_database()
                                        
                                        st.success("Jogador atualizado com sucesso!")
                                        st.rerun()
                        
                        with col2:
                            if st.button("Remover Jogador", key=f"remove_{selected_player_id}"):
                                # Confirm removal
                                if st.checkbox("Confirma a remoção deste jogador?"):
                                    # Remove player
                                    st.session_state.db['players'] = [p for p in st.session_state.db['players'] if p['id'] != selected_player_id]
                                    
                                    # Save database
                                    save_database()
                                    
                                    st.success("Jogador removido com sucesso!")
                                    st.rerun()
                
                # Add new player
                st.subheader("Adicionar Novo Jogador")
                with st.form("add_player_form"):
                    new_player_name = st.text_input("Nome do Jogador", key="new_player_admin")
                    new_player_birth = st.date_input("Data de Nascimento", key="new_birth_admin")
                    
                    add_player_submit = st.form_submit_button("Adicionar Jogador")
                    
                    if add_player_submit:
                        if not new_player_name:
                            st.error("O nome do jogador é obrigatório.")
                        elif len(team_players) >= 15:
                            st.error("Este time já possui o máximo de 15 jogadores permitidos.")
                        else:
                            # Validate age for U-13
                            today = datetime.date.today()
                            age = today.year - new_player_birth.year - ((today.month, today.day) < (new_player_birth.month, new_player_birth.day))
                            
                            if age >= 13:
                                st.warning(f"Este jogador tem {age} anos, acima do limite para Sub-13. Cadastrado, mas verifique.")
                            
                            player_id = f"player_{selected_team_id}_{str(uuid.uuid4())[:8]}"
                            
                            # Add player
                            new_player = {
                                'id': player_id,
                                'name': new_player_name,
                                'teamId': selected_team_id,
                                'birthDate': new_player_birth.strftime('%Y-%m-%d')
                            }
                            
                            st.session_state.db['players'].append(new_player)
                            
                            # Save database
                            save_database()
                            
                            st.success("Jogador adicionado com sucesso!")
                            st.rerun()
            
            with tab3:
                selected_team = next((t for t in teams if t['id'] == selected_team_id), None)
                
                if selected_team:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Pontos", selected_team['points'])
                        st.metric("Jogos", selected_team['games'])
                        st.metric("Vitórias", selected_team['wins'])
                    
                    with col2:
                        st.metric("Empates", selected_team['draws'])
                        st.metric("Derrotas", selected_team['losses'])
                        st.metric("Saldo de Gols", selected_team['goalsFor'] - selected_team['goalsAgainst'])
                    
                    # Show recent matches
                    st.subheader("Jogos Recentes")
                    recent_matches = [m for m in st.session_state.db['matches'] 
                                    if (m['teamAId'] == selected_team_id or m['teamBId'] == selected_team_id) 
                                    and m.get('played', False)]
                    
                    if recent_matches:
                        for match in recent_matches[:5]:  # Show last 5 matches
                            if match['teamAId'] == selected_team_id:
                                result = "Vitória" if match['scoreA'] > match['scoreB'] else "Derrota" if match['scoreA'] < match['scoreB'] else "Empate"
                                score = f"{match['scoreA']} x {match['scoreB']}"
                                opponent = match['teamB']
                            else:
                                result = "Vitória" if match['scoreB'] > match['scoreA'] else "Derrota" if match['scoreB'] < match['scoreA'] else "Empate"
                                score = f"{match['scoreB']} x {match['scoreA']}"
                                opponent = match['teamA']
                            
                            st.markdown(f"**{result}** contra {opponent}: {score} ({match['date']})")
                    else:
                        st.info("Nenhum jogo realizado ainda.")
    else:
        st.info("Nenhum time cadastrado ainda.")
        
        # Add new team form
        st.subheader("Adicionar Novo Time")
        
        with st.form("add_team_form"):
            new_team_name = st.text_input("Nome do Time")
            new_rep_name = st.text_input("Nome do Representante")
            new_rep_phone = st.text_input("Telefone")
            new_username = st.text_input("Nome de Usuário")
            new_password = st.text_input("Senha", type="password")
            
            add_team_submit = st.form_submit_button("Adicionar Time")
            
            if add_team_submit:
                # Check if username already exists
                if any(u['username'] == new_username for u in st.session_state.db['users']):
                    st.error("Este nome de usuário já está em uso.")
                elif not new_team_name or not new_rep_name or not new_rep_phone or not new_username or not new_password:
                    st.error("Todos os campos são obrigatórios.")
                else:
                    team_id = f"team_{len(st.session_state.db['teams']) + 1}"
                    
                    # Create team
                    new_team = {
                        'id': team_id,
                        'name': new_team_name,
                        'representative': {
                            'name': new_rep_name,
                            'phone': new_rep_phone
                        },
                        'points': 0,
                        'games': 0,
                        'wins': 0,
                        'draws': 0,
                        'losses': 0,
                        'goalsFor': 0,
                        'goalsAgainst': 0
                    }
                    
                    st.session_state.db['teams'].append(new_team)
                    
                    # Create user account
                    new_user = {
                        'id': team_id,
                        'username': new_username,
                        'password': new_password,
                        'type': 'team',
                        'teamId': team_id,
                        'name': new_team_name
                    }
                    
                    st.session_state.db['users'].append(new_user)
                    
                    # Save database
                    save_database()
                    
                    st.success("Time adicionado com sucesso!")
                    st.rerun()

# Helper function to calculate age from birthdate string
def calculate_age(birthdate_str):
    try:
        birthdate = datetime.datetime.strptime(birthdate_str, '%Y-%m-%d').date()
        today = datetime.date.today()
        age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))
        return age
    except:
        return "N/A"

def render_my_bets():
    st.title("Minhas Apostas")
    
    if not st.session_state.logged_in or st.session_state.user_type != 'fan':
        st.error("Você precisa estar logado como torcedor para ver suas apostas.")
        return
    
    user = st.session_state.current_user
    st.subheader(f"Pontos disponíveis: {user['points']} Terrara Coins")
    
    subtab1, subtab2, subtab3 = st.tabs(["Apostas Ativas", "Histórico", "Apostar"])
    
    with subtab1:
        user_bets = [ub for ub in st.session_state.db['userBets'] if ub['userId'] == user['id']]
        active_user_bets = [ub for ub in user_bets if get_bet_by_id(ub['betId']) and get_bet_by_id(ub['betId']).get('status') == 'active']
        
        if active_user_bets:
            for user_bet in active_user_bets:
                bet = get_bet_by_id(user_bet['betId'])
                if bet:
                    st.markdown(f"""
                    <div class="bet-card">
                        <h4>{bet['description']}</h4>
                        <p>Odd: {bet['odd']}</p>
                        <p>Valor Apostado: {user_bet['amount']} Terrara Coins</p>
                        <p>Possível Retorno: {int(user_bet['amount'] * bet['odd'])} Terrara Coins</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Você não tem apostas ativas no momento.")
    
    with subtab2:
        user_bets = [ub for ub in st.session_state.db['userBets'] if ub['userId'] == user['id']]
        completed_user_bets = [ub for ub in user_bets 
                             if get_bet_by_id(ub['betId']) and 
                             (get_bet_by_id(ub['betId']).get('status') == 'completed' or 
                              get_bet_by_id(ub['betId']).get('status') == 'cancelled')]
        
        if completed_user_bets:
            bet_data = []
            for user_bet in completed_user_bets:
                bet = get_bet_by_id(user_bet['betId'])
                if bet:
                    result = bet.get('result', False)
                    status = bet.get('status', '')
                    
                    bet_data.append({
                        "Aposta": bet['description'],
                        "Odd": bet['odd'],
                        "Valor Apostado": user_bet['amount'],
                        "Resultado": "Ganhou" if result else "Perdeu" if status == 'completed' else "Cancelada",
                        "Retorno": int(user_bet['amount'] * bet['odd']) if result else 0
                    })
            
            df = pd.DataFrame(bet_data)
            st.dataframe(df)
        else:
            st.info("Você não tem histórico de apostas finalizadas.")
    
    with subtab3:
        active_bets = get_active_bets()
        
        if active_bets:
            for bet in active_bets:
                with st.expander(bet['description']):
                    st.write(f"Odd: {bet['odd']}")
                    if bet.get('matchId'):
                        st.write(f"Jogo: {get_match_name(bet['matchId'])}")
                    
                    amount = st.number_input(f"Terrara Coins para apostar (disponível: {user['points']})", 
                                    min_value=10, max_value=user['points'], value=100, 
                                    key=f"amount_{bet['id']}")
                    
                    st.write(f"Retorno potencial: {int(amount * bet['odd'])} Terrara Coins")
                    
                    if st.button("Confirmar Aposta", key=f"place_{bet['id']}"):
                        # Check if user has enough points
                        if amount > user['points']:
                            st.error("Você não tem Terrara Coins suficientes para esta aposta.")
                        else:
                            # Create user bet
                            new_user_bet = {
                                'id': f"userBet_{user['id']}_{bet['id']}_{str(uuid.uuid4())[:8]}",
                                'userId': user['id'],
                                'betId': bet['id'],
                                'amount': amount,
                                'placedAt': datetime.datetime.now().isoformat()
                            }
                            
                            st.session_state.db['userBets'].append(new_user_bet)
                            
                            # Deduct points from user
                            user_index = next((i for i, u in enumerate(st.session_state.db['users']) 
                                       if u['id'] == user['id']), None)
                            
                            if user_index is not None:
                                st.session_state.db['users'][user_index]['points'] -= amount
                                st.session_state.current_user['points'] -= amount
                            
                            save_database()
                            
                            st.success("Aposta realizada com sucesso!")
                            st.rerun()
        else:
            st.info("Não há apostas disponíveis no momento.")

def render_my_team():
    # Call the existing team management code
    if not st.session_state.logged_in or st.session_state.user_type != 'team':
        st.error("Acesso restrito a times.")
        return
        
    # This will show the team management tab
    render_dashboard()

def main():
    # Render sidebar for navigation
    render_sidebar()
    
    # Main content area based on current page
    if st.session_state.page == 'home':
        render_home()
    elif st.session_state.page == 'classification':
        render_classification()
    elif st.session_state.page == 'topScorers':
        render_top_scorers()
    elif st.session_state.page == 'matches':
        render_matches()
    elif st.session_state.page == 'login':
        render_login()
    elif st.session_state.page == 'register_choice':
        render_register_choice()
    elif st.session_state.page == 'register_team':
        render_register_team()
    elif st.session_state.page == 'register_fan':
        render_register_fan()
    elif st.session_state.page == 'dashboard':
        render_dashboard()
    elif st.session_state.page == 'teams':
        render_teams()
    elif st.session_state.page == 'results':
        render_results()
    elif st.session_state.page == 'betting':
        render_betting()
    elif st.session_state.page == 'settings':
        render_settings()
    elif st.session_state.page == 'my_team':
        render_my_team()
    elif st.session_state.page == 'players':
        render_dashboard()  # Players tab is inside dashboard
    elif st.session_state.page == 'my_bets':
        render_my_bets()
    elif st.session_state.page == 'stats':
        render_dashboard()  # Stats tab is inside dashboard

if __name__ == "__main__":
    main()
