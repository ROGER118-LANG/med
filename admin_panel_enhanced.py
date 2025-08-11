import streamlit as st
import pandas as pd
import datetime
import requests
import json
from guimabet_melhorado import *

# Configure page
st.set_page_config(
    page_title="GuimaBet - Painel Admin",
    page_icon="⚽",
    layout="wide"
)

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'is_admin' not in st.session_state:
    st.session_state.is_admin = False

def admin_login_page():
    st.title("🔐 Login Administrativo")
    
    with st.form("admin_login"):
        username = st.text_input("Usuário")
        password = st.text_input("Senha", type="password")
        submit = st.form_submit_button("Entrar")
        
        if submit:
            user = login(username, password)
            if user and user[3]:  # is_admin
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.is_admin = True
                st.success("Login realizado com sucesso!")
                st.rerun()
            else:
                st.error("Credenciais inválidas ou usuário não é administrador")

def main_admin_panel():
    st.title("⚽ GuimaBet - Painel Administrativo")
    
    # Sidebar navigation
    st.sidebar.title("Menu Administrativo")
    
    menu_options = [
        "📊 Dashboard",
        "⚽ Gerenciar Partidas",
        "🎯 Gerenciar Odds",
        "📝 Templates de Apostas",
        "🎲 Apostas Personalizadas",
        "💡 Propostas de Usuários",
        "👥 Gerenciar Usuários",
        "🏆 Times e Jogadores",
        "📈 Relatórios"
    ]
    
    selected_page = st.sidebar.selectbox("Selecione uma página:", menu_options)
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.rerun()
    
    # Page routing
    if selected_page == "📊 Dashboard":
        dashboard_page()
    elif selected_page == "⚽ Gerenciar Partidas":
        manage_matches_page()
    elif selected_page == "🎯 Gerenciar Odds":
        manage_odds_page()
    elif selected_page == "📝 Templates de Apostas":
        manage_templates_page()
    elif selected_page == "🎲 Apostas Personalizadas":
        manage_custom_bets_page()
    elif selected_page == "💡 Propostas de Usuários":
        manage_proposals_page()
    elif selected_page == "👥 Gerenciar Usuários":
        manage_users_page()
    elif selected_page == "🏆 Times e Jogadores":
        manage_teams_players_page()
    elif selected_page == "📈 Relatórios":
        reports_page()

def dashboard_page():
    st.header("📊 Dashboard Administrativo")
    
    # Get statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        users = get_all_users()
        st.metric("Total de Usuários", len(users))
    
    with col2:
        matches = get_upcoming_matches() + get_match_history()
        st.metric("Total de Partidas", len(matches))
    
    with col3:
        # Count active bets
        conn = sqlite3.connect('guimabet.db')
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM bets WHERE status = 'pending'")
        active_bets = c.fetchone()[0]
        conn.close()
        st.metric("Apostas Ativas", active_bets)
    
    with col4:
        # Count custom bet proposals
        proposals = get_custom_bet_proposals('pending')
        st.metric("Propostas Pendentes", len(proposals))
    
    # Recent activity
    st.subheader("📈 Atividade Recente")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Últimas Apostas**")
        conn = sqlite3.connect('guimabet.db')
        recent_bets = pd.read_sql_query('''
        SELECT b.user_id, b.amount, b.bet_type, b.timestamp, m.team1_id, m.team2_id
        FROM bets b
        JOIN matches m ON b.match_id = m.id
        ORDER BY b.timestamp DESC
        LIMIT 10
        ''', conn)
        conn.close()
        
        if not recent_bets.empty:
            for _, bet in recent_bets.iterrows():
                team1 = get_team_name(bet['team1_id'])
                team2 = get_team_name(bet['team2_id'])
                st.write(f"• {bet['user_id']} apostou {bet['amount']} pts em {team1} vs {team2}")
        else:
            st.write("Nenhuma aposta recente")
    
    with col2:
        st.write("**Propostas Recentes**")
        recent_proposals = get_custom_bet_proposals('pending')[:5]
        
        if recent_proposals:
            for proposal in recent_proposals:
                team1 = get_team_name(proposal['team1_id'])
                team2 = get_team_name(proposal['team2_id'])
                st.write(f"• {proposal['username']}: {proposal['description'][:50]}...")
        else:
            st.write("Nenhuma proposta pendente")

def manage_odds_page():
    st.header("🎯 Gerenciar Odds")
    
    # Select match
    matches = get_upcoming_matches()
    if not matches:
        st.warning("Nenhuma partida disponível para gerenciar odds")
        return
    
    match_options = {}
    for match in matches:
        team1 = get_team_name(match['team1_id'])
        team2 = get_team_name(match['team2_id'])
        match_key = f"{team1} vs {team2} - {match['date']} {match['time']}"
        match_options[match_key] = match['id']
    
    selected_match_key = st.selectbox("Selecione uma partida:", list(match_options.keys()))
    selected_match_id = match_options[selected_match_key]
    
    # Get current odds for the match
    match_odds = get_match_odds(selected_match_id)
    
    if not match_odds:
        st.warning("Nenhuma odd encontrada para esta partida")
        if st.button("🎲 Gerar Odds Padrão"):
            create_match_odds(selected_match_id, st.session_state.username)
            st.success("Odds geradas com sucesso!")
            st.rerun()
        return
    
    # Group odds by category
    odds_by_category = {}
    for odd in match_odds:
        category = odd['category_name']
        if category not in odds_by_category:
            odds_by_category[category] = []
        odds_by_category[category].append(odd)
    
    # Display and edit odds by category
    for category, odds_list in odds_by_category.items():
        st.subheader(f"📂 {category}")
        
        cols = st.columns(min(3, len(odds_list)))
        
        for i, odd in enumerate(odds_list):
            with cols[i % 3]:
                display_name = odd['template_name']
                if odd['player_name']:
                    display_name += f" ({odd['player_name']})"
                
                st.write(f"**{display_name}**")
                st.write(f"_{odd['description']}_")
                
                # Edit odds value
                new_odds = st.number_input(
                    f"Odds atual: {odd['odds_value']}", 
                    min_value=1.01, 
                    value=float(odd['odds_value']), 
                    step=0.01,
                    key=f"odds_{odd['id']}"
                )
                
                reason = st.text_input(
                    "Motivo da alteração:", 
                    key=f"reason_{odd['id']}"
                )
                
                if st.button(f"💾 Atualizar", key=f"update_{odd['id']}"):
                    if new_odds != odd['odds_value']:
                        update_match_odds(odd['id'], new_odds, st.session_state.username, reason)
                        st.success("Odds atualizada!")
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração detectada")
                
                st.divider()

def manage_templates_page():
    st.header("📝 Templates de Apostas")
    
    tab1, tab2 = st.tabs(["📋 Ver Templates", "➕ Criar Template"])
    
    with tab1:
        # Display existing templates
        categories = get_odds_categories()
        
        for category in categories:
            st.subheader(f"📂 {category['name']}")
            st.write(category['description'])
            
            templates = get_odds_templates(category['id'])
            
            if templates:
                df = pd.DataFrame(templates)
                df = df[['name', 'description', 'bet_type', 'default_odds', 'requires_player']]
                df.columns = ['Nome', 'Descrição', 'Tipo', 'Odds Padrão', 'Requer Jogador']
                df['Requer Jogador'] = df['Requer Jogador'].map({1: 'Sim', 0: 'Não'})
                st.dataframe(df, use_container_width=True)
            else:
                st.write("Nenhum template nesta categoria")
            
            st.divider()
    
    with tab2:
        # Create new template
        st.subheader("➕ Criar Novo Template")
        
        with st.form("create_template"):
            categories = get_odds_categories()
            category_options = {cat['name']: cat['id'] for cat in categories}
            
            selected_category = st.selectbox("Categoria:", list(category_options.keys()))
            name = st.text_input("Nome do Template:")
            description = st.text_area("Descrição:")
            bet_type = st.text_input("Tipo de Aposta (identificador único):")
            default_odds = st.number_input("Odds Padrão:", min_value=1.01, value=2.0, step=0.01)
            requires_player = st.checkbox("Requer Jogador Específico")
            
            if st.form_submit_button("🎯 Criar Template"):
                if name and description and bet_type:
                    success, message = add_custom_odds_template(
                        category_options[selected_category],
                        name,
                        description,
                        bet_type,
                        default_odds,
                        requires_player
                    )
                    
                    if success:
                        st.success(message)
                        st.rerun()
                    else:
                        st.error(message)
                else:
                    st.error("Todos os campos são obrigatórios")

def manage_custom_bets_page():
    st.header("🎲 Apostas Personalizadas")
    
    tab1, tab2 = st.tabs(["📋 Ver Apostas", "➕ Criar Aposta"])
    
    with tab1:
        # Display existing custom bets
        matches = get_upcoming_matches()
        
        if matches:
            match_options = {}
            for match in matches:
                team1 = get_team_name(match['team1_id'])
                team2 = get_team_name(match['team2_id'])
                match_key = f"{team1} vs {team2} - {match['date']} {match['time']}"
                match_options[match_key] = match['id']
            
            selected_match_key = st.selectbox("Filtrar por partida:", ["Todas"] + list(match_options.keys()))
            
            if selected_match_key == "Todas":
                custom_bets = get_custom_bets()
            else:
                custom_bets = get_custom_bets(match_options[selected_match_key])
            
            if custom_bets:
                for bet in custom_bets:
                    with st.expander(f"🎯 {bet['description']} (Odds: {bet['odds']})"):
                        team1 = get_team_name(bet.get('team1_id', 0))
                        team2 = get_team_name(bet.get('team2_id', 0))
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Partida:** {team1} vs {team2}")
                            st.write(f"**Odds:** {bet['odds']}")
                            st.write(f"**Status:** {bet['status']}")
                            if bet['player_id']:
                                player_name = get_player_name(bet['player_id'])
                                st.write(f"**Jogador:** {player_name}")
                        
                        with col2:
                            if bet['status'] == 'pending':
                                result = st.selectbox(
                                    "Resultado:", 
                                    ["", "yes", "no"], 
                                    key=f"result_{bet['id']}"
                                )
                                
                                if st.button(f"✅ Finalizar Aposta", key=f"finish_{bet['id']}"):
                                    if result:
                                        update_custom_bet_result(bet['id'], result)
                                        st.success("Aposta finalizada!")
                                        st.rerun()
                                    else:
                                        st.error("Selecione um resultado")
            else:
                st.info("Nenhuma aposta personalizada encontrada")
    
    with tab2:
        # Create new custom bet
        st.subheader("➕ Criar Nova Aposta Personalizada")
        
        matches = get_upcoming_matches()
        
        if not matches:
            st.warning("Nenhuma partida disponível")
            return
        
        with st.form("create_custom_bet"):
            match_options = {}
            for match in matches:
                team1 = get_team_name(match['team1_id'])
                team2 = get_team_name(match['team2_id'])
                match_key = f"{team1} vs {team2} - {match['date']} {match['time']}"
                match_options[match_key] = match['id']
            
            selected_match_key = st.selectbox("Partida:", list(match_options.keys()))
            selected_match_id = match_options[selected_match_key]
            
            description = st.text_area("Descrição da Aposta:")
            odds = st.number_input("Odds:", min_value=1.01, value=2.0, step=0.01)
            
            # Optional player selection
            use_player = st.checkbox("Aposta específica de jogador")
            player_id = None
            
            if use_player:
                players = get_match_players(selected_match_id)
                if players:
                    player_options = {player['name']: player['id'] for player in players}
                    selected_player = st.selectbox("Jogador:", list(player_options.keys()))
                    player_id = player_options[selected_player]
                else:
                    st.warning("Nenhum jogador encontrado para esta partida")
            
            if st.form_submit_button("🎲 Criar Aposta"):
                if description:
                    success = add_custom_bet(selected_match_id, description, odds, player_id)
                    if success:
                        st.success("Aposta personalizada criada!")
                        st.rerun()
                    else:
                        st.error("Erro ao criar aposta")
                else:
                    st.error("Descrição é obrigatória")

def manage_proposals_page():
    st.header("💡 Propostas de Usuários")
    
    proposals = get_custom_bet_proposals('pending')
    
    if not proposals:
        st.info("Nenhuma proposta pendente")
        return
    
    for proposal in proposals:
        with st.expander(f"💡 {proposal['description'][:50]}... (por {proposal['username']})"):
            team1 = get_team_name(proposal['team1_id'])
            team2 = get_team_name(proposal['team2_id'])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Usuário:** {proposal['username']}")
                st.write(f"**Partida:** {team1} vs {team2}")
                st.write(f"**Data:** {proposal['date']} {proposal['time']}")
                st.write(f"**Descrição:** {proposal['description']}")
                st.write(f"**Odds Propostas:** {proposal['proposed_odds']}")
                st.write(f"**Criado em:** {proposal['created_at']}")
            
            with col2:
                st.subheader("🔍 Revisar Proposta")
                
                action = st.selectbox(
                    "Ação:", 
                    ["", "approve", "reject"], 
                    key=f"action_{proposal['id']}"
                )
                
                response = st.text_area(
                    "Resposta para o usuário:", 
                    key=f"response_{proposal['id']}"
                )
                
                if action == "approve":
                    final_odds = st.number_input(
                        "Odds Final:", 
                        min_value=1.01, 
                        value=float(proposal['proposed_odds']), 
                        step=0.01,
                        key=f"final_odds_{proposal['id']}"
                    )
                else:
                    final_odds = None
                
                if st.button(f"✅ Processar", key=f"process_{proposal['id']}"):
                    if action:
                        review_custom_bet_proposal(
                            proposal['id'], 
                            st.session_state.username, 
                            action, 
                            response, 
                            final_odds
                        )
                        st.success(f"Proposta {'aprovada' if action == 'approve' else 'rejeitada'}!")
                        st.rerun()
                    else:
                        st.error("Selecione uma ação")

def manage_matches_page():
    st.header("⚽ Gerenciar Partidas")
    
    tab1, tab2, tab3 = st.tabs(["📋 Partidas Ativas", "📈 Resultados", "➕ Nova Partida"])
    
    with tab1:
        matches = get_upcoming_matches()
        
        if matches:
            for match in matches:
                team1 = get_team_name(match['team1_id'])
                team2 = get_team_name(match['team2_id'])
                
                with st.expander(f"⚽ {team1} vs {team2} - {match['date']} {match['time']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Status:** {match['status']}")
                        if match['status'] == 'live':
                            st.write(f"**Placar:** {match['team1_score'] or 0} - {match['team2_score'] or 0}")
                    
                    with col2:
                        if match['status'] == 'upcoming':
                            if st.button(f"🔴 Iniciar Partida", key=f"start_{match['id']}"):
                                set_match_live(match['id'])
                                st.success("Partida iniciada!")
                                st.rerun()
                        
                        elif match['status'] == 'live':
                            st.subheader("📊 Finalizar Partida")
                            
                            col_a, col_b = st.columns(2)
                            with col_a:
                                team1_score = st.number_input(f"Gols {team1}:", min_value=0, key=f"t1_{match['id']}")
                            with col_b:
                                team2_score = st.number_input(f"Gols {team2}:", min_value=0, key=f"t2_{match['id']}")
                            
                            if st.button(f"✅ Finalizar", key=f"finish_{match['id']}"):
                                update_match_result(match['id'], team1_score, team2_score)
                                st.success("Partida finalizada!")
                                st.rerun()
        else:
            st.info("Nenhuma partida ativa")
    
    with tab2:
        history = get_match_history()
        
        if history:
            for match in history[:10]:  # Show last 10 matches
                team1 = get_team_name(match['team1_id'])
                team2 = get_team_name(match['team2_id'])
                
                st.write(f"⚽ **{team1} {match['team1_score']} - {match['team2_score']} {team2}** ({match['date']})")
        else:
            st.info("Nenhuma partida finalizada")
    
    with tab3:
        st.subheader("➕ Criar Nova Partida")
        
        teams = get_all_teams()
        team_options = {team['name']: team['id'] for team in teams}
        
        with st.form("create_match"):
            col1, col2 = st.columns(2)
            
            with col1:
                team1 = st.selectbox("Time 1:", list(team_options.keys()))
            
            with col2:
                team2_options = [name for name in team_options.keys() if name != team1]
                team2 = st.selectbox("Time 2:", team2_options)
            
            col3, col4 = st.columns(2)
            
            with col3:
                date = st.date_input("Data:", datetime.date.today())
            
            with col4:
                time = st.time_input("Horário:", datetime.time(20, 0))
            
            if st.form_submit_button("⚽ Criar Partida"):
                if team1 != team2:
                    success = add_match(
                        team_options[team1], 
                        team_options[team2], 
                        date.strftime("%Y-%m-%d"), 
                        time.strftime("%H:%M")
                    )
                    
                    if success:
                        st.success("Partida criada com sucesso!")
                        st.rerun()
                    else:
                        st.error("Erro ao criar partida")
                else:
                    st.error("Selecione times diferentes")

def manage_users_page():
    st.header("👥 Gerenciar Usuários")
    
    users = get_all_users()
    
    if users:
        df = pd.DataFrame(users)
        df['is_admin'] = df['is_admin'].map({1: 'Sim', 0: 'Não'})
        df.columns = ['Usuário', 'Pontos', 'Admin']
        
        st.dataframe(df, use_container_width=True)
        
        # User management
        st.subheader("✏️ Editar Usuário")
        
        user_options = {user['username']: user for user in users}
        selected_user = st.selectbox("Selecionar usuário:", list(user_options.keys()))
        
        if selected_user:
            user_data = user_options[selected_user]
            
            col1, col2 = st.columns(2)
            
            with col1:
                new_points = st.number_input("Pontos:", value=user_data['points'], min_value=0)
            
            with col2:
                new_admin = st.checkbox("É Admin", value=bool(user_data['is_admin']))
            
            if st.button("💾 Atualizar Usuário"):
                success, message = update_user(
                    selected_user, 
                    new_points=new_points, 
                    is_admin=new_admin
                )
                
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
    else:
        st.info("Nenhum usuário encontrado")

def manage_teams_players_page():
    st.header("🏆 Times e Jogadores")
    
    tab1, tab2 = st.tabs(["🏆 Times", "👤 Jogadores"])
    
    with tab1:
        teams = get_all_teams()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📋 Times Existentes")
            for team in teams:
                st.write(f"• {team['name']}")
        
        with col2:
            st.subheader("➕ Adicionar Time")
            
            with st.form("add_team"):
                team_name = st.text_input("Nome do Time:")
                
                if st.form_submit_button("🏆 Adicionar"):
                    if team_name:
                        success = add_team(team_name)
                        if success:
                            st.success("Time adicionado!")
                            st.rerun()
                        else:
                            st.error("Erro ao adicionar time")
                    else:
                        st.error("Nome é obrigatório")
    
    with tab2:
        players = get_all_players()
        teams = get_all_teams()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📋 Jogadores Existentes")
            
            if players:
                for player in players:
                    team_name = get_team_name(player['team_id'])
                    st.write(f"• {player['name']} ({team_name})")
            else:
                st.write("Nenhum jogador cadastrado")
        
        with col2:
            st.subheader("➕ Adicionar Jogador")
            
            if teams:
                with st.form("add_player"):
                    player_name = st.text_input("Nome do Jogador:")
                    
                    team_options = {team['name']: team['id'] for team in teams}
                    selected_team = st.selectbox("Time:", list(team_options.keys()))
                    
                    if st.form_submit_button("👤 Adicionar"):
                        if player_name:
                            success = add_player(player_name, team_options[selected_team])
                            if success:
                                st.success("Jogador adicionado!")
                                st.rerun()
                            else:
                                st.error("Erro ao adicionar jogador")
                        else:
                            st.error("Nome é obrigatório")
            else:
                st.warning("Adicione times primeiro")

def reports_page():
    st.header("📈 Relatórios")
    
    # Betting statistics
    conn = sqlite3.connect('guimabet.db')
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Estatísticas de Apostas")
        
        # Total bets by status
        bet_stats = pd.read_sql_query('''
        SELECT status, COUNT(*) as count, SUM(amount) as total_amount
        FROM bets
        GROUP BY status
        ''', conn)
        
        if not bet_stats.empty:
            st.dataframe(bet_stats)
        
        # Top bettors
        st.subheader("🏆 Maiores Apostadores")
        top_bettors = pd.read_sql_query('''
        SELECT user_id, COUNT(*) as total_bets, SUM(amount) as total_amount
        FROM bets
        GROUP BY user_id
        ORDER BY total_amount DESC
        LIMIT 10
        ''', conn)
        
        if not top_bettors.empty:
            st.dataframe(top_bettors)
    
    with col2:
        st.subheader("💰 Análise Financeira")
        
        # Daily betting volume
        daily_volume = pd.read_sql_query('''
        SELECT DATE(timestamp) as date, COUNT(*) as bets, SUM(amount) as volume
        FROM bets
        WHERE timestamp >= date('now', '-30 days')
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
        ''', conn)
        
        if not daily_volume.empty:
            st.line_chart(daily_volume.set_index('date')['volume'])
        
        # Win/Loss ratio
        win_loss = pd.read_sql_query('''
        SELECT 
            SUM(CASE WHEN status = 'won' THEN amount ELSE 0 END) as total_winnings,
            SUM(CASE WHEN status = 'lost' THEN amount ELSE 0 END) as total_losses,
            COUNT(CASE WHEN status = 'won' THEN 1 END) as wins,
            COUNT(CASE WHEN status = 'lost' THEN 1 END) as losses
        FROM bets
        WHERE status IN ('won', 'lost')
        ''', conn)
        
        if not win_loss.empty and win_loss.iloc[0]['wins'] > 0:
            st.metric("Taxa de Vitória", f"{win_loss.iloc[0]['wins'] / (win_loss.iloc[0]['wins'] + win_loss.iloc[0]['losses']) * 100:.1f}%")
    
    conn.close()

# Main app logic
def main():
    init_db()  # Initialize database
    
    if not st.session_state.logged_in:
        admin_login_page()
    else:
        main_admin_panel()

if __name__ == "__main__":
    main()

