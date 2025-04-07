import streamlit as st
import pandas as pd
import datetime
import uuid
import json
import os
from streamlit_option_menu import option_menu

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

# Initialize authentication state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = None
    st.session_state.user_type = None
    st.session_state.user_team = None

# Initialize navigation state
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'home'

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
    st.session_state.current_page = 'home'

# UI Components
def render_header():
    st.markdown("""
    <div style="background-color: #1a2a3a; padding: 15px; border-radius: 10px; display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px">
        <div style="display: flex; align-items: center;">
            <div style="background-color: #1a2a3a; padding: 10px; border-radius: 10px; border: 2px solid #4CAF50; margin-right: 20px">
                <h1 style="color: white; margin: 0; font-size: 24px">MATHEUZINHO</h1>
                <h2 style="color: #4CAF50; margin: 0; font-size: 28px">LEAGUE</h2>
            </div>
            <h3 style="color: white; margin: 0">Copa Sub-13 de Futsal</h3>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Main navigation with nice icons
    selected = option_menu(
        menu_title=None,
        options=["Início", "Classificação", "Artilharia", "Jogos", 
                 "Login" if not st.session_state.logged_in else "Painel", 
                 "Cadastro" if not st.session_state.logged_in else "Sair"],
        icons=["house", "trophy", "star", "calendar", 
               "box-arrow-in-right" if not st.session_state.logged_in else "speedometer", 
               "person-plus" if not st.session_state.logged_in else "box-arrow-right"],
        menu_icon="cast",
        default_index=0,
        orientation="horizontal",
        styles={
            "container": {"padding": "0!important", "background-color": "#f0f2f6"},
            "icon": {"color": "#4CAF50", "font-size": "14px"}, 
            "nav-link": {"font-size": "14px", "text-align": "center", "margin":"0px", "--hover-color": "#eee"},
            "nav-link-selected": {"background-color": "#4CAF50"},
        }
    )
    
    # Handle navigation based on selection
    if selected == "Início":
        st.session_state.current_page = 'home'
    elif selected == "Classificação":
        st.session_state.current_page = 'classification'
    elif selected == "Artilharia":
        st.session_state.current_page = 'topScorers'
    elif selected == "Jogos":
        st.session_state.current_page = 'matches'
    elif selected == "Login":
        st.session_state.current_page = 'login'
    elif selected == "Cadastro":
        st.session_state.current_page = 'register'
    elif selected == "Painel":
        st.session_state.current_page = 'dashboard'
    elif selected == "Sair":
        logout()
        st.experimental_rerun()

# Page Rendering
def render_home():
    # Hero section with card layout
    st.markdown("""
    <div style="background: linear-gradient(to right, #1a2a3a, #293e54); padding: 30px; border-radius: 10px; text-align: center; margin-bottom: 30px">
        <h1 style="color: white; font-size: 36px">Copa Sub-13 de Futsal</h1>
        <h2 style="color: #4CAF50; font-size: 24px">Condomínio Terrara</h2>
        <p style="color: white; font-size: 18px; margin: 20px 0">A melhor competição de futsal para jovens talentos!</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%">
            <h3 style="color: #1a2a3a; text-align: center; margin-bottom: 20px">Cadastrar Time</h3>
            <p style="text-align: center; margin-bottom: 20px">Registre seu time para participar da competição!</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Cadastrar Time", key="home_register", use_container_width=True):
            st.session_state.current_page = 'register'
            st.experimental_rerun()
    
    with col2:
        st.markdown("""
        <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); height: 100%">
            <h3 style="color: #1a2a3a; text-align: center; margin-bottom: 20px">Seja um Torcedor</h3>
            <p style="text-align: center; margin-bottom: 20px">Registre-se como torcedor e faça apostas!</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Cadastro de Torcedor", key="home_fan_register", use_container_width=True):
            st.session_state.current_page = 'fanRegister'
            st.experimental_rerun()
    
    st.markdown("<h2 style='text-align: center; margin: 40px 0 20px 0; color: #1a2a3a'>Próximos Jogos</h2>", unsafe_allow_html=True)
    
    upcoming = get_upcoming_matches()
    if upcoming:
        # Display matches in a card grid
        cols = st.columns(min(3, len(upcoming)))
        for i, match in enumerate(upcoming[:3]):
            with cols[i % 3]:
                st.markdown(f"""
                <div style="background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px">
                    <div style="background-color: #4CAF50; color: white; padding: 8px; border-radius: 5px 5px 0 0; text-align: center; font-weight: bold">
                        Próximo Jogo
                    </div>
                    <div style="padding: 15px; text-align: center">
                        <div style="font-weight: bold; font-size: 18px">
                            {match['teamA']} <span style="color: #999; margin: 0 8px">VS</span> {match['teamB']}
                        </div>
                        <div style="color: #666; margin-top: 10px">
                            {match['date']}
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Não há jogos agendados no momento.")

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
            st.session_state.current_page = 'dashboard'
            st.experimental_rerun()
        else:
            st.error("Usuário ou senha incorretos.")
    
    st.write("Ainda não tem conta?")
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Cadastrar seu time"):
            st.session_state.current_page = 'register'
            st.experimental_rerun()
    
    with col2:
        if st.button("Seja um torcedor"):
            st.session_state.current_page = 'fanRegister'
            st.experimental_rerun()

def render_register():
    st.title("Cadastrar Time")
    
    team_name = st.text_input("Nome do Time")
    rep_name = st.text_input("Nome do Representante")
    rep_phone = st.text_input("Telefone do Representante")
    username = st.text_input("Nome de Usuário")
    password = st.text_input("Senha", type="password")
    
    if st.button("Cadastrar Time"):
        # Check if username already exists
        if any(u['username'] == username for u in st.session_state.db['users']):
            st.error("Este nome de usuário já está em uso.")
        elif not team_name or not rep_name or not rep_phone or not username or not password:
            st.error("Todos os campos são obrigatórios.")
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
            
            # Save database
            save_database()
            
            # Auto login
            st.session_state.logged_in = True
            st.session_state.current_user = new_user
            st.session_state.user_type = 'team'
            st.session_state.user_team = new_team
            st.session_state.current_page = 'dashboard'
            
            st.success("Time cadastrado com sucesso!")
            st.experimental_rerun()

def render_fan_register():
    st.title("Cadastro de Torcedor")
    
    name = st.text_input("Nome Completo")
    username = st.text_input("Nome de Usuário")
    password = st.text_input("Senha", type="password")
    
    teams = st.session_state.db['teams']
    team_options = [team['name'] for team in teams]
    team_ids = [team['id'] for team in teams]
    
    selected_team_idx = st.selectbox("Time Favorito", 
                                 options=range(len(team_options)),
                                 format_func=lambda x: team_options[x] if x < len(team_options) else "Selecione um time")
    
    if st.button("Cadastrar como Torcedor"):
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
                'favoriteTeamId': team_ids[selected_team_idx] if selected_team_idx < len(team_ids) else None,
                'points': 1000
            }
            
            st.session_state.db['users'].append(new_fan)
            
            # Save database
            save_database()
            
            # Auto login
            st.session_state.logged_in = True
            st.session_state.current_user = new_fan
            st.session_state.user_type = 'fan'
            st.session_state.current_page = 'dashboard'
            
            st.success("Cadastro realizado com sucesso! Você recebeu 1000 pontos para começar suas apostas.")
            st.experimental_rerun()

def render_dashboard():
    # Custom header for dashboard
    st.markdown(f"""
    <h1 style="text-align: center; color: #1a2a3a; margin-bottom: 30px">Painel de Controle</h1>
    <h3 style="text-align: center; color: #4CAF50; margin-bottom: 30px">Bem-vindo, {st.session_state.current_user['name']}</h3>
    """, unsafe_allow_html=True)
    
    if not st.session_state.logged_in:
        st.error("Você precisa estar logado para acessar esta página.")
        return
    
    # Create better dashboard tabs with icons
    tabs = []
    icons = []
    
    # All user types have overview
    tabs.append("Visão Geral")
    icons.append("speedometer2")
    
    # Team specific tabs
    if st.session_state.user_type == 'team':
        tabs.extend(["Meu Time", "Jogadores"])
        icons.extend(["shield", "people"])
    
    # Admin specific tabs
    if st.session_state.user_type == 'admin':
        tabs.extend(["Times", "Resultados", "Apostas"])
        icons.extend(["diagram-3", "list-check", "coin"])
    
    # Fan specific tabs
    if st.session_state.user_type == 'fan':
        tabs.append("Minhas Apostas")
        icons.append("cash-coin")
    
    # Create dashboard sidebar
    with st.sidebar:
        selected_tab = option_menu(
            menu_title="Dashboard",
            options=tabs,
            icons=icons,
            menu_icon="house",
            default_index=0,
            styles={
                "container": {"padding": "5px", "background-color": "#f9f9f9"},
                "icon": {"color": "#4CAF50", "font-size": "20px"}, 
                "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
                "nav-link-selected": {"background-color": "#4CAF50"},
            }
        )
    
    # Overview Tab
    if selected_tab == "Visão Geral":
        if st.session_state.user_type == 'team':
            team = st.session_state.user_team
            
            # Metric cards in 3 columns
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("""
                <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center">
                    <h4 style="color: #666; margin-bottom: 10px">Jogadores Registrados</h4>
                """, unsafe_allow_html=True)
                st.metric("", f"{len(get_team_players(team['id']))} / 15")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col2:
                next_match = next((m for m in get_upcoming_matches() 
                                if m['teamAId'] == team['id'] or m['teamBId'] == team['id']), None)
                
                st.markdown("""
                <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center">
                    <h4 style="color: #666; margin-bottom: 10px">Próximo Jogo</h4>
                """, unsafe_allow_html=True)
                
                if next_match:
                    st.metric("", f"{next_match['teamA']} vs {next_match['teamB']}", next_match['date'])
                else:
                    st.metric("", "Nenhum jogo agendado")
                st.markdown("</div>", unsafe_allow_html=True)
            
            with col3:
                st.markdown("""
                <div style="background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center">
                    <h4 style="color: #666; margin-bottom: 10px">Posição na Tabela</h4>
                """, unsafe_allow_html=True)
                st.metric("", f"{get_team_position(team['id'])}º")
                st.markdown("</div>", unsafe_allow_html=True)

def render_page():
    # Render the appropriate page based on current_page
    if st.session_state.current_page == 'home':
        render_home()
    elif st.session_state.current_page == 'classification':
        render_classification()
    elif st.session_state.current_page == 'topScorers':
        render_top_scorers()
    elif st.session_state.current_page == 'matches':
        render_matches()
    elif st.session_state.current_page == 'login':
        render_login()
    elif st.session_state.current_page == 'register':
        render_register()
    elif st.session_state.current_page == 'fanRegister':
        render_fan_register()
    elif st.session_state.current_page == 'dashboard':
        render_dashboard()

# Main app execution
def main():
    st.set_page_config(
        page_title="Matheuzinho League - Copa Sub-13 de Futsal",
        page_icon="⚽",
        layout="wide"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .block-container {
        padding-top: 1rem;
        padding-bottom: 1rem;
        max-width: 1200px !important;
    }
    h1, h2, h3 {
        color: #1a2a3a;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .stButton > button {
        background-color: #4CAF50;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #3e9142;
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
    }
    .stDataFrame {
        border-radius: 10px;
        overflow: hidden;
        border: none !important;
    }
    .dataframe {
        border-collapse: collapse;
        border: none !important;
    }
    .dataframe th {
        background-color: #1a2a3a;
        color: white;
        font-weight: bold;
        padding: 10px !important;
        border: none !important;
    }
    .dataframe td {
        padding: 10px !important;
        border-bottom: 1px solid #eee !important;
        border-right: none !important;
        border-left: none !important;
        border-top: none !important;
    }
    .dataframe tr:nth-child(even) {
        background-color: #f9f9f9;
    }
    .dataframe tr:hover {
        background-color: #f0f7f0;
    }
    </style>
    """, unsafe_allow_html=True)
    
    render_header()
    render_page()

if __name__ == "__main__":
    main()
