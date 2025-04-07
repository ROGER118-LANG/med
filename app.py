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
        text-align: center;
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
        try:
            with open('database.json', 'r') as f:
                st.session_state.db = json.load(f)
        except json.JSONDecodeError:
            st.error("Erro ao carregar database.json. Iniciando com banco de dados vazio.")
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
        json.dump(st.session_state.db, f, indent=4) # Use indent for readability

# Initialize session states
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_type = None
    st.session_state.user_team = None

# Navigation state
if 'page' not in st.session_state:
    st.session_state.page = 'home'

# State for player registration form (within team registration)
if 'player_entries' not in st.session_state:
    st.session_state.player_entries = {} # Stores data for player inputs {form_key: {'name': '', 'birthDate': None}}

# Helper functions
def get_team_by_id(team_id):
    teams = st.session_state.db.get('teams', [])
    for team in teams:
        if team.get('id') == team_id:
            return team
    return {'name': 'Time Desconhecido', 'id': None} # Return a default dict

def get_player_by_id(player_id):
    players = st.session_state.db.get('players', [])
    for player in players:
        if player.get('id') == player_id:
            return player
    return None

def get_match_by_id(match_id):
    matches = st.session_state.db.get('matches', [])
    for match in matches:
        if match.get('id') == match_id:
            return match
    return None

def get_match_name(match_id):
    match = get_match_by_id(match_id)
    if match:
        team_a_name = match.get('teamA', 'Time A')
        team_b_name = match.get('teamB', 'Time B')
        return f"{team_a_name} vs {team_b_name}"
    return 'Jogo Desconhecido'

def get_bet_by_id(bet_id):
    bets = st.session_state.db.get('bets', [])
    for bet in bets:
        if bet.get('id') == bet_id:
            return bet
    return None

def get_team_players(team_id):
    if not team_id:
        return []
    return [p for p in st.session_state.db.get('players', []) if p.get('teamId') == team_id]

def get_player_goals(player_id):
    goals = [g for g in st.session_state.db.get('goals', [])
             if g.get('playerId') == player_id and g.get('type') in ['normal', 'penalty']]
    return len(goals)

def format_date(date_string):
    if not date_string:
        return 'Data Inválida'
    try:
        # Attempt parsing ISO format first
        date = datetime.datetime.fromisoformat(date_string.replace('Z', '+00:00'))
        return date.strftime('%d/%m/%Y %H:%M:%S')
    except ValueError:
        # Fallback for other potential formats or return as is
        try:
             # Try common date formats if ISO fails
             date = datetime.datetime.strptime(date_string, '%Y-%m-%d')
             return date.strftime('%d/%m/%Y')
        except ValueError:
            return date_string # Return original if all parsing fails

def get_sorted_teams():
    teams = st.session_state.db.get('teams', [])
    # Ensure default values for sorting keys if missing
    return sorted(teams, key=lambda x: (
        -x.get('points', 0),
        -(x.get('goalsFor', 0) - x.get('goalsAgainst', 0)),
        -x.get('goalsFor', 0)
    ))

def get_team_position(team_id):
    sorted_teams = get_sorted_teams()
    for i, team in enumerate(sorted_teams):
        if team.get('id') == team_id:
            return i + 1
    return 0

def get_upcoming_matches():
    matches = st.session_state.db.get('matches', [])
    now = datetime.datetime.now()
    upcoming = []
    for m in matches:
        if not m.get('played', False) and not m.get('cancelled', False):
            try:
                # Ensure date is parsed correctly
                match_date = datetime.datetime.strptime(m.get('date', ''), '%d/%m/%Y %H:%M')
                if match_date > now:
                    upcoming.append(m)
            except ValueError:
                # Handle matches with invalid date formats if needed
                 # st.warning(f"Formato de data inválido para o jogo ID {m.get('id')}: {m.get('date')}")
                pass # Or log the error
    return sorted(upcoming, key=lambda x: datetime.datetime.strptime(x['date'], '%d/%m/%Y %H:%M'))

def get_completed_matches():
    matches = st.session_state.db.get('matches', [])
    return [m for m in matches if m.get('played', False)]

def get_scorers():
    goals = st.session_state.db.get('goals', [])
    if not goals:
        return []

    player_goals = {}

    for goal in goals:
        player = get_player_by_id(goal.get('playerId'))
        if not player:
            continue

        player_id = player.get('id')
        if player_id not in player_goals:
            team = get_team_by_id(player.get('teamId'))
            player_goals[player_id] = {
                'id': player_id,
                'name': player.get('name', 'Desconhecido'),
                'teamId': player.get('teamId'),
                'team': team.get('name', 'Desconhecido') if team else 'Desconhecido',
                'goals': {
                    'normal': 0,
                    'penalty': 0,
                    'own': 0,
                    'total': 0
                }
            }

        goal_type = goal.get('type')
        if goal_type == 'normal':
            player_goals[player_id]['goals']['normal'] += 1
            player_goals[player_id]['goals']['total'] += 1
        elif goal_type == 'penalty':
            player_goals[player_id]['goals']['penalty'] += 1
            player_goals[player_id]['goals']['total'] += 1
        elif goal_type == 'own':
            # Need to assign own goal to the correct player (scorer) but count against their team stats usually
            # Current logic attributes own goal count to the player who scored it.
            player_goals[player_id]['goals']['own'] += 1

    # Convert to list and sort
    scorers_list = list(player_goals.values())
    scorers_list.sort(key=lambda x: (
        -x['goals']['total'],
        -x['goals']['normal'],
        -x['goals']['penalty']
    ))

    return scorers_list

def get_active_bets():
    return [b for b in st.session_state.db.get('bets', []) if b.get('status') == 'active']

def get_completed_bets():
    return [b for b in st.session_state.db.get('bets', [])
            if b.get('status') in ['completed', 'cancelled']]

def login(username, password):
    users = st.session_state.db.get('users', [])
    for user in users:
        if user.get('username') == username and user.get('password') == password:
            st.session_state.logged_in = True
            st.session_state.current_user = user
            st.session_state.user_type = user.get('type')

            if user.get('type') == 'team':
                st.session_state.user_team = get_team_by_id(user.get('teamId'))
            elif user.get('type') == 'fan':
                 # Ensure fan has points, initialize if not present
                 if 'points' not in user:
                     user['points'] = 1000 # Default starting points
                     # Maybe find the user index and update the db state directly if needed
                     save_database()
                 st.session_state.user_team = None # Fans don't manage a team

            st.session_state.page = 'dashboard' # Redirect to dashboard after login
            return True
    return False

def logout():
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_type = None
    st.session_state.user_team = None
    st.session_state.page = 'home' # Redirect to home after logout
    st.rerun() # Force rerun to update UI


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

        # Determine default index based on current page
        page_to_index_logged_in_admin = { "home": 0, "classification": 1, "topScorers": 2, "matches": 3, "dashboard": 4, "teams": 5, "results": 6, "betting": 7, "settings": 8 }
        page_to_index_logged_in_team = { "home": 0, "classification": 1, "topScorers": 2, "matches": 3, "my_team": 4, "players": 5, "stats": 6 }
        page_to_index_logged_in_fan = { "home": 0, "classification": 1, "topScorers": 2, "matches": 3, "my_bets": 4 }
        page_to_index_logged_out = { "home": 0, "classification": 1, "topScorers": 2, "matches": 3, "login": 4, "register_choice": 5 }

        current_page = st.session_state.get('page', 'home')

        # Navigation menu
        if st.session_state.logged_in:
            user = st.session_state.current_user
            st.markdown(f"**Olá, {user.get('name', 'Usuário')}!**")
            user_type_display = {
                'admin': 'Administrador',
                'team': 'Gerente de Time',
                'fan': 'Torcedor'
            }.get(st.session_state.user_type, 'Desconhecido')
            st.markdown(f"Tipo: {user_type_display}")

            # Sidebar menu - different options based on user type
            if st.session_state.user_type == 'admin':
                 default_index = page_to_index_logged_in_admin.get(current_page, 0)
                 selected = option_menu(
                    "Menu Principal",
                    ["Início", "Classificação", "Artilharia", "Jogos", "Dashboard", "Times", "Resultados", "Apostas", "Configurações", "Sair"],
                    icons=['house', 'trophy', 'star', 'calendar2', 'speedometer2', 'people', 'clipboard-check', 'currency-exchange', 'gear', 'box-arrow-right'],
                    menu_icon="cast", default_index=default_index, key="admin_menu"
                 )
                 page_mapping = { "Início": "home", "Classificação": "classification", "Artilharia": "topScorers", "Jogos": "matches", "Dashboard": "dashboard", "Times": "teams", "Resultados": "results", "Apostas": "betting", "Configurações": "settings" }

            elif st.session_state.user_type == 'team':
                default_index = page_to_index_logged_in_team.get(current_page, 0)
                selected = option_menu(
                    "Menu Principal",
                    ["Início", "Classificação", "Artilharia", "Jogos", "Meu Time", "Jogadores", "Estatísticas", "Sair"],
                    icons=['house', 'trophy', 'star', 'calendar2', 'shield', 'person-badge', 'graph-up', 'box-arrow-right'],
                    menu_icon="cast", default_index=default_index, key="team_menu"
                )
                page_mapping = { "Início": "home", "Classificação": "classification", "Artilharia": "topScorers", "Jogos": "matches", "Meu Time": "my_team", "Jogadores": "players", "Estatísticas": "stats" }

            else:  # fan
                default_index = page_to_index_logged_in_fan.get(current_page, 0)
                selected = option_menu(
                    "Menu Principal",
                    ["Início", "Classificação", "Artilharia", "Jogos", "Minhas Apostas", "Sair"],
                    icons=['house', 'trophy', 'star', 'calendar2', 'cash-coin', 'box-arrow-right'],
                    menu_icon="cast", default_index=default_index, key="fan_menu"
                )
                page_mapping = { "Início": "home", "Classificação": "classification", "Artilharia": "topScorers", "Jogos": "matches", "Minhas Apostas": "my_bets" }

            # Handle menu selection
            if selected == "Sair":
                logout() # logout handles rerun
            else:
                new_page = page_mapping.get(selected)
                if new_page and st.session_state.page != new_page:
                    st.session_state.page = new_page
                    st.rerun()

        else:
            # Login/Register options
            default_index = page_to_index_logged_out.get(current_page, 0)
            selected = option_menu(
                "Menu Principal",
                ["Início", "Classificação", "Artilharia", "Jogos", "Login", "Cadastro"],
                icons=['house', 'trophy', 'star', 'calendar2', 'box-arrow-in-right', 'person-plus'],
                menu_icon="cast", default_index=default_index, key="guest_menu"
            )

            # Handle selection
            page_mapping = { "Início": "home", "Classificação": "classification", "Artilharia": "topScorers", "Jogos": "matches", "Login": "login", "Cadastro": "register_choice" }
            new_page = page_mapping.get(selected)
            if new_page and st.session_state.page != new_page:
                 st.session_state.page = new_page
                 st.rerun()


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
                if st.button("Cadastrar Time", use_container_width=True, key="home_reg_team"):
                    st.session_state.page = 'register_team'
                    st.rerun()
            with reg_col2:
                if st.button("Cadastro de Torcedor", use_container_width=True, key="home_reg_fan"):
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
                team_a = match.get('teamA', 'Time A')
                team_b = match.get('teamB', 'Time B')
                match_date = match.get('date', 'Data indefinida')
                st.markdown(f"""
                <div class="matches-card {'highlighted' if i == 0 else ''}">
                    <strong>{team_a} vs {team_b}</strong><br>
                    <small>Data: {match_date}</small>
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
        """.format(len(st.session_state.db.get('teams', []))), unsafe_allow_html=True)

    with stats_col2:
        st.markdown("""
        <div class="stat-card">
            <h4 style="margin-top:0">Jogadores</h4>
            <h2 style="color:#4CAF50; margin-bottom:0">{}</h2>
        </div>
        """.format(len(st.session_state.db.get('players', []))), unsafe_allow_html=True)

    with stats_col3:
        st.markdown("""
        <div class="stat-card">
            <h4 style="margin-top:0">Jogos Realizados</h4>
            <h2 style="color:#4CAF50; margin-bottom:0">{}</h2>
        </div>
        """.format(len(get_completed_matches())), unsafe_allow_html=True)

    with stats_col4:
        # Total goals
        total_goals = len(st.session_state.db.get('goals', []))
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
            # Use index=False to hide pandas index
            st.dataframe(scorers_df.set_index('Pos'), use_container_width=True)
        else:
            st.info("Nenhum gol registrado ainda.")

    with col2:
        st.subheader("Classificação")
        teams = get_sorted_teams()[:5]  # Top 5
        if teams:
            teams_df = pd.DataFrame([
                {"Pos": i+1, "Time": t.get('name', 'N/A'), "Pts": t.get('points', 0), "J": t.get('games', 0), "V": t.get('wins', 0)}
                for i, t in enumerate(teams)
            ])
            st.dataframe(teams_df.set_index('Pos'), use_container_width=True)
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
                "Time": team.get('name', 'N/A'),
                "P": team.get('points', 0),
                "J": team.get('games', 0),
                "V": team.get('wins', 0),
                "E": team.get('draws', 0),
                "D": team.get('losses', 0),
                "GP": team.get('goalsFor', 0),
                "GC": team.get('goalsAgainst', 0),
                "SG": team.get('goalsFor', 0) - team.get('goalsAgainst', 0)
            })

        df = pd.DataFrame(data)
        # Use st.dataframe for better presentation and sorting/filtering
        st.dataframe(df.set_index('Pos'), use_container_width=True)
    else:
        st.info("Nenhum time cadastrado ainda.")

def render_top_scorers():
    st.title("Artilharia")

    tab1, tab2, tab3, tab4 = st.tabs(["Gols Totais", "Gols Normais", "Gols de Pênalti", "Gols Contra"])

    scorers = get_scorers()

    with tab1:
        st.subheader("Artilheiros - Gols Totais")
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
                    "Contra": player['goals']['own'] # Keep track, but doesn't add to total
                })

            df = pd.DataFrame(data)
            st.dataframe(df.set_index('Pos'), use_container_width=True)
        else:
            st.info("Nenhum gol registrado ainda.")

    with tab2:
        st.subheader("Artilheiros - Gols Normais")
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
                st.dataframe(df.set_index('Pos'), use_container_width=True)
            else:
                st.info("Nenhum gol normal registrado ainda.")
        else:
            st.info("Nenhum gol registrado ainda.")

    with tab3:
        st.subheader("Artilheiros - Gols de Pênalti")
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
                st.dataframe(df.set_index('Pos'), use_container_width=True)
            else:
                st.info("Nenhum gol de pênalti registrado ainda.")
        else:
            st.info("Nenhum gol registrado ainda.")

    with tab4:
        st.subheader("Gols Contra")
        if scorers:
             # Filtering players who scored own goals. Note: This shows the SCORER, not necessarily the player who benefited.
            own_goal_scorers = sorted([p for p in scorers if p['goals']['own'] > 0],
                           key=lambda x: -x['goals']['own'])

            data = []
            for i, player in enumerate(own_goal_scorers):
                # Need goal details to show which team benefited if needed.
                # For now, just list the player who scored the OG.
                data.append({
                    "Pos": i+1,
                    "Jogador": player['name'],
                    "Time (Jogador)": player['team'], # Team of the player who scored the OG
                    "Gols Contra": player['goals']['own']
                })

            if data:
                df = pd.DataFrame(data)
                st.dataframe(df.set_index('Pos'), use_container_width=True)
            else:
                st.info("Nenhum gol contra registrado ainda.")
        else:
            st.info("Nenhum gol registrado ainda.")

def render_matches():
    st.title("Jogos")

    tab1, tab2 = st.tabs(["Próximos Jogos", "Resultados"])

    with tab1:
        st.subheader("Próximos Jogos Agendados")
        upcoming = get_upcoming_matches()
        if upcoming:
            for match in upcoming:
                 team_a = match.get('teamA', 'Time A')
                 score_a = match.get('scoreA', '?')
                 team_b = match.get('teamB', 'Time B')
                 score_b = match.get('scoreB', '?')
                 match_date = match.get('date', 'Data indefinida')
                 match_id = match.get('id')

                 with st.expander(f"{team_a} {score_a} x {score_b} {team_b} - {match_date}"):
                    st.write(f"Data: {match_date}")
                    st.write(f"ID do Jogo: {match_id}") # Display ID for reference

                    # Show match goals
                    match_goals = [g for g in st.session_state.db.get('goals', []) if g.get('matchId') == match_id]
                    if match_goals:
                        st.write("---")
                        st.subheader("Gols:")
                        for goal in match_goals:
                            player = get_player_by_id(goal.get('playerId'))
                            goal_team = get_team_by_id(goal.get('teamId')) # Team of the player who scored
                            player_name = player.get('name', 'Desconhecido') if player else 'Desconhecido'
                            goal_team_name = goal_team.get('name', 'Desconhecido') if goal_team else 'Desconhecido'

                            if goal.get('type') == 'own':
                                # Find which team the own goal was scored against (credited to)
                                for_team = get_team_by_id(goal.get('forTeamId'))
                                for_team_name = for_team.get('name', 'Desconhecido') if for_team else 'Desconhecido'
                                st.write(f"⚽ {player_name} ({goal_team_name}) - Gol contra para {for_team_name}")
                            else:
                                goal_type_str = 'Pênalti' if goal.get('type') == 'penalty' else 'Gol'
                                st.write(f"⚽ {player_name} ({goal_team_name}) - {goal_type_str}")
                    else:
                        st.info("Nenhum gol registrado para esta partida.")

                    # Admin can edit results or view details
                    if st.session_state.user_type == 'admin':
                        # Option for admin to add result directly from upcoming matches view
                        if st.button("Adicionar Resultado", key=f"add_result_upcoming_{match_id}"):
                            # Navigate or show modal to add result - Simplification: redirect to results page
                            st.session_state.page = 'results'
                            st.session_state.selected_match_for_result = match_id # Store which match to focus on
                            st.rerun()

        else:
            st.info("Não há jogos agendados no momento.")

    with tab2:
        st.subheader("Resultados dos Jogos")
        completed = get_completed_matches()
        if completed:
            # Sort completed matches by date, most recent first
            completed_sorted = sorted(completed, key=lambda x: datetime.datetime.strptime(x.get('date', '01/01/1900 00:00'), '%d/%m/%Y %H:%M'), reverse=True)

            for match in completed_sorted:
                team_a = match.get('teamA', 'Time A')
                score_a = match.get('scoreA', '?')
                team_b = match.get('teamB', 'Time B')
                score_b = match.get('scoreB', '?')
                match_date = match.get('date', 'Data indefinida')
                match_id = match.get('id')

                with st.expander(f"{team_a} {score_a} x {score_b} {team_b} - {match_date}"):
                    st.write(f"Data: {match_date}")
                    st.write(f"ID do Jogo: {match_id}") # Display ID for reference

                    # Show match goals
                    match_goals = [g for g in st.session_state.db.get('goals', []) if g.get('matchId') == match_id]
                    if match_goals:
                        st.write("---")
                        st.subheader("Gols:")
                        for goal in match_goals:
                            player = get_player_by_id(goal.get('playerId'))
                            goal_team = get_team_by_id(goal.get('teamId')) # Team of the player who scored
                            player_name = player.get('name', 'Desconhecido') if player else 'Desconhecido'
                            goal_team_name = goal_team.get('name', 'Desconhecido') if goal_team else 'Desconhecido'

                            if goal.get('type') == 'own':
                                # Find which team the own goal was scored against (credited to)
                                for_team = get_team_by_id(goal.get('forTeamId'))
                                for_team_name = for_team.get('name', 'Desconhecido') if for_team else 'Desconhecido'
                                st.write(f"⚽ {player_name} ({goal_team_name}) - Gol contra para {for_team_name}")
                            else:
                                goal_type_str = 'Pênalti' if goal.get('type') == 'penalty' else 'Gol'
                                st.write(f"⚽ {player_name} ({goal_team_name}) - {goal_type_str}")
                    else:
                        st.info("Nenhum gol registrado para esta partida.")

                    # Admin can edit results or view details
                    if st.session_state.user_type == 'admin':
                        if st.button("Editar Resultado", key=f"edit_result_{match_id}"):
                             # Navigate or show modal to edit result
                            st.session_state.page = 'results'
                            st.session_state.selected_match_for_result = match_id # Store which match to focus on
                            st.rerun()


        else:
            st.info("Nenhum jogo realizado ainda.")

def render_login():
    st.title("Login")
    st.markdown('<div class="form-container">', unsafe_allow_html=True) # Start form container

    username = st.text_input("Usuário", key="login_user")
    password = st.text_input("Senha", type="password", key="login_pass")

    if st.button("Entrar", key="login_button"):
        if login(username, password):
            # Login function now handles redirection
             st.rerun() # Rerun to reflect login state change immediately
        else:
            st.error("Usuário ou senha incorretos.")

    st.write("---") # Separator
    st.write("Ainda não tem conta?")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Cadastrar Time", key="login_reg_team", use_container_width=True):
            st.session_state.page = 'register_team'
            st.rerun()

    with col2:
        if st.button("Seja um torcedor", key="login_reg_fan", use_container_width=True):
            st.session_state.page = 'register_fan'
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True) # End form container

def render_register_choice():
    """Page to choose between registering a team or a fan."""
    st.title("Cadastro")
    st.markdown('<div class="form-container">', unsafe_allow_html=True)
    st.write("Selecione o tipo de cadastro que deseja realizar:")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cadastrar Time", key="choice_reg_team", use_container_width=True):
            st.session_state.page = 'register_team'
            st.rerun()
    with col2:
        if st.button("Cadastro de Torcedor", key="choice_reg_fan", use_container_width=True):
            st.session_state.page = 'register_fan'
            st.rerun()

    st.markdown("---")
    if st.button("Voltar para Login", key="choice_back_login"):
         st.session_state.page = 'login'
         st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


def render_register_team():
    st.title("Cadastrar Time")
    st.markdown('<div class="form-container">', unsafe_allow_html=True)

    with st.form("register_team_form", clear_on_submit=False):
        st.subheader("Informações do Time e Representante")
        team_name = st.text_input("Nome do Time*")
        rep_name = st.text_input("Nome do Representante*")
        rep_phone = st.text_input("Telefone do Representante*")
        username = st.text_input("Nome de Usuário (para login)*")
        password = st.text_input("Senha (para login)*", type="password")

        st.subheader("Cadastro de Jogadores (Mínimo 5, Máximo 15)")
        st.caption("Preencha os dados para cada jogador. Você poderá adicionar/editar mais tarde.")

        # Dynamically add player input fields
        if 'num_players_to_add' not in st.session_state:
            st.session_state.num_players_to_add = 5 # Start with minimum

        num_players = st.number_input("Número de jogadores a cadastrar inicialmente (5-15)",
                                      min_value=5, max_value=15,
                                      value=st.session_state.num_players_to_add, step=1,
                                      key="num_players_input")
        st.session_state.num_players_to_add = num_players # Update state if changed

        players_data = [] # List to hold player dicts {'name': ..., 'birthDate': ...}

        cols_per_row = 2
        for i in range(st.session_state.num_players_to_add):
             row_idx = i // cols_per_row
             col_idx = i % cols_per_row

             if col_idx == 0:
                 cols = st.columns(cols_per_row)

             with cols[col_idx]:
                 st.markdown(f"**Jogador {i+1}**")
                 player_name_key = f"player_name_{i}"
                 player_birth_key = f"player_birth_{i}"

                 player_name = st.text_input(f"Nome Completo*", key=player_name_key)
                 # Default to a reasonable date to avoid errors, user must change
                 default_birth_date = datetime.date.today() - datetime.timedelta(days=12*365)
                 player_birth = st.date_input(f"Data de Nascimento*", key=player_birth_key,
                                              min_value=datetime.date(1990, 1, 1), # Reasonable min
                                              max_value=datetime.date.today(), # Cannot be born in future
                                              value=default_birth_date)
                 players_data.append({'name': player_name, 'birthDate': player_birth})


        submitted = st.form_submit_button("Cadastrar Time e Jogadores")

        if submitted:
            # --- Validations ---
            errors = []
            if not all([team_name, rep_name, rep_phone, username, password]):
                errors.append("Todos os campos de informação do time e login são obrigatórios.")
            if any(u.get('username') == username for u in st.session_state.db.get('users', [])):
                errors.append(f"O nome de usuário '{username}' já está em uso.")

            # Player validations
            valid_players = []
            today = datetime.date.today()
            min_birth_year_for_sub13 = today.year - 13 # Must be born in or after this year
            max_birth_year_for_sub13 = today.year # Cannot be born in future

            for i, p_data in enumerate(players_data):
                p_name = p_data['name']
                p_birth = p_data['birthDate']

                if not p_name:
                    errors.append(f"Nome do Jogador {i+1} é obrigatório.")
                    continue # Skip age check if name missing

                if not p_birth:
                     errors.append(f"Data de nascimento do Jogador {i+1} é obrigatória.")
                     continue

                age = today.year - p_birth.year - ((today.month, today.day) < (p_birth.month, p_birth.day))

                if age >= 13:
                    errors.append(f"Jogador {i+1} ({p_name}) tem {age} anos e não pode participar (Sub-13). Data de nasc.: {p_birth.strftime('%d/%m/%Y')}")
                else:
                     valid_players.append({'name': p_name, 'birthDate': p_birth.strftime('%Y-%m-%d')}) # Store valid ones

            if len(valid_players) < 5:
                 errors.append(f"É necessário cadastrar pelo menos 5 jogadores válidos (Sub-13). Você forneceu {len(valid_players)} válidos.")


            if errors:
                for error in errors:
                    st.error(error)
            else:
                # --- Create Team and User ---
                team_id = f"team_{str(uuid.uuid4())[:8]}" # More unique ID

                new_team = {
                    'id': team_id,
                    'name': team_name,
                    'representative': { 'name': rep_name, 'phone': rep_phone },
                    'points': 0, 'games': 0, 'wins': 0, 'draws': 0, 'losses': 0,
                    'goalsFor': 0, 'goalsAgainst': 0
                }
                st.session_state.db['teams'].append(new_team)

                new_user = {
                    'id': f"user_{str(uuid.uuid4())[:8]}", # User ID distinct from team ID
                    'username': username,
                    'password': password, # Consider hashing passwords in a real app
                    'type': 'team',
                    'teamId': team_id, # Link user to the team they manage
                    'name': team_name # User's display name (can be team name)
                }
                st.session_state.db['users'].append(new_user)

                # --- Create Players ---
                for player_info in valid_players:
                    player_id = f"player_{team_id}_{str(uuid.uuid4())[:8]}"
                    new_player = {
                        'id': player_id,
                        'name': player_info['name'],
                        'teamId': team_id,
                        'birthDate': player_info['birthDate']
                        # Add other player stats/info fields if needed later
                    }
                    st.session_state.db['players'].append(new_player)


                # --- Save and Login ---
                save_database()

                st.success(f"Time '{team_name}' e {len(valid_players)} jogadores cadastrados com sucesso!")

                # Auto login after successful registration
                if login(username, password):
                    st.info("Você foi logado automaticamente.")
                    # Rerun needed after login sets session state
                    st.session_state.page = 'players' # Go to player management page
                    st.experimental_rerun() # Use experimental rerun if needed
                else:
                    st.warning("Cadastro realizado, mas ocorreu um erro no login automático. Por favor, faça login manualmente.")
                    st.session_state.page = 'login'
                    st.experimental_rerun()

    st.markdown('</div>', unsafe_allow_html=True) # End form container


def render_register_fan():
    st.title("Cadastro de Torcedor")
    st.markdown('<div class="form-container">', unsafe_allow_html=True)

    with st.form("register_fan_form", clear_on_submit=True):
        name = st.text_input("Nome Completo*")
        username = st.text_input("Nome de Usuário (para login)*")
        password = st.text_input("Senha (para login)*", type="password")

        teams = st.session_state.db.get('teams', [])
        team_options = ["Nenhum (geral)"] + [team.get('name', 'Nome Inválido') for team in teams]
        team_ids = [None] + [team.get('id') for team in teams] # Map index back to ID

        selected_team_name = st.selectbox("Time Favorito (Opcional)", options=team_options)

        submitted = st.form_submit_button("Cadastrar como Torcedor")

        if submitted:
            errors = []
            if not all([name, username, password]):
                errors.append("Nome Completo, Nome de Usuário e Senha são obrigatórios.")
            if any(u.get('username') == username for u in st.session_state.db.get('users', [])):
                errors.append(f"O nome de usuário '{username}' já está em uso.")

            if errors:
                for error in errors:
                    st.error(error)
            else:
                fan_id = f"fan_{str(uuid.uuid4())[:8]}"
                selected_team_id = None
                if selected_team_name != "Nenhum (geral)":
                    try:
                         # Find the ID corresponding to the selected name
                         selected_index = team_options.index(selected_team_name)
                         selected_team_id = team_ids[selected_index]
                    except ValueError:
                         st.warning("Time favorito selecionado inválido, registrando sem time favorito.")


                new_fan = {
                    'id': fan_id,
                    'username': username,
                    'password': password, # Hash in real app
                    'type': 'fan',
                    'name': name,
                    'favoriteTeamId': selected_team_id,
                    'points': 1000 # Starting points for betting
                }

                st.session_state.db['users'].append(new_fan)
                save_database()
                st.success(f"Cadastro de torcedor para '{name}' realizado com sucesso!")
                st.info("Você recebeu 1000 pontos para começar a apostar.")

                # Attempt auto-login
                if login(username, password):
                     st.info("Você foi logado automaticamente.")
                     st.session_state.page = 'my_bets' # Go to betting page
                     st.experimental_rerun()
                else:
                     st.warning("Cadastro realizado, mas ocorreu um erro no login automático. Faça login manualmente.")
                     st.session_state.page = 'login'
                     st.experimental_rerun()


    st.markdown("---")
    if st.button("Voltar para Login", key="fan_back_login"):
        st.session_state.page = 'login'
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def render_dashboard():
    st.title("Painel de Controle")

    if not st.session_state.logged_in:
        st.error("Você precisa estar logado para acessar esta página.")
        st.session_state.page = 'login' # Redirect if not logged in
        st.rerun()
        return

    # --- Determine Tabs based on User Type ---
    tabs_titles = ["Visão Geral"]
    page_to_render = { "Visão Geral": render_dashboard_overview }

    if st.session_state.user_type == 'team':
        tabs_titles.extend(["Meu Time", "Jogadores", "Estatísticas"])
        page_to_render["Meu Time"] = render_my_team_management # Renamed function
        page_to_render["Jogadores"] = render_player_management # Renamed function
        page_to_render["Estatísticas"] = render_team_stats

    elif st.session_state.user_type == 'admin':
        tabs_titles.extend(["Times", "Resultados", "Apostas", "Configurações"])
        page_to_render["Times"] = render_admin_teams
        page_to_render["Resultados"] = render_admin_results
        page_to_render["Apostas"] = render_admin_betting
        page_to_render["Configurações"] = render_settings # Assuming a settings page exists

    elif st.session_state.user_type == 'fan':
        tabs_titles.extend(["Minhas Apostas"])
        page_to_render["Minhas Apostas"] = render_my_bets

    # --- Render Tabs ---
    # Use st.tabs correctly - it returns a list of context managers
    selected_tabs = st.tabs(tabs_titles)

    for i, title in enumerate(tabs_titles):
        with selected_tabs[i]:
            render_func = page_to_render.get(title)
            if render_func:
                render_func() # Call the specific rendering function for the tab
            else:
                st.error(f"Erro: Função de renderização para '{title}' não encontrada.")


# --- Dashboard Tab Specific Rendering Functions ---

def render_dashboard_overview():
    st.header(f"Bem-vindo ao seu Painel, {st.session_state.current_user.get('name', 'Usuário')}!")
    user_type = st.session_state.user_type

    if user_type == 'team':
        team = st.session_state.user_team

        if not team or not team.get('id'): # Check if team data is loaded
             st.warning("Dados do time não encontrados. Tente recarregar a página ou contate o suporte.")
             return

        team_id = team['id']
        players = get_team_players(team_id)
        position = get_team_position(team_id)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Jogadores Registrados", f"{len(players)}/15")
        with col2:
            # Find next match for this specific team
            next_match = None
            upcoming = get_upcoming_matches() # Already sorted by date
            for m in upcoming:
                if m.get('teamAId') == team_id or m.get('teamBId') == team_id:
                     next_match = m
                     break # Found the first upcoming match

            if next_match:
                st.metric("Próximo Jogo",
                          f"{next_match.get('teamA')} vs {next_match.get('teamB')}",
                           next_match.get('date'))
            else:
                st.metric("Próximo Jogo", "Nenhum jogo agendado")
        with col3:
            st.metric("Posição na Tabela", f"{position}º" if position > 0 else "N/A")

    elif user_type == 'admin':
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total de Times", len(st.session_state.db.get('teams', [])))
        with col2:
            st.metric("Total de Jogadores", len(st.session_state.db.get('players', [])))
        with col3:
            st.metric("Jogos Realizados", len(get_completed_matches()))
        with col4:
            st.metric("Apostas Ativas", len(get_active_bets()))

    elif user_type == 'fan':
        user = st.session_state.current_user
        user_id = user.get('id')
        user_bets = [ub for ub in st.session_state.db.get('userBets', []) if ub.get('userId') == user_id]

        # Calculate won bets correctly - need bet status and result
        won_bets_count = 0
        points_won = 0
        points_lost = 0
        for ub in user_bets:
             bet = get_bet_by_id(ub.get('betId'))
             if bet and bet.get('status') == 'completed':
                 bet_amount = ub.get('amount', 0)
                 if bet.get('result') == 'won': # Assuming 'result' field is 'won' or 'lost'
                     won_bets_count += 1
                     points_won += bet_amount * bet.get('odd', 1) - bet_amount # Profit
                 else:
                     points_lost += bet_amount


        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pontos Disponíveis", f"{user.get('points', 0):,}")
        with col2:
            st.metric("Apostas Realizadas", len(user_bets))
        with col3:
             # Display W/L or total won bets count
             st.metric("Apostas Ganhas", won_bets_count)
             # Maybe add profit/loss metric?
             # st.metric("Lucro/Prejuízo", f"{points_won - points_lost:+,}")


# --- Team Management Specific Tabs (Called from Dashboard) ---

def render_my_team_management():
    st.header("Gerenciar Informações do Time")
    team = st.session_state.user_team

    if not team or not team.get('id'):
        st.error("Não foi possível carregar as informações do seu time.")
        return

    team_id = team['id']

    with st.form("edit_team_info_form"):
        st.write(f"**ID do Time:** {team_id}") # Display ID for reference
        current_name = team.get('name', '')
        current_rep_name = team.get('representative', {}).get('name', '')
        current_rep_phone = team.get('representative', {}).get('phone', '')

        new_team_name = st.text_input("Nome do Time", value=current_name)
        new_rep_name = st.text_input("Nome do Representante", value=current_rep_name)
        new_rep_phone = st.text_input("Telefone do Representante", value=current_rep_phone)

        submitted = st.form_submit_button("Atualizar Informações")

        if submitted:
            if not new_team_name or not new_rep_name or not new_rep_phone:
                 st.error("Todos os campos são obrigatórios.")
            else:
                # Find team index to update
                team_index = next((i for i, t in enumerate(st.session_state.db['teams']) if t.get('id') == team_id), None)

                if team_index is not None:
                    st.session_state.db['teams'][team_index]['name'] = new_team_name
                    st.session_state.db['teams'][team_index]['representative']['name'] = new_rep_name
                    st.session_state.db['teams'][team_index]['representative']['phone'] = new_rep_phone

                    # Update user name if it's tied to the team name
                    user_index = next((i for i, u in enumerate(st.session_state.db['users']) if u.get('teamId') == team_id), None)
                    if user_index is not None:
                         st.session_state.db['users'][user_index]['name'] = new_team_name

                     # Update the session state team info as well
                    st.session_state.user_team['name'] = new_team_name
                    st.session_state.user_team['representative']['name'] = new_rep_name
                    st.session_state.user_team['representative']['phone'] = new_rep_phone


                    save_database()
                    st.success("Informações do time atualizadas com sucesso!")
                    st.rerun() # Rerun to reflect changes immediately if needed
                else:
                    st.error("Erro ao encontrar o time no banco de dados.")

def render_player_management():
    st.header("Gerenciar Jogadores")
    team = st.session_state.user_team

    if not team or not team.get('id'):
        st.error("Não foi possível carregar as informações do seu time.")
        return

    team_id = team['id']
    team_name = team.get('name', 'Seu Time')
    team_players = get_team_players(team_id)
    max_players = 15
    min_players = 5 # Minimum required

    st.subheader(f"Jogadores Registrados ({len(team_players)}/{max_players})")
    if len(team_players) < min_players:
         st.warning(f"Seu time tem menos que o mínimo de {min_players} jogadores registrados. Adicione mais jogadores.")


    if team_players:
        player_data = []
        player_options = {} # For selectbox: {player_id: player_name}
        for player in team_players:
            player_id = player.get('id')
            birth_date_str = player.get('birthDate', 'N/A')
            try:
                # Attempt to parse date for display formatting
                birth_date_obj = datetime.datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                birth_date_display = birth_date_obj.strftime('%d/%m/%Y')
                # Calculate age
                today = datetime.date.today()
                age = today.year - birth_date_obj.year - ((today.month, today.day) < (birth_date_obj.month, birth_date_obj.day))
            except:
                birth_date_display = 'Inválida'
                age = 'N/A'


            player_data.append({
                # "ID": player_id, # Optional to show ID
                "Nome": player.get('name', 'N/A'),
                "Nascimento": birth_date_display,
                "Idade": age,
                "Gols": get_player_goals(player_id)
            })
            player_options[player_id] = player.get('name', 'N/A')

        df_players = pd.DataFrame(player_data)
        st.dataframe(df_players, use_container_width=True)

        st.markdown("---")
        st.subheader("Editar ou Remover Jogador")

        selected_player_id = st.selectbox(
            "Selecione um jogador",
            options=list(player_options.keys()),
            format_func=lambda x: f"{player_options[x]} (ID: ...{x[-4:]})" if x in player_options else "Selecione",
             index=0, # Default to first player or prompt
             key="edit_player_select"
        )

        if selected_player_id and selected_player_id in player_options:
             selected_player = get_player_by_id(selected_player_id)

             if selected_player:
                 # --- Edit Form ---
                 with st.form(f"edit_player_{selected_player_id}_form"):
                     st.write(f"Editando: **{selected_player.get('name')}**")
                     current_name = selected_player.get('name', '')
                     current_birth_str = selected_player.get('birthDate')

                     try:
                         current_birth_date = datetime.datetime.strptime(current_birth_str, '%Y-%m-%d').date()
                     except (ValueError, TypeError):
                         current_birth_date = datetime.date.today() - datetime.timedelta(days=12*365) # Default if invalid

                     new_name = st.text_input("Nome do Jogador", value=current_name, key=f"edit_name_{selected_player_id}")
                     new_birth_date = st.date_input("Data de Nascimento", value=current_birth_date, key=f"edit_birth_{selected_player_id}",
                                                      max_value=datetime.date.today(), # Cannot be born in future
                                                      value=datetime.date.today()) # Set default date

                     edit_submitted = st.form_submit_button("Salvar Alterações")

                     if edit_submitted:
                         # Validate age again on edit
                         today = datetime.date.today()
                         age = today.year - new_birth_date.year - ((today.month, today.day) < (new_birth_date.month, new_birth_date.day))

                         if age >= 13:
                             st.error(f"Erro: Jogador teria {age} anos com esta data de nascimento. Deve ser Sub-13.")
                         elif not new_name:
                              st.error("Erro: Nome do jogador não pode ser vazio.")
                         else:
                            # Find player index in DB to update
                            player_index = next((i for i, p in enumerate(st.session_state.db['players']) if p.get('id') == selected_player_id), None)
                            if player_index is not None:
                                st.session_state.db['players'][player_index]['name'] = new_name
                                st.session_state.db['players'][player_index]['birthDate'] = new_birth_date.strftime('%Y-%m-%d')
                                save_database()
                                st.success(f"Jogador '{new_name}' atualizado com sucesso!")
                                st.rerun() # Update the player list display
                            else:
                                st.error("Erro ao encontrar jogador no banco de dados para atualização.")

                 # --- Remove Button ---
                 st.markdown("---") # Separator before remove
                 if st.button(f"Remover {selected_player.get('name')}", key=f"remove_{selected_player_id}", type="primary"):
                     # Add a confirmation step using session state or checkbox
                     confirm_key = f"confirm_remove_{selected_player_id}"
                     if confirm_key not in st.session_state:
                         st.session_state[confirm_key] = False

                     st.session_state[confirm_key] = st.checkbox(f"**Confirmar remoção de {selected_player.get('name')}?** Esta ação não pode ser desfeita.", key=f"check_confirm_{selected_player_id}")

                     if st.session_state[confirm_key]:
                         # Proceed with removal
                         st.session_state.db['players'] = [p for p in st.session_state.db.get('players', []) if p.get('id') != selected_player_id]

                         # Also remove any goals associated with this player
                         st.session_state.db['goals'] = [g for g in st.session_state.db.get('goals', []) if g.get('playerId') != selected_player_id]

                         save_database()
                         st.success(f"Jogador {selected_player.get('name')} removido com sucesso!")
                         del st.session_state[confirm_key] # Clean up confirmation state
                         st.rerun()
                     else:
                          # If checkbox is unchecked after being checked (or initially)
                          st.info("Remoção cancelada.")


             else:
                 st.error("Jogador selecionado não encontrado.")
        else:
            st.info("Selecione um jogador da lista acima para editar ou remover.")

    else: # No players yet
        st.info(f"Seu time ainda não tem jogadores cadastrados. Adicione pelo menos {min_players}.")


    st.markdown("---")
    # --- Add Player Form ---
    if len(team_players) < max_players:
        st.subheader("Adicionar Novo Jogador")
        with st.form("add_player_form", clear_on_submit=True):
            new_player_name = st.text_input("Nome Completo*", key="add_player_name")
            default_birth_date = datetime.date.today() - datetime.timedelta(days=12*365) # Sensible default
            new_player_birth = st.date_input("Data de Nascimento*", key="add_player_birth",
                                           value=default_birth_date,
                                           max_value=datetime.date.today()) # Cannot be born in future

            add_submitted = st.form_submit_button("Adicionar Jogador")

            if add_submitted:
                # Validate age
                today = datetime.date.today()
                age = today.year - new_player_birth.year - ((today.month, today.day) < (new_player_birth.month, new_player_birth.day))

                if age >= 13:
                    st.error(f"Erro: Jogador teria {age} anos com esta data de nascimento. Deve ser Sub-13.")
                elif not new_player_name:
                    st.error("Erro: Nome do jogador é obrigatório.")
                else:
                    player_id = f"player_{team_id}_{str(uuid.uuid4())[:8]}"
                    new_player = {
                        'id': player_id,
                        'name': new_player_name,
                        'teamId': team_id,
                        'birthDate': new_player_birth.strftime('%Y-%m-%d')
                    }
                    st.session_state.db['players'].append(new_player)
                    save_database()
                    st.success(f"Jogador '{new_player_name}' adicionado com sucesso!")
                    st.rerun() # Update player list
    else:
        st.warning(f"Seu time já atingiu o limite máximo de {max_players} jogadores.")


def render_team_stats():
    st.header("Estatísticas do Time")
    team = st.session_state.user_team
    if not team or not team.get('id'):
        st.error("Não foi possível carregar as informações do seu time.")
        return

    team_id = team['id']
    st.subheader(f"Desempenho Geral - {team.get('name')}")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Posição", f"{get_team_position(team_id)}º")
    with col2:
        st.metric("Pontos", team.get('points', 0))
    with col3:
        st.metric("Jogos", team.get('games', 0))
    with col4:
         st.metric("Saldo Gols", team.get('goalsFor', 0) - team.get('goalsAgainst', 0))


    st.markdown("---")
    st.subheader("Histórico de Jogos")
    team_matches = [m for m in st.session_state.db.get('matches', []) if m.get('teamAId') == team_id or m.get('teamBId') == team_id]
    completed_team_matches = [m for m in team_matches if m.get('played')]
    upcoming_team_matches = [m for m in team_matches if not m.get('played') and not m.get('cancelled')]


    st.write("**Próximos Jogos:**")
    if upcoming_team_matches:
        for match in upcoming_team_matches:
             opponent = match.get('teamB') if match.get('teamAId') == team_id else match.get('teamA')
             st.write(f"- vs {opponent} em {match.get('date')}")
    else:
        st.info("Nenhum jogo futuro agendado.")

    st.write("**Resultados Anteriores:**")
    if completed_team_matches:
        # Sort by date, most recent first
        completed_team_matches_sorted = sorted(completed_team_matches, key=lambda x: datetime.datetime.strptime(x.get('date', '01/01/1900 00:00'), '%d/%m/%Y %H:%M'), reverse=True)
        results_data = []
        for match in completed_team_matches_sorted:
            is_team_a = match.get('teamAId') == team_id
            opponent = match.get('teamB') if is_team_a else match.get('teamA')
            score_own = match.get('scoreA') if is_team_a else match.get('scoreB')
            score_opp = match.get('scoreB') if is_team_a else match.get('scoreA')

            result_char = 'V' if score_own > score_opp else ('E' if score_own == score_opp else 'D')

            results_data.append({
                "Data": match.get('date'),
                "Adversário": opponent,
                "Placar": f"{score_own} x {score_opp}",
                "Resultado": result_char
            })
        df_results = pd.DataFrame(results_data)
        st.dataframe(df_results, use_container_width=True)

    else:
        st.info("Nenhum jogo anterior registrado.")

    st.markdown("---")
    st.subheader("Artilheiros do Time")
    team_players = get_team_players(team_id)
    scorers_data = []
    for player in team_players:
         goals = get_player_goals(player.get('id'))
         if goals > 0:
             scorers_data.append({ "Jogador": player.get('name'), "Gols": goals })

    if scorers_data:
        df_scorers = pd.DataFrame(scorers_data).sort_values(by="Gols", ascending=False).reset_index(drop=True)
        df_scorers.index += 1 # Start index at 1 for display
        st.dataframe(df_scorers, use_container_width=True)
    else:
        st.info("Nenhum jogador do time marcou gols ainda.")


# --- Admin Management Specific Tabs ---

def render_admin_teams():
    st.header("Gerenciar Times")

    teams = st.session_state.db.get('teams', [])
    if not teams:
        st.info("Nenhum time cadastrado ainda.")
         # Show add form even if no teams exist
        render_admin_add_team_form()
        return

    team_data = []
    team_options = {} # id: name mapping for selectbox
    for team in teams:
        team_id = team.get('id')
        team_data.append({
            # "ID": team_id,
            "Time": team.get('name', 'N/A'),
            "Representante": team.get('representative', {}).get('name', 'N/A'),
            "Contato": team.get('representative', {}).get('phone', 'N/A'),
            "Jogadores": len(get_team_players(team_id)),
            "Pontos": team.get('points', 0)
        })
        team_options[team_id] = team.get('name', 'N/A')

    df_teams = pd.DataFrame(team_data)
    st.dataframe(df_teams, use_container_width=True)

    st.markdown("---")
    st.subheader("Ações do Time")

    selected_team_id = st.selectbox(
        "Selecione um time para gerenciar",
        options=list(team_options.keys()),
        format_func=lambda x: f"{team_options[x]} (ID: ...{x[-4:]})" if x in team_options else "Selecione",
        index=0, # Or use a prompt by setting index=None if list is not empty
        key="admin_team_select"
    )

    if selected_team_id and selected_team_id in team_options:
        selected_team = get_team_by_id(selected_team_id)

        if selected_team:
            col1, col2, col3 = st.columns(3)

            with col1:
                # Edit Team Button / Form Expander
                with st.expander("Editar Informações do Time"):
                    with st.form(f"admin_edit_team_{selected_team_id}_form"):
                        st.write(f"Editando: **{selected_team.get('name')}**")
                        current_name = selected_team.get('name', '')
                        current_rep_name = selected_team.get('representative', {}).get('name', '')
                        current_rep_phone = selected_team.get('representative', {}).get('phone', '')

                        new_team_name = st.text_input("Nome do Time", value=current_name, key=f"admin_edit_team_name_{selected_team_id}")
                        new_rep_name = st.text_input("Nome Representante", value=current_rep_name, key=f"admin_edit_rep_name_{selected_team_id}")
                        new_rep_phone = st.text_input("Telefone Representante", value=current_rep_phone, key=f"admin_edit_rep_phone_{selected_team_id}")

                        edit_submitted = st.form_submit_button("Salvar Alterações do Time")

                        if edit_submitted:
                             if not all([new_team_name, new_rep_name, new_rep_phone]):
                                 st.error("Todos os campos são obrigatórios.")
                             else:
                                 team_index = next((i for i, t in enumerate(st.session_state.db['teams']) if t.get('id') == selected_team_id), None)
                                 if team_index is not None:
                                     st.session_state.db['teams'][team_index]['name'] = new_team_name
                                     st.session_state.db['teams'][team_index]['representative']['name'] = new_rep_name
                                     st.session_state.db['teams'][team_index]['representative']['phone'] = new_rep_phone

                                     # Update corresponding user name
                                     user_index = next((i for i, u in enumerate(st.session_state.db['users']) if u.get('teamId') == selected_team_id), None)
                                     if user_index is not None:
                                         st.session_state.db['users'][user_index]['name'] = new_team_name

                                     # Update match names involving this team
                                     for i, match in enumerate(st.session_state.db['matches']):
                                         if match.get('teamAId') == selected_team_id:
                                             st.session_state.db['matches'][i]['teamA'] = new_team_name
                                         elif match.get('teamBId') == selected_team_id:
                                             st.session_state.db['matches'][i]['teamB'] = new_team_name

                                     save_database()
                                     st.success("Time atualizado com sucesso!")
                                     st.rerun()
                                 else:
                                     st.error("Erro ao encontrar o time para atualizar.")


            with col2:
                 # View Players Button / Expander
                 with st.expander("Ver/Gerenciar Jogadores"):
                     team_players = get_team_players(selected_team_id)
                     st.write(f"**Jogadores de {selected_team.get('name')} ({len(team_players)}/15)**")
                     if team_players:
                        player_data_admin = []
                        for p in team_players:
                             birth_date_str = p.get('birthDate', 'N/A')
                             try:
                                 birth_date_obj = datetime.datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                                 birth_date_display = birth_date_obj.strftime('%d/%m/%Y')
                                 today = datetime.date.today()
                                 age = today.year - birth_date_obj.year - ((today.month, today.day) < (birth_date_obj.month, birth_date_obj.day))
                             except:
                                 birth_date_display = 'Inválida'
                                 age = 'N/A'

                             player_data_admin.append({
                                 "Nome": p.get('name'),
                                 "Nascimento": birth_date_display,
                                 "Idade": age,
                                 "Gols": get_player_goals(p.get('id'))
                             })
                        df_players_admin = pd.DataFrame(player_data_admin)
                        st.dataframe(df_players_admin, use_container_width=True)
                        # TODO: Add admin editing/removing players for a team? Maybe too complex for now.
                     else:
                         st.info(f"O time {selected_team.get('name')} ainda não tem jogadores registrados.")

            with col3:
                 # Remove Team Button with Confirmation
                if st.button(f"Remover Time {selected_team.get('name')}", key=f"admin_remove_{selected_team_id}", type="primary"):
                     confirm_key = f"admin_confirm_remove_team_{selected_team_id}"
                     if confirm_key not in st.session_state:
                         st.session_state[confirm_key] = False

                     st.session_state[confirm_key] = st.checkbox(f"**Confirmar remoção de {selected_team.get('name')}?**\n\nIsso removerá o time, a conta do representante, todos os jogadores associados e cancelará jogos futuros. Esta ação é IRREVERSÍVEL.", key=f"admin_check_remove_{selected_team_id}")

                     if st.session_state[confirm_key]:
                         # Proceed with removal
                         team_name_removed = selected_team.get('name')

                         # 1. Remove Team Record
                         st.session_state.db['teams'] = [t for t in st.session_state.db.get('teams', []) if t.get('id') != selected_team_id]

                         # 2. Remove Associated User Account
                         st.session_state.db['users'] = [u for u in st.session_state.db.get('users', []) if u.get('teamId') != selected_team_id]

                         # 3. Remove Associated Players and their Goals
                         players_to_remove = [p.get('id') for p in st.session_state.db.get('players', []) if p.get('teamId') == selected_team_id]
                         st.session_state.db['players'] = [p for p in st.session_state.db.get('players', []) if p.get('teamId') != selected_team_id]
                         st.session_state.db['goals'] = [g for g in st.session_state.db.get('goals', []) if g.get('playerId') not in players_to_remove]

                         # 4. Cancel/Remove Future Matches (or mark as cancelled)
                         updated_matches = []
                         for match in st.session_state.db.get('matches', []):
                             is_involved = match.get('teamAId') == selected_team_id or match.get('teamBId') == selected_team_id
                             if is_involved and not match.get('played'):
                                 # Option 1: Mark as cancelled
                                 # match['cancelled'] = True
                                 # updated_matches.append(match)
                                 # Option 2: Simply remove the match
                                 pass # Don't add it to the updated list
                             else:
                                 updated_matches.append(match)
                         st.session_state.db['matches'] = updated_matches

                         # 5. TODO: Handle Bets related to the removed team/matches? (Cancel active bets?)


                         save_database()
                         st.success(f"Time '{team_name_removed}' e todos os dados associados foram removidos com sucesso!")
                         del st.session_state[confirm_key] # Clean up state
                         st.rerun()
                     else:
                         st.info("Remoção cancelada.")


        else: # Should not happen if ID is from options
            st.error("Erro: Time selecionado não encontrado.")
    else:
        st.info("Selecione um time da lista acima para ver as ações.")


    st.markdown("---")
    # --- Add New Team Form (Always Visible or in Expander) ---
    render_admin_add_team_form()


def render_admin_add_team_form():
     with st.expander("Adicionar Novo Time", expanded=not st.session_state.db.get('teams', [])): # Expanded if no teams exist
        with st.form("admin_add_team_form", clear_on_submit=True):
            st.subheader("Cadastrar Novo Time")
            new_team_name = st.text_input("Nome do Time*", key="admin_add_team_name")
            new_rep_name = st.text_input("Nome do Representante*", key="admin_add_rep_name")
            new_rep_phone = st.text_input("Telefone*", key="admin_add_rep_phone")
            new_username = st.text_input("Nome de Usuário (login)*", key="admin_add_username")
            new_password = st.text_input("Senha (login)*", type="password", key="admin_add_password")

            add_submitted = st.form_submit_button("Adicionar Time")

            if add_submitted:
                errors = []
                if not all([new_team_name, new_rep_name, new_rep_phone, new_username, new_password]):
                    errors.append("Todos os campos são obrigatórios.")
                if any(u.get('username') == new_username for u in st.session_state.db.get('users', [])):
                    errors.append(f"O nome de usuário '{new_username}' já está em uso.")

                if errors:
                     for error in errors:
                         st.error(error)
                else:
                    team_id = f"team_{str(uuid.uuid4())[:8]}"
                    new_team = {
                        'id': team_id, 'name': new_team_name,
                        'representative': { 'name': new_rep_name, 'phone': new_rep_phone },
                        'points': 0, 'games': 0, 'wins': 0, 'draws': 0, 'losses': 0, 'goalsFor': 0, 'goalsAgainst': 0
                    }
                    st.session_state.db['teams'].append(new_team)

                    new_user = {
                        'id': f"user_{str(uuid.uuid4())[:8]}", 'username': new_username,
                        'password': new_password, 'type': 'team', 'teamId': team_id, 'name': new_team_name
                    }
                    st.session_state.db['users'].append(new_user)

                    save_database()
                    st.success(f"Time '{new_team_name}' adicionado com sucesso!")
                    st.rerun() # Refresh the teams list


def render_admin_results():
    st.header("Gerenciar Resultados e Jogos")

    # Use session state to keep track of the match being edited
    if 'selected_match_for_result' not in st.session_state:
         st.session_state.selected_match_for_result = None

    tab1, tab2, tab3 = st.tabs(["Adicionar/Editar Resultado", "Jogos Agendados", "Agendar Novo Jogo"])

    with tab1:
        st.subheader("Adicionar ou Editar Resultado de Jogo")

        # Select Match: Show completed first, then upcoming
        matches_for_results = get_completed_matches() + get_upcoming_matches()
        
        if not matches_for_results:
            st.info("Não há jogos disponíveis. Agende um jogo primeiro.")
            return
            
        match_options = {m.get('id'): f"{m.get('teamA')} vs {m.get('teamB')} ({m.get('date')}) {' - JÁ REALIZADO' if m.get('played') else ''}"
                         for m in matches_for_results}

        # Pre-select if navigated here with a specific match ID
        try:
            default_index = list(match_options.keys()).index(st.session_state.selected_match_for_result) if st.session_state.selected_match_for_result in match_options else 0
        except ValueError:
            default_index = 0 # Fallback if ID not found

        selected_match_id = st.selectbox(
             "Selecione o Jogo",
             options=list(match_options.keys()),
             format_func=lambda x: match_options[x] if x in match_options else "Selecione",
             index=default_index,
             key="result_match_select"
        )
        # Update the session state tracking variable when selection changes
        if selected_match_id != st.session_state.selected_match_for_result:
            st.session_state.selected_match_for_result = selected_match_id
            st.rerun() # Rerun to load the correct form state below

        # Render form only if a match is selected
        if st.session_state.selected_match_for_result:
            match = get_match_by_id(st.session_state.selected_match_for_result)
            if match:
                 render_add_edit_result_form(match)
            else:
                 st.error("Jogo selecionado não encontrado.")
        else:
             st.info("Selecione um jogo acima para adicionar ou editar o resultado.")


    with tab2:
        st.subheader("Próximos Jogos Agendados")
        upcoming = get_upcoming_matches()

        if upcoming:
            for match in upcoming:
                 match_id = match.get('id')
                 with st.expander(f"{match.get('teamA')} vs {match.get('teamB')} - {match.get('date')}"):
                    st.write(f"ID: {match_id}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Adicionar Resultado", key=f"add_res_btn_{match_id}"):
                             st.session_state.selected_match_for_result = match_id
                             st.rerun() # Will switch to the first tab and load the form

                    with col2:
                         # Cancel Match Button
                         if st.button("Cancelar Jogo", key=f"cancel_btn_{match_id}", type="secondary"):
                             confirm_key = f"admin_confirm_cancel_match_{match_id}"
                             if confirm_key not in st.session_state:
                                 st.session_state[confirm_key] = False

                             st.session_state[confirm_key] = st.checkbox(f"Confirmar cancelamento do jogo {match.get('teamA')} vs {match.get('teamB')}?", key=f"admin_check_cancel_{match_id}")

                             if st.session_state[confirm_key]:
                                 # Option 1: Mark as cancelled
                                 match_index = next((i for i, m in enumerate(st.session_state.db['matches']) if m.get('id') == match_id), None)
                                 if match_index is not None:
                                      st.session_state.db['matches'][match_index]['cancelled'] = True
                                      st.session_state.db['matches'][match_index]['played'] = False # Ensure played is false

                                      # TODO: Cancel associated bets?
                                      # cancel_bets_for_match(match_id)

                                      save_database()
                                      st.success("Jogo marcado como cancelado.")
                                      del st.session_state[confirm_key]
                                      st.rerun()
                                 else:
                                      st.error("Erro ao encontrar jogo para cancelar.")

                             else:
                                 st.info("Cancelamento de jogo não confirmado.")

        else:
            st.info("Não há jogos futuros agendados no momento.")

    with tab3:
        render_admin_schedule_match_form()


def render_add_edit_result_form(match):
    """Renders the form for adding or editing a match result."""
    match_id = match.get('id')
    team_a_id = match.get('teamAId')
    team_b_id = match.get('teamBId')
    team_a_name = match.get('teamA', 'Time A')
    team_b_name = match.get('teamB', 'Time B')
    is_played = match.get('played', False)

    st.markdown("---")
    st.subheader(f"Resultado: {team_a_name} vs {team_b_name}")
    st.caption(f"Data Original: {match.get('date')}")

    # --- Get current data if editing ---
    current_score_a = match.get('scoreA', 0 if is_played else None)
    current_score_b = match.get('scoreB', 0 if is_played else None)
    current_goals = [g for g in st.session_state.db.get('goals', []) if g.get('matchId') == match_id]

    with st.form(f"result_form_{match_id}", clear_on_submit=False):
        st.markdown("**Placar Final**")
        col_score1, col_score2 = st.columns(2)
        with col_score1:
             score_a = st.number_input(f"Gols {team_a_name}", min_value=0, value=current_score_a if current_score_a is not None else 0, step=1, key=f"scoreA_{match_id}")
        with col_score2:
             score_b = st.number_input(f"Gols {team_b_name}", min_value=0, value=current_score_b if current_score_b is not None else 0, step=1, key=f"scoreB_{match_id}")

        st.markdown("**Registro de Gols**")
        st.caption("Adicione cada gol individualmente. Gols contra são atribuídos ao jogador que marcou, mas contam para o time adversário.")

        # --- Goal Input Section ---
        if f"goals_input_{match_id}" not in st.session_state:
             # Initialize with existing goals if editing
             st.session_state[f"goals_input_{match_id}"] = current_goals[:] if is_played else []

        goal_entries = st.session_state[f"goals_input_{match_id}"]

        # Display current/added goals
        if goal_entries:
             st.write("**Gols Registrados:**")
             for i, goal in enumerate(goal_entries):
                 player = get_player_by_id(goal.get('playerId'))
                 goal_team = get_team_by_id(goal.get('teamId')) # Team of the player who scored
                 player_name = player.get('name', 'N/A') if player else 'N/A'
                 goal_team_name = goal_team.get('name', 'N/A') if goal_team else 'N/A'
                 goal_type = goal.get('type', 'normal')
                 type_str = "Pênalti" if goal_type == 'penalty' else ("Contra" if goal_type == 'own' else "Normal")

                 goal_desc = f"{i+1}. {player_name} ({goal_team_name}) - {type_str}"
                 if goal_type == 'own':
                      for_team = get_team_by_id(goal.get('forTeamId'))
                      goal_desc += f" (para {for_team.get('name', 'N/A')})"

                 col_desc, col_remove = st.columns([4, 1])
                 with col_desc:
                     st.write(goal_desc)
                 with col_remove:
                      if st.button("Remover", key=f"remove_goal_{match_id}_{i}"):
                          goal_entries.pop(i)
                          st.rerun() # Update display immediately


        # --- Form to Add New Goal ---
        st.markdown("**Adicionar Novo Gol:**")
        players_team_a = get_team_players(team_a_id)
        players_team_b = get_team_players(team_b_id)
        all_players = players_team_a + players_team_b
        player_options = {p.get('id'): f"{p.get('name')} ({get_team_by_id(p.get('teamId')).get('name')})" for p in all_players}

        if not player_options:
             st.warning("Não há jogadores cadastrados para os times desta partida. Cadastre jogadores antes de registrar gols.")
             goal_player_id = None
        else:
            goal_player_id = st.selectbox(
                 "Jogador que Marcou",
                 options=list(player_options.keys()),
                 format_func=lambda x: player_options.get(x, "Selecione"),
                 key=f"goal_player_{match_id}"
            )

        goal_type = st.selectbox("Tipo de Gol", ["normal", "penalty", "own"],
                                 format_func=lambda x: "Normal" if x=="normal" else ("Pênalti" if x=="penalty" else "Gol Contra"),
                                 key=f"goal_type_{match_id}")

        if st.button("Adicionar Gol à Lista", key=f"add_goal_btn_{match_id}"):
             if goal_player_id and goal_player_id in player_options:
                 player = get_player_by_id(goal_player_id)
                 scorer_team_id = player.get('teamId')
                 for_team_id = None # Only for own goals

                 if goal_type == 'own':
                      # Own goal counts for the *other* team
                      for_team_id = team_b_id if scorer_team_id == team_a_id else team_a_id

                 new_goal = {
                     # Generate a unique ID for the goal if needed for editing later, or rely on list index for now
                     # 'goalId': f"goal_{match_id}_{str(uuid.uuid4())[:4]}",
                     'playerId': goal_player_id,
                     'teamId': scorer_team_id, # Team of the player who scored
                     'matchId': match_id,
                     'type': goal_type,
                     'forTeamId': for_team_id # Indicates which team gets the goal credit (especially for OG)
                 }
                 goal_entries.append(new_goal)
                 st.rerun() # Update display
             else:
                 st.error("Selecione um jogador válido.")


        st.markdown("---")
        form_submit_button_text = "Salvar Resultado Final" if not is_played else "Atualizar Resultado"
        submitted = st.form_submit_button(form_submit_button_text)

        if submitted:
            # --- Validation ---
            # 1. Check if total registered goals match the final score
            calculated_score_a = 0
            calculated_score_b = 0
            for goal in goal_entries:
                 goal_team_gets_point = goal.get('forTeamId') if goal.get('type') == 'own' else goal.get('teamId')
                 if goal_team_gets_point == team_a_id:
                     calculated_score_a += 1
                 elif goal_team_gets_point == team_b_id:
                     calculated_score_b += 1

            if calculated_score_a != score_a or calculated_score_b != score_b:
                st.error(f"Erro: O placar final ({score_a}x{score_b}) não corresponde ao número de gols registrados ({calculated_score_a}x{calculated_score_b}). Verifique os gols.")
                # Prevent saving if scores don't match
            else:
                # --- Save Data ---
                match_index = next((i for i, m in enumerate(st.session_state.db['matches']) if m.get('id') == match_id), None)
                if match_index is None:
                     st.error("Erro fatal: Jogo não encontrado no banco de dados para salvar.")
                     return # Stop execution

                # Get previous state for comparison if editing
                prev_score_a = st.session_state.db['matches'][match_index].get('scoreA')
                prev_score_b = st.session_state.db['matches'][match_index].get('scoreB')
                was_played = st.session_state.db['matches'][match_index].get('played', False)

                # --- Update Match Record ---
                st.session_state.db['matches'][match_index]['scoreA'] = score_a
                st.session_state.db['matches'][match_index]['scoreB'] = score_b
                st.session_state.db['matches'][match_index]['played'] = True
                st.session_state.db['matches'][match_index]['cancelled'] = False # Ensure not cancelled


                # --- Update Goal Records ---
                # Remove old goals for this match, then add the current list
                st.session_state.db['goals'] = [g for g in st.session_state.db.get('goals', []) if g.get('matchId') != match_id]
                st.session_state.db['goals'].extend(goal_entries) # Add the ones from the form state


                # --- Update Team Stats ---
                team_a_index = next((i for i, t in enumerate(st.session_state.db['teams']) if t.get('id') == team_a_id), None)
                team_b_index = next((i for i, t in enumerate(st.session_state.db['teams']) if t.get('id') == team_b_id), None)

                if team_a_index is not None and team_b_index is not None:
                    # Adjust stats based on whether this is a new result or an update
                    update_team_stats(team_a_index, team_b_index, score_a, score_b, was_played, prev_score_a, prev_score_b)
                else:
                    st.warning("Não foi possível atualizar as estatísticas dos times (times não encontrados).")


                 # --- Update Bet Statuses ---
                resolve_bets_for_match(match_id, score_a, score_b)

                # --- Final Steps ---
                save_database()
                st.success(f"Resultado do jogo {team_a_name} vs {team_b_name} salvo com sucesso!")

                # Clear the goal input state for this match
                del st.session_state[f"goals_input_{match_id}"]
                st.session_state.selected_match_for_result = None # Reset selection

                st.rerun()


def update_team_stats(team_a_idx, team_b_idx, score_a, score_b, was_played, prev_score_a, prev_score_b):
    """Updates points, wins, draws, losses, goals for/against for both teams based on a match result.
       Handles both adding a new result and updating an existing one.
    """
    team_a = st.session_state.db['teams'][team_a_idx]
    team_b = st.session_state.db['teams'][team_b_idx]

    # --- Revert previous stats if it was already played ---
    if was_played and prev_score_a is not None and prev_score_b is not None:
        team_a['games'] -= 1
        team_b['games'] -= 1
        team_a['goalsFor'] -= prev_score_a
        team_a['goalsAgainst'] -= prev_score_b
        team_b['goalsFor'] -= prev_score_b
        team_b['goalsAgainst'] -= prev_score_a

        # Revert points and W/D/L
        if prev_score_a > prev_score_b: # Team A won previously
            team_a['points'] -= 3
            team_a['wins'] -= 1
            team_b['losses'] -= 1
        elif prev_score_b > prev_score_a: # Team B won previously
            team_b['points'] -= 3
            team_b['wins'] -= 1
            team_a['losses'] -= 1
        else: # Draw previously
            team_a['points'] -= 1
            team_b['points'] -= 1
            team_a['draws'] -= 1
            team_b['draws'] -= 1

    # --- Apply new stats ---
    team_a['games'] += 1
    team_b['games'] += 1
    team_a['goalsFor'] += score_a
    team_a['goalsAgainst'] += score_b
    team_b['goalsFor'] += score_b
    team_b['goalsAgainst'] += score_a

    # Apply points and W/D/L
    if score_a > score_b: # Team A wins
        team_a['points'] += 3
        team_a['wins'] += 1
        team_b['losses'] += 1
    elif score_b > score_a: # Team B wins
        team_b['points'] += 3
        team_b['wins'] += 1
        team_a['losses'] += 1
    else: # Draw
        team_a['points'] += 1
        team_b['points'] += 1
        team_a['draws'] += 1
        team_b['draws'] += 1

    # Update the database directly (or rely on save_database being called after this)
    st.session_state.db['teams'][team_a_idx] = team_a
    st.session_state.db['teams'][team_b_idx] = team_b


def render_admin_schedule_match_form():
    """Renders the form for scheduling a new match."""
    st.subheader("Agendar Novo Jogo")

    teams = st.session_state.db.get('teams', [])
    if len(teams) < 2:
        st.warning("É preciso ter pelo menos 2 times cadastrados para agendar um jogo.")
        return

    team_options = {team.get('id'): team.get('name', 'N/A') for team in teams}
    team_ids = list(team_options.keys())
    team_names = list(team_options.values())


    with st.form("schedule_match_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            team_a_id = st.selectbox("Time A*", options=team_ids, format_func=lambda x: team_options.get(x, "Selecione"), key="schedule_team_a")
        with col2:
             # Filter out selected team A for team B options
            team_b_options_filtered = {id: name for id, name in team_options.items() if id != team_a_id}
            team_b_id = st.selectbox("Time B*", options=list(team_b_options_filtered.keys()), format_func=lambda x: team_b_options_filtered.get(x, "Selecione"), key="schedule_team_b")


        # Use datetime input for better UX potentially, or keep separate date/time
        match_date = st.date_input("Data do Jogo*", value=datetime.date.today(), min_value=datetime.date.today(), key="schedule_date")
        match_time = st.time_input("Horário*", value=datetime.time(15, 0), key="schedule_time")

        submitted = st.form_submit_button("Agendar Jogo")

        if submitted:
            errors = []
            if not team_a_id or not team_b_id:
                 errors.append("Selecione ambos os times.")
            elif team_a_id == team_b_id: # Should be prevented by filtering, but double check
                errors.append("Os times A e B devem ser diferentes.")
            if not match_date or not match_time:
                errors.append("Selecione a data e o horário do jogo.")

            if errors:
                for error in errors:
                    st.error(error)
            else:
                team_a = get_team_by_id(team_a_id)
                team_b = get_team_by_id(team_b_id)

                match_datetime = datetime.datetime.combine(match_date, match_time)
                formatted_datetime = match_datetime.strftime('%d/%m/%Y %H:%M') # Consistent format

                new_match = {
                    'id': f"match_{str(uuid.uuid4())[:8]}", # Unique ID
                    'teamAId': team_a_id,
                    'teamBId': team_b_id,
                    'teamA': team_a.get('name'),
                    'teamB': team_b.get('name'),
                    'date': formatted_datetime,
                    'played': False,
                    'cancelled': False,
                     # Initialize scores to None or omit until played
                    # 'scoreA': None,
                    # 'scoreB': None
                }

                st.session_state.db['matches'].append(new_match)
                save_database()
                st.success(f"Jogo entre {team_a.get('name')} e {team_b.get('name')} agendado para {formatted_datetime}!")
                st.rerun() # Refresh the lists


def render_admin_betting():
    st.header("Gerenciar Apostas")

    tab1, tab2, tab3 = st.tabs(["Apostas Ativas", "Criar Nova Aposta", "Histórico de Apostas"])

    with tab1:
        st.subheader("Apostas Ativas Pendentes")
        active_bets = get_active_bets()

        if active_bets:
            for bet in active_bets:
                bet_id = bet.get('id')
                match_id = bet.get('matchId')
                match_name = get_match_name(match_id) if match_id else "Geral/Custom"

                with st.expander(f"{bet.get('description', 'Aposta')} (Odd: {bet.get('odd'):.2f}) - {match_name}"):
                    st.write(f"ID da Aposta: {bet_id}")
                    st.write(f"Criada em: {format_date(bet.get('createdAt', ''))}")

                    # Get user bets placed on this active bet
                    placed_user_bets = [ub for ub in st.session_state.db.get('userBets', []) if ub.get('betId') == bet_id]
                    total_staked = sum(ub.get('amount', 0) for ub in placed_user_bets)
                    st.write(f"Apostas realizadas: {len(placed_user_bets)} (Total: {total_staked:,} pontos)")

                    # Buttons to resolve the bet
                    st.markdown("**Finalizar Aposta:**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        if st.button("Marcar como GANHA", key=f"resolve_win_{bet_id}"):
                             resolve_bet(bet_id, 'won')
                             st.rerun()
                    with col2:
                        if st.button("Marcar como PERDIDA", key=f"resolve_lose_{bet_id}"):
                             resolve_bet(bet_id, 'lost')
                             st.rerun()
                    with col3:
                         # Option to cancel an active bet (e.g., if match cancelled)
                         if st.button("Cancelar Aposta", key=f"cancel_bet_{bet_id}", type="secondary"):
                             cancel_bet(bet_id)
                             st.rerun()

                    # TODO: Add editing functionality if needed (might be complex if bets already placed)
                    # if st.button("Editar Aposta", key=f"edit_bet_{bet_id}"):
                    #     st.warning("Edição de apostas ativas ainda não implementada.")

        else:
            st.info("Não há apostas ativas no momento.")

    with tab2:
        render_admin_create_bet_form()

    with tab3:
        st.subheader("Histórico de Apostas Finalizadas")
        completed_bets = get_completed_bets()

        if completed_bets:
            # Sort by resolved date if available, otherwise creation date
            completed_bets_sorted = sorted(completed_bets, key=lambda x: x.get('resolvedAt', x.get('createdAt', '')), reverse=True)

            history_data = []
            for bet in completed_bets_sorted:
                bet_id = bet.get('id')
                status = bet.get('status', 'N/A').capitalize()
                result = bet.get('result', 'N/A').capitalize() if status == 'Completed' else 'N/A'
                if status == 'Cancelled':
                    result = 'Cancelada'

                # Calculate total payout vs total stake for completed bets
                user_bets_on_this = [ub for ub in st.session_state.db.get('userBets',[]) if ub.get('betId') == bet_id]
                total_stake = sum(ub.get('amount',0) for ub in user_bets_on_this)
                total_payout = sum(ub.get('payout',0) for ub in user_bets_on_this) # payout stored when resolved

                history_data.append({
                    "Descrição": bet.get('description', 'Aposta'),
                    "Odd": f"{bet.get('odd', 1.0):.2f}",
                    "Status": status,
                    "Resultado": result,
                    "Total Apostado": f"{total_stake:,}",
                    "Total Pago": f"{total_payout:,}" if status == 'Completed' else 'N/A',
                    "Finalizada em": format_date(bet.get('resolvedAt', bet.get('createdAt', '')))
                })

            df_history = pd.DataFrame(history_data)
            st.dataframe(df_history, use_container_width=True)
        else:
            st.info("Não há apostas finalizadas no histórico.")


def render_admin_create_bet_form():
    """Form for Admin to create new betting opportunities."""
    st.subheader("Criar Nova Oportunidade de Aposta")

    with st.form("create_bet_form", clear_on_submit=True):
        bet_type = st.selectbox(
            "Tipo de Aposta",
            options=["match_result", "custom"],
            format_func=lambda x: "Resultado de Jogo Específico" if x == "match_result" else "Aposta Personalizada (Ex: Artilheiro, Campeão)",
            key="bet_create_type"
        )

        match_id = None
        bet_description = ""

        if bet_type == "match_result":
            st.markdown("**Selecione o Jogo e o Resultado:**")
            upcoming_matches = get_upcoming_matches()
            if not upcoming_matches:
                st.warning("Não há jogos futuros agendados para criar apostas de resultado.")
                submitted = st.form_submit_button("Criar Aposta", disabled=True) # Disable if no matches
                return # Exit form rendering if no matches

            match_options = {m.get('id'): f"{m.get('teamA')} vs {m.get('teamB')} ({m.get('date')})" for m in upcoming_matches}
            selected_match_id = st.selectbox(
                "Jogo*",
                options=list(match_options.keys()),
                format_func=lambda x: match_options.get(x, "Selecione"),
                key="bet_create_match"
            )

            if selected_match_id:
                match_id = selected_match_id
                selected_match = get_match_by_id(selected_match_id)
                team_a_name = selected_match.get('teamA')
                team_b_name = selected_match.get('teamB')

                outcome = st.selectbox(
                    "Resultado a Apostar*",
                    options=["teamA_win", "draw", "teamB_win"],
                    format_func=lambda x: f"{team_a_name} Vence" if x == "teamA_win" else ("Empate" if x == "draw" else f"{team_b_name} Vence"),
                    key="bet_create_outcome"
                )

                # Auto-generate description based on match and outcome
                if outcome == "teamA_win":
                    bet_description = f"Resultado: {team_a_name} vence {team_b_name}"
                elif outcome == "draw":
                    bet_description = f"Resultado: Empate entre {team_a_name} e {team_b_name}"
                else: # teamB_win
                    bet_description = f"Resultado: {team_b_name} vence {team_a_name}"

                # Display the auto-generated description
                st.text_input("Descrição (Automática)", value=bet_description, disabled=True, key="bet_desc_auto")

        elif bet_type == "custom":
            st.markdown("**Defina a Aposta Personalizada:**")
            bet_description = st.text_input("Descrição da Aposta*", placeholder="Ex: Jogador X será o artilheiro", key="bet_create_desc_custom")


        bet_odd = st.number_input("Odd (Multiplicador)*", min_value=1.01, value=2.0, step=0.05, format="%.2f", key="bet_create_odd")

        submitted = st.form_submit_button("Criar Aposta")

        if submitted:
            errors = []
            if bet_type == "match_result" and not match_id:
                errors.append("Selecione um jogo válido para apostas de resultado.")
            if not bet_description:
                 errors.append("A descrição da aposta é obrigatória.")
            if bet_odd <= 1.0:
                 errors.append("A Odd deve ser maior que 1.0.")

            # Check for duplicate active bets (optional but good practice)
            # E.g., check if an active bet with the same description or matchId/outcome already exists

            if errors:
                 for error in errors:
                     st.error(error)
            else:
                new_bet_id = f"bet_{str(uuid.uuid4())[:8]}"
                new_bet = {
                    'id': new_bet_id,
                    'description': bet_description,
                    'odd': float(bet_odd),
                    'matchId': match_id, # Will be None for custom bets
                    'status': 'active', # Bets start as active
                    'createdAt': datetime.datetime.now().isoformat(),
                    'outcome_condition': outcome if bet_type == "match_result" else None, # Store condition for match results
                    'result': None, # Result is determined later (won/lost)
                    'resolvedAt': None
                }

                st.session_state.db['bets'].append(new_bet)
                save_database()
                st.success(f"Aposta '{bet_description}' criada com sucesso!")
                st.rerun() # Refresh the active bets list


def resolve_bet(bet_id, result):
    """Resolves an active bet (marks as won or lost) and updates user points."""
    bet_index = next((i for i, b in enumerate(st.session_state.db['bets']) if b.get('id') == bet_id), None)
    if bet_index is None:
        st.error(f"Aposta com ID {bet_id} não encontrada.")
        return

    bet = st.session_state.db['bets'][bet_index]
    if bet.get('status') != 'active':
        st.warning(f"Aposta {bet_id} não está ativa, status atual: {bet.get('status')}")
        return

    bet['status'] = 'completed'
    bet['result'] = result # 'won' or 'lost'
    bet['resolvedAt'] = datetime.datetime.now().isoformat()

    # Find all user bets placed on this bet
    user_bets_indices = [i for i, ub in enumerate(st.session_state.db.get('userBets', [])) if ub.get('betId') == bet_id]

    if not user_bets_indices:
         st.info("Nenhum torcedor apostou nesta opção.")
         # Just update the bet status
         st.session_state.db['bets'][bet_index] = bet
         save_database()
         st.success(f"Aposta {bet_id} finalizada como '{result}'.")
         return

    odd = bet.get('odd', 1.0)
    bet_desc = bet.get('description', 'Aposta')

    total_paid_out = 0
    users_updated = 0

    for idx in user_bets_indices:
         user_bet = st.session_state.db['userBets'][idx]
         user_id = user_bet.get('userId')
         amount = user_bet.get('amount', 0)

         user_index = next((i for i, u in enumerate(st.session_state.db['users']) if u.get('id') == user_id), None)
         if user_index is None:
             st.warning(f"Usuário {user_id} da aposta não encontrado, pulando pagamento.")
             continue

         user = st.session_state.db['users'][user_index]
         payout = 0
         if result == 'won':
             payout = amount * odd
             user['points'] = user.get('points', 0) + payout
             total_paid_out += payout
             users_updated += 1
         else: # Bet lost, user loses the staked amount (already deducted when placed)
             payout = 0 # No payout

         # Update the userBet record itself (optional, but good for history)
         user_bet['status'] = 'completed'
         user_bet['result'] = result
         user_bet['payout'] = payout
         st.session_state.db['userBets'][idx] = user_bet

         # Update user in the database
         st.session_state.db['users'][user_index] = user


    # Update the main bet record
    st.session_state.db['bets'][bet_index] = bet
    save_database()

    if result == 'won':
        st.success(f"Aposta '{bet_desc}' finalizada como GANHA. {users_updated} torcedores receberam {total_paid_out:,.0f} pontos no total.")
    else:
         st.success(f"Aposta '{bet_desc}' finalizada como PERDIDA. {len(user_bets_indices)} apostas foram resolvidas.")


def cancel_bet(bet_id):
    """Cancels an active bet and refunds any placed user bets."""
    bet_index = next((i for i, b in enumerate(st.session_state.db['bets']) if b.get('id') == bet_id), None)
    if bet_index is None:
        st.error(f"Aposta com ID {bet_id} não encontrada.")
        return

    bet = st.session_state.db['bets'][bet_index]
    if bet.get('status') != 'active':
        st.warning(f"Aposta {bet_id} não está ativa para cancelar, status atual: {bet.get('status')}")
        return

    bet['status'] = 'cancelled'
    bet['result'] = 'cancelled' # Indicate cancellation result
    bet['resolvedAt'] = datetime.datetime.now().isoformat()

    # Find and refund user bets
    user_bets_indices = [i for i, ub in enumerate(st.session_state.db.get('userBets', [])) if ub.get('betId') == bet_id]
    total_refunded = 0
    users_refunded = 0

    for idx in user_bets_indices:
         user_bet = st.session_state.db['userBets'][idx]
         user_id = user_bet.get('userId')
         amount = user_bet.get('amount', 0)

         user_index = next((i for i, u in enumerate(st.session_state.db['users']) if u.get('id') == user_id), None)
         if user_index is None:
             st.warning(f"Usuário {user_id} da aposta não encontrado, pulando reembolso.")
             continue

         user = st.session_state.db['users'][user_index]
         # Refund the original amount
         user['points'] = user.get('points', 0) + amount
         total_refunded += amount
         users_refunded += 1

         # Update the userBet record
         user_bet['status'] = 'cancelled'
         user_bet['result'] = 'refunded'
         user_bet['payout'] = amount # Store refunded amount as payout
         st.session_state.db['userBets'][idx] = user_bet

         # Update user in the database
         st.session_state.db['users'][user_index] = user

    # Update the main bet record
    st.session_state.db['bets'][bet_index] = bet
    save_database()

    st.success(f"Aposta '{bet.get('description', 'Aposta')}' cancelada. {users_refunded} torcedores reembolsados no total de {total_refunded:,.0f} pontos.")


def resolve_bets_for_match(match_id, score_a, score_b):
    """Finds and resolves all 'match_result' bets related to a completed match."""
    st.write(f"Resolvendo apostas para o jogo ID: {match_id}...")
    match_bets = [b for b in st.session_state.db.get('bets', [])
                  if b.get('matchId') == match_id and b.get('status') == 'active' and b.get('outcome_condition')]

    if not match_bets:
        st.info(f"Nenhuma aposta ativa encontrada para resolver para o jogo ID {match_id}.")
        return

    # Determine match outcome string based on score
    if score_a > score_b:
        match_outcome = "teamA_win"
    elif score_b > score_a:
        match_outcome = "teamB_win"
    else:
        match_outcome = "draw"

    resolved_count = 0
    for bet in match_bets:
        bet_id = bet.get('id')
        bet_condition = bet.get('outcome_condition')

        if bet_condition == match_outcome:
            resolve_bet(bet_id, 'won') # Bet condition met, mark as won
        else:
            resolve_bet(bet_id, 'lost') # Bet condition not met, mark as lost
        resolved_count += 1

    st.success(f"{resolved_count} apostas de resultado resolvidas para o jogo ID {match_id}.")



def render_settings():
     st.title("Configurações")
     st.info("Página de configurações em desenvolvimento.")
     # Add any general settings here, e.g., changing admin password, league name, rules display?


# --- Fan Management Specific Tabs ---

def render_my_bets():
    st.header("Minhas Apostas")
    user = st.session_state.current_user
    if not user or st.session_state.user_type != 'fan':
        st.error("Acesso não autorizado.")
        return

    user_id = user.get('id')
    st.metric("Pontos Disponíveis", f"{user.get('points', 0):,}")

    tab1, tab2, tab3 = st.tabs(["Apostar Agora", "Minhas Apostas Ativas", "Histórico de Apostas"])

    with tab1:
        st.subheader("Oportunidades de Aposta")
        active_bets = get_active_bets()

        if not active_bets:
            st.info("Não há apostas disponíveis no momento. Volte mais tarde!")
        else:
            # Group bets by match?
            bets_by_match = {}
            general_bets = []
            for bet in active_bets:
                match_id = bet.get('matchId')
                if match_id:
                    if match_id not in bets_by_match:
                         match = get_match_by_id(match_id)
                         if match: # Ensure match exists
                            bets_by_match[match_id] = {'match_info': match, 'bets': []}
                         else:
                              continue # Skip bet if match not found
                    if match_id in bets_by_match: # Check again after potentially adding
                        bets_by_match[match_id]['bets'].append(bet)
                else:
                    general_bets.append(bet)

            # Display bets grouped by match
            upcoming_matches_with_bets = sorted(
                 [m_data for m_id, m_data in bets_by_match.items()],
                 key=lambda x: datetime.datetime.strptime(x['match_info'].get('date', '01/01/1900 00:00'), '%d/%m/%Y %H:%M')
            )


            for match_data in upcoming_matches_with_bets:
                 match_info = match_data['match_info']
                 match_bets = match_data['bets']
                 match_id = match_info.get('id')
                 st.markdown("---")
                 st.subheader(f"Jogo: {match_info.get('teamA')} vs {match_info.get('teamB')} ({match_info.get('date')})")

                 for bet in match_bets:
                     render_bet_card(bet, user_id)


            # Display general/custom bets
            if general_bets:
                st.markdown("---")
                st.subheader("Apostas Gerais / Especiais")
                for bet in general_bets:
                    render_bet_card(bet, user_id)


    with tab2:
        st.subheader("Apostas Ativas que Você Realizou")
        user_active_bets = [ub for ub in st.session_state.db.get('userBets', [])
                           if ub.get('userId') == user_id and ub.get('status', 'active') == 'active']

        if not user_active_bets:
            st.info("Você não tem nenhuma aposta ativa no momento.")
        else:
            for user_bet in user_active_bets:
                bet_id = user_bet.get('betId')
                bet_info = get_bet_by_id(bet_id)
                if bet_info:
                    st.markdown(f"""
                    <div class="matches-card">
                        <strong>{bet_info.get('description', 'Aposta')}</strong> (Odd: {bet_info.get('odd'):.2f})<br>
                        <small>Você apostou: {user_bet.get('amount'):,} pontos</small><br>
                        <small>Possível Retorno: {(user_bet.get('amount', 0) * bet_info.get('odd', 1)):,.0f} pontos</small><br>
                        <small>Status: {user_bet.get('status', 'Ativa').capitalize()}</small>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning(f"Informação da aposta ID {bet_id} não encontrada.")


    with tab3:
        st.subheader("Seu Histórico de Apostas")
        user_completed_bets = [ub for ub in st.session_state.db.get('userBets', [])
                              if ub.get('userId') == user_id and ub.get('status') != 'active']


        if not user_completed_bets:
            st.info("Você ainda não tem histórico de apostas.")
        else:
             # Sort by resolved date? Need to fetch bet info
            history_data = []
            for user_bet in user_completed_bets:
                 bet_id = user_bet.get('betId')
                 bet_info = get_bet_by_id(bet_id)
                 if not bet_info: continue # Skip if original bet not found

                 result = user_bet.get('result', 'N/A').capitalize()
                 payout = user_bet.get('payout', 0)
                 amount = user_bet.get('amount', 0)
                 profit_loss = payout - amount if result != 'Refunded' else 0
                 profit_loss_str = f"{profit_loss:+,}" if result != 'Refunded' else "Reembolsado"

                 history_data.append({
                    "Descrição": bet_info.get('description', 'N/A'),
                    "Apostado": f"{amount:,}",
                    "Odd": f"{bet_info.get('odd', 1.0):.2f}",
                    "Resultado": result,
                    "Retorno": f"{payout:,}",
                    "Lucro/Prejuízo": profit_loss_str,
                    "Data": format_date(bet_info.get('resolvedAt', bet_info.get('createdAt', '')))
                 })

            # Sort by date descending
            history_data_sorted = sorted(history_data, key=lambda x: datetime.datetime.strptime(x['Data'], '%d/%m/%Y %H:%M:%S') if '/' in x['Data'] else datetime.datetime.min, reverse=True)

            df_history = pd.DataFrame(history_data_sorted)
            st.dataframe(df_history, use_container_width=True)



def render_bet_card(bet, user_id):
    """Displays a card for placing a bet."""
    bet_id = bet.get('id')
    bet_desc = bet.get('description', 'Aposta')
    bet_odd = bet.get('odd', 1.0)
    user = st.session_state.current_user
    user_points = user.get('points', 0)

    # Check if user already placed this specific bet
    user_has_bet = any(ub.get('betId') == bet_id and ub.get('userId') == user_id
                       for ub in st.session_state.db.get('userBets', []))


    st.markdown(f"""
    <div class="matches-card">
        <strong>{bet_desc}</strong><br>
        <span style="font-size: 1.1em; color: #4CAF50; font-weight: bold;">Odd: {bet_odd:.2f}</span>
    </div>
    """, unsafe_allow_html=True)

    if user_has_bet:
        st.success("✔️ Você já apostou nisso.")
    elif user_points <= 0:
         st.warning("Você não tem pontos suficientes para apostar.")
    else:
        # Unique key combining bet_id and maybe a counter/timestamp if needed
        form_key = f"place_bet_form_{bet_id}"
        amount_key = f"amount_{bet_id}"
        button_key = f"button_{bet_id}"

        with st.form(key=form_key):
            amount_col, button_col = st.columns([2,1])
            with amount_col:
                 amount = st.number_input(
                     "Pontos a Apostar",
                     min_value=10, # Minimum bet
                     max_value=user_points,
                     value=10, # Default bet
                     step=10,
                     key=amount_key,
                     label_visibility="collapsed", # Hide label, use placeholder or title above
                     help=f"Você tem {user_points:,} pontos."
                 )
            with button_col:
                 submitted = st.form_submit_button("Apostar!", key=button_key, use_container_width=True)

            if submitted:
                 if amount > user_points:
                     st.error("Pontos insuficientes!")
                 elif amount < 10:
                      st.error("Aposta mínima é de 10 pontos.")
                 else:
                     place_bet(bet_id, amount)
                     st.rerun() # Update UI


def place_bet(bet_id, amount):
    """Logic for a fan placing a bet."""
    user = st.session_state.current_user
    user_id = user.get('id')
    user_points = user.get('points', 0)
    bet = get_bet_by_id(bet_id)

    # --- Validations ---
    if not bet or bet.get('status') != 'active':
        st.error("Esta aposta não está mais ativa.")
        return
    if amount <= 0:
        st.error("Valor da aposta deve ser positivo.")
        return
    if amount > user_points:
        st.error("Pontos insuficientes.")
        return
    # Check if user already placed this bet
    if any(ub.get('betId') == bet_id and ub.get('userId') == user_id for ub in st.session_state.db.get('userBets', [])):
        st.error("Você já fez essa aposta.")
        return

    # --- Process Bet ---
    # 1. Deduct points from user
    user_index = next((i for i, u in enumerate(st.session_state.db['users']) if u.get('id') == user_id), None)
    if user_index is None:
         st.error("Erro ao encontrar usuário.")
         return
    st.session_state.db['users'][user_index]['points'] -= amount

    # 2. Create UserBet record
    user_bet_id = f"userbet_{user_id}_{bet_id}_{str(uuid.uuid4())[:4]}" # Unique ID
    new_user_bet = {
        'id': user_bet_id,
        'userId': user_id,
        'betId': bet_id,
        'amount': amount,
        'oddPlaced': bet.get('odd'), # Record odd at time of placing
        'placedAt': datetime.datetime.now().isoformat(),
        'status': 'active', # User bet is active until resolved
        'result': None,
        'payout': None
    }
    st.session_state.db['userBets'].append(new_user_bet)

    # 3. Update current user state in session
    st.session_state.current_user['points'] -= amount

    # 4. Save
    save_database()

    st.success(f"Aposta de {amount:,} pontos realizada com sucesso em '{bet.get('description')}'!")


# Main application flow
def main():
    # Render sidebar for navigation - it now handles page changes and reruns
    render_sidebar()

    # Main content area based on current page state
    page = st.session_state.get('page', 'home') # Default to home

    # Map page state to rendering function
    page_render_functions = {
        'home': render_home,
        'classification': render_classification,
        'topScorers': render_top_scorers,
        'matches': render_matches,
        'login': render_login,
        'register_choice': render_register_choice, # Added choice page
        'register_team': render_register_team,
        'register_fan': render_register_fan,
        'dashboard': render_dashboard,
        # Add mappings for functions called *within* dashboard tabs if they should also be top-level pages
        'my_team': render_my_team_management, # If accessible directly
        'players': render_player_management, # If accessible directly
        'stats': render_team_stats,          # If accessible directly
        'teams': render_admin_teams,         # If accessible directly (admin)
        'results': render_admin_results,       # If accessible directly (admin)
        'betting': render_admin_betting,       # If accessible directly (admin)
        'settings': render_settings,         # If accessible directly (admin)
        'my_bets': render_my_bets            # If accessible directly (fan)
    }

    render_func = page_render_functions.get(page)

    if render_func:
        render_func()
    else:
        # Fallback to home if page state is invalid
        st.warning(f"Página '{page}' não encontrada. Redirecionando para o início.")
        st.session_state.page = 'home'
        render_home()


if __name__ == "__main__":
    main()
