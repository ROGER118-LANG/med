import streamlit as st
import pandas as pd
import datetime
import requests
import json
import sqlite3

# Importar funções de guimabet_melhorado
from guimabet_melhorado import (
    login, get_all_users, get_upcoming_matches, get_match_history, 
    get_custom_bet_proposals, get_team_name, get_match_odds, 
    create_match_odds, update_match_odds, get_odds_categories, 
    get_odds_templates, add_custom_odds_template, get_custom_bets, 
    update_custom_bet_result, add_custom_bet, review_custom_bet_proposal, 
    set_match_live, update_match_result, add_match, update_user, 
    get_all_teams, add_team, get_all_players, add_player, get_player_name, 
    get_match_players, add_custom_bet_proposal
)

def admin_login_page():
    st.title("🔐 Login Administrativo")
    
    with st.form("admin_login", key="admin_login_form"):
        username = st.text_input("Usuário", key="admin_login_username")
        password = st.text_input("Senha", type="password", key="admin_login_password")
        submit = st.form_submit_button("Entrar", key="admin_login_submit")
        
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

def main_admin_panel_content():
    """Conteúdo principal do painel administrativo, a ser chamado por uma função wrapper."""
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
    
    selected_page = st.sidebar.selectbox("Selecione uma página:", menu_options, key="admin_main_navigation")
    
    if st.sidebar.button("🚪 Logout", key="admin_logout_button"):
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
        st.metric("Total de Partidas", len(matches)")
    
    with col3:
        # Count active bets
        conn = sqlite3.connect("guimabet.db")
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM bets WHERE status = \'pending\'")
        active_bets = c.fetchone()[0]
        conn.close()
        st.metric("Apostas Ativas", active_bets,)
    
    with col4:
        # Count custom bet proposals
        proposals = get_custom_bet_proposals("pending")
        st.metric("Propostas Pendentes", len(proposals), key="dashboard_pending_proposals")
    
    # Recent activity
    st.subheader("📈 Atividade Recente")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Últimas Apostas**")
        conn = sqlite3.connect("guimabet.db")
        recent_bets = pd.read_sql_query("""
        SELECT b.user_id, b.amount, b.bet_type, b.timestamp, m.team1_id, m.team2_id
        FROM bets b
        JOIN matches m ON b.match_id = m.id
        ORDER BY b.timestamp DESC
        LIMIT 10
        """, conn)
        conn.close()
        
        if not recent_bets.empty:
            for idx, bet in recent_bets.iterrows():
                team1 = get_team_name(bet["team1_id"])
                team2 = get_team_name(bet["team2_id"])
                st.write(f"• {bet['user_id']} apostou {bet['amount']} pts em {team1} vs {team2}", key=f"recent_bet_{idx}")
        else:
            st.write("Nenhuma aposta recente", key="no_recent_bets")
    
    with col2:
        st.write("**Propostas Recentes**")
        recent_proposals = get_custom_bet_proposals("pending")[:5]
        
        if recent_proposals:
            for idx, proposal in enumerate(recent_proposals):
                team1 = get_team_name(proposal["match_id"])
                team2 = get_team_name(proposal["match_id"])
                st.write(f"• {proposal['username']}: {proposal['description'][:50]}...", key=f"recent_proposal_{idx}")
        else:
            st.write("Nenhuma proposta pendente", key="no_recent_proposals")

def manage_odds_page():
    st.header("🎯 Gerenciar Odds")
    
    # Select match
    matches = get_upcoming_matches()
    if not matches:
        st.warning("Nenhuma partida disponível para gerenciar odds")
        return
    
    match_options = {}
    for match in matches:
        team1 = get_team_name(match["team1_id"])
        team2 = get_team_name(match["team2_id"])
        match_key = f"{team1} vs {team2} - {match["date"]} {match["time"]}"
        match_options[match_key] = match["id"]
    
    selected_match_key = st.selectbox("Selecione uma partida:", list(match_options.keys()), key="manage_odds_match_select")
    selected_match_id = match_options[selected_match_key]
    
    # Get current odds for the match
    match_odds = get_match_odds(selected_match_id)
    
    if not match_odds:
        st.warning("Nenhuma odd encontrada para esta partida")
        if st.button("🎲 Gerar Odds Padrão", key="generate_default_odds_button"):
            create_match_odds(selected_match_id, st.session_state.username)
            st.success("Odds geradas com sucesso!")
            st.rerun()
        return
    
    # Group odds by category
    odds_by_category = {}
    for odd in match_odds:
        category = odd["category_name"]
        if category not in odds_by_category:
            odds_by_category[category] = []
        odds_by_category[category].append(odd)
    
    # Display and edit odds by category
    for category_idx, (category, odds_list) in enumerate(odds_by_category.items()):
        st.subheader(f"📂 {category}", key=f"odds_category_subheader_{category_idx}")
        
        cols = st.columns(min(3, len(odds_list)))
        
        for i, odd in enumerate(odds_list):
            with cols[i % 3]:
                display_name = odd["template_name"]
                if odd["player_name"]:
                    display_name += f" ({odd['player_name']})"
                
                st.write(f"**{display_name}**", key=f"odd_display_name_{odd['id']}")
                st.write(f"_{odd['description']}_", key=f"odd_description_{odd['id']}")
                
                # Edit odds value
                new_odds = st.number_input(
                    f"Odds atual: {odd['odds_value']}", 
                    min_value=1.01, 
                    value=float(odd['odds_value']),
                    step=0.01,
                    key=f"odds_input_{odd['id']}"
                )
                
                reason = st.text_input(
                    "Motivo da alteração:", 
                    key=f"reason_input_{odd['id']}"
                )
                
                if st.button(f"💾 Atualizar", key=f"update_odd_button_{odd['id']}"):
                    if new_odds != odd['odds_value']:
                        update_match_odds(odd['id'], new_odds, st.session_state.username, reason)
                        st.success("Odds atualizada!")
                        st.rerun()
                    else:
                        st.info("Nenhuma alteração detectada")
                
                st.divider()

def manage_templates_page():
    st.header("📝 Templates de Apostas")
    
    tab1, tab2 = st.tabs(["📋 Ver Templates", "➕ Criar Template"], key="manage_templates_tabs")
    
    with tab1:
        # Display existing templates
        categories = get_odds_categories()
        
        for category_idx, category in enumerate(categories):
            st.subheader(f"📂 {category['name']}", key=f"template_category_subheader_{category_idx}")
            st.write(category['description'], key=f"template_category_description_{category_idx}")
            
            templates = get_odds_templates(category["id"])
            
            if templates:
                df = pd.DataFrame(templates)
                df = df[["name", "description", "bet_type", "default_odds", "requires_player"]]
                df.columns = ["Nome", "Descrição", "Tipo", "Odds Padrão", "Requer Jogador"]
                df["Requer Jogador"] = df["Requer Jogador"].map({1: "Sim", 0: "Não"})
                st.dataframe(df, use_container_width=True, key=f"templates_dataframe_{category_idx}")
            else:
                st.write("Nenhum template nesta categoria", key=f"no_templates_in_category_{category_idx}")
            
            st.divider()
    
    with tab2:
        # Create new template
        st.subheader("➕ Criar Novo Template", key="create_template_subheader")
        
        with st.form("create_template_form", key="create_template_form"):
            categories = get_odds_categories()
            category_options = {cat["name"]: cat["id"] for cat in categories}
            
            selected_category = st.selectbox("Categoria:", list(category_options.keys()), key="new_template_category_select")
            name = st.text_input("Nome do Template:", key="new_template_name_input")
            description = st.text_area("Descrição:", key="new_template_description_input")
            bet_type = st.text_input("Tipo de Aposta (identificador único):", key="new_template_bet_type_input")
            default_odds = st.number_input("Odds Padrão:", min_value=1.01, value=2.0, step=0.01, key="new_template_default_odds_input")
            requires_player = st.checkbox("Requer Jogador Específico", key="new_template_requires_player_checkbox")
            
            if st.form_submit_button("🎯 Criar Template", key="create_template_submit_button"):
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
    
    tab1, tab2 = st.tabs(["📋 Ver Apostas", "➕ Criar Aposta"], key="manage_custom_bets_tabs")
    
    with tab1:
        # Display existing custom bets
        matches = get_upcoming_matches()
        
        if matches:
            match_options = {}
            for match in matches:
                team1 = get_team_name(match["team1_id"])
                team2 = get_team_name(match["team2_id"])
                match_key = f"{team1} vs {team2} - {match["date"]} {match["time"]}"
                match_options[match_key] = match["id"]
            
            selected_match_key = st.selectbox("Filtrar por partida:", ["Todas"] + list(match_options.keys()), key="filter_custom_bets_match_select")
            
            if selected_match_key == "Todas":
                custom_bets = get_custom_bets()
            else:
                custom_bets = get_custom_bets(match_options[selected_match_key])
            
            if custom_bets:
                for bet_idx, bet in enumerate(custom_bets):
                    with st.expander(f"🎯 {bet['description']} (Odds: {bet['odds']})", key=f"custom_bet_expander_{bet_idx}_{bet['id']}"):
                        # Get match info for this bet
                        conn = sqlite3.connect("guimabet.db")
                        c = conn.cursor()
                        c.execute("SELECT team1_id, team2_id FROM matches WHERE id = ?", (bet["match_id"],))
                        match_info = c.fetchone()
                        conn.close()
                        
                        if match_info:
                            team1 = get_team_name(match_info[0])
                            team2 = get_team_name(match_info[1])
                        else:
                            team1 = team2 = "Desconhecido"
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Partida:** {team1} vs {team2}", key=f"custom_bet_match_info_{bet['id']}")
                            st.write(f"**Odds:** {bet['odds']}", key=f"custom_bet_odds_info_{bet['id']}")
                            st.write(f"**Status:** {bet['status']}", key=f"custom_bet_status_info_{bet['id']}")
                            if bet["player_id"]:
                                player_name = get_player_name(bet["player_id"])
                                st.write(f"**Jogador:** {player_name}", key=f"custom_bet_player_info_{bet['id']}")
                        
                        with col2:
                            if bet["status"] == "pending":
                                result = st.selectbox(
                                    "Resultado:", 
                                    ["", "yes", "no"], 
                                    key=f"custom_bet_result_select_{bet['id']}"
                                )
                                
                                if st.button(f"✅ Finalizar Aposta", key=f"finish_custom_bet_button_{bet['id']}"):
                                    if result:
                                        update_custom_bet_result(bet["id"], result)
                                        st.success("Aposta finalizada!")
                                        st.rerun()
                                    else:
                                        st.error("Selecione um resultado")
            else:
                st.info("Nenhuma aposta personalizada encontrada", key="no_custom_bets_found")
    
    with tab2:
        # Create new custom bet
        st.subheader("➕ Criar Nova Aposta Personalizada", key="create_new_custom_bet_subheader")
        
        matches = get_upcoming_matches()
        
        if not matches:
            st.warning("Nenhuma partida disponível", key="no_matches_for_custom_bet")
            return
        
        with st.form("create_custom_bet_form", key="create_custom_bet_form"):
            match_options = {}
            for match in matches:
                team1 = get_team_name(match["team1_id"])
                team2 = get_team_name(match["team2_id"])
                match_key = f"{team1} vs {team2} - {match["date"]} {match["time"]}"
                match_options[match_key] = match["id"]
            
            selected_match_key = st.selectbox("Partida:", list(match_options.keys()), key="new_custom_bet_match_select")
            selected_match_id = match_options[selected_match_key]
            
            description = st.text_area("Descrição da Aposta:", key="new_custom_bet_description_input")
            odds = st.number_input("Odds:", min_value=1.01, value=2.0, step=0.01, key="new_custom_bet_odds_input")
            
            # Optional player selection
            use_player = st.checkbox("Aposta específica de jogador", key="new_custom_bet_use_player_checkbox")
            player_id = None
            
            if use_player:
                players = get_match_players(selected_match_id)
                if players:
                    player_options = {player["name"]: player["id"] for player in players}
                    selected_player = st.selectbox("Jogador:", list(player_options.keys()), key="new_custom_bet_player_select")
                    player_id = player_options[selected_player]
                else:
                    st.warning("Nenhum jogador encontrado para esta partida", key="no_players_for_custom_bet")
            
            if st.form_submit_button("🎲 Criar Aposta", key="create_custom_bet_submit_button"):
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
    
    proposals = get_custom_bet_proposals("pending")
    
    if not proposals:
        st.info("Nenhuma proposta pendente", key="no_pending_proposals")
        return
    
    for proposal_idx, proposal in enumerate(proposals):
        with st.expander(f"💡 {proposal['description'][:50]}... (por {proposal['username']})", key=f"proposal_expander_{proposal_idx}_{proposal['id']}"):
            team1 = get_team_name(proposal["match_id"])
            team2 = get_team_name(proposal["match_id"])
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Usuário:** {proposal['username']}", key=f"proposal_username_{proposal['id']}")
                st.write(f"**Partida:** {team1} vs {team2}", key=f"proposal_match_{proposal['id']}")
                st.write(f"**Data:** {proposal['created_at']}", key=f"proposal_created_at_display_{proposal['id']}") # Changed to created_at
                st.write(f"**Descrição:** {proposal['description']}", key=f"proposal_description_{proposal['id']}")
                st.write(f"**Odds Propostas:** {proposal['proposed_odds']}", key=f"proposal_odds_{proposal['id']}")
                
            
            with col2:
                st.subheader("🔍 Revisar Proposta", key=f"review_proposal_subheader_{proposal['id']}")
                
                with st.form(key=f"process_proposal_form_{proposal['id']}"):
                    action = st.selectbox(
                        "Ação:", 
                        ["", "approve", "reject"], 
                        key=f"proposal_action_select_{proposal['id']}"
                    )
                    
                    response = st.text_area(
                        "Resposta para o usuário:", 
                        key=f"proposal_response_text_area_{proposal['id']}"
                    )
                    
                    final_odds = None
                    if action == "approve":
                        final_odds = st.number_input(
                            "Odds Final:", 
                            min_value=1.01, 
                            value=float(proposal['proposed_odds']),
                            step=0.01,
                            key=f"proposal_final_odds_input_{proposal['id']}"
                        )
                    
                    if st.form_submit_button(f"✅ Processar Proposta", key=f"process_proposal_button_{proposal['id']}"):
                        if action:
                            review_custom_bet_proposal(
                                proposal["id"], 
                                st.session_state.username, 
                                action, 
                                response, 
                                final_odds
                            )
                            st.success(f"Proposta {"aprovada" if action == "approve" else "rejeitada"}!")
                            st.rerun()
                        else:
                            st.error("Selecione uma ação")

def manage_matches_page():
    st.header("⚽ Gerenciar Partidas")
    
    tab1, tab2, tab3 = st.tabs(["📋 Partidas Ativas", "📈 Resultados", "➕ Nova Partida"], key="manage_matches_tabs")
    
    with tab1:
        matches = get_upcoming_matches()
        
        if matches:
            for match_idx, match in enumerate(matches):
                team1 = get_team_name(match["team1_id"])
                team2 = get_team_name(match["team2_id"])
                
                with st.expander(f"⚽ {team1} vs {team2} - {match['date']} {match['time']}", key=f"manage_match_expander_{match_idx}_{match['id']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Status:** {match['status']}", key=f"manage_match_status_{match['id']}")
                        if match["status"] == "live":
                            st.write(f"**Placar:** {match['team1_score'] or 0} - {match['team2_score'] or 0}", key=f"manage_match_score_{match['id']}")
                    
                    with col2:
                        if match["status"] == "upcoming":
                            if st.button(f"🔴 Iniciar Partida", key=f"start_match_button_{match['id']}"):
                                set_match_live(match["id"])
                                st.success("Partida iniciada!")
                                st.rerun()
                        
                        elif match["status"] == "live":
                            st.subheader("📊 Finalizar Partida", key=f"finalize_match_subheader_{match['id']}")
                            
                            with st.form(key=f"finalize_match_form_{match['id']}"):
                                col_a, col_b = st.columns(2)
                                with col_a:
                                    team1_score = st.number_input(f"Gols {team1}:", min_value=0, key=f"t1_score_input_{match['id']}")
                                with col_b:
                                    team2_score = st.number_input(f"Gols {team2}:", min_value=0, key=f"t2_score_input_{match['id']}")
                                
                                if st.form_submit_button(f"✅ Finalizar", key=f"finish_match_button_{match['id']}"):
                                    update_match_result(match["id"], team1_score, team2_score)
                                    st.success("Partida finalizada!")
                                    st.rerun()
        else:
            st.info("Nenhuma partida ativa", key="no_active_matches")
    
    with tab2:
        history = get_match_history()
        
        if history:
            for history_idx, match in enumerate(history[:10]):  # Show last 10 matches
                team1 = get_team_name(match["team1_id"])
                team2 = get_team_name(match["team2_id"])
                
                st.write(f"⚽ **{team1} {match['team1_score']} - {match['team2_score']} {team2}** ({match['date']})", key=f"match_history_entry_{history_idx}_{match['id']}")
        else:
            st.info("Nenhuma partida finalizada", key="no_finished_matches")
    
    with tab3:
        st.subheader("➕ Criar Nova Partida", key="create_new_match_subheader")
        
        teams = get_all_teams()
        team_options = {team["name"]: team["id"] for team in teams}
        
        with st.form("create_match_form", key="create_match_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                team1 = st.selectbox("Time 1:", list(team_options.keys()), key="new_match_team1_select")
            
            with col2:
                team2_options = [name for name in team_options.keys() if name != team1]
                team2 = st.selectbox("Time 2:", team2_options, key="new_match_team2_select")
            
            col3, col4 = st.columns(2)
            
            with col3:
                date = st.date_input("Data:", datetime.date.today(), key="new_match_date_input")
            
            with col4:
                time = st.time_input("Horário:", datetime.time(20, 0), key="new_match_time_input")
            
            if st.form_submit_button("⚽ Criar Partida", key="create_match_submit_button"):
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
        df["is_admin"] = df["is_admin"].map({1: "Sim", 0: "Não"})
        df.columns = ["Usuário", "Pontos", "Admin"]
        
        st.dataframe(df, use_container_width=True, key="users_dataframe")
        
        # User management
        st.subheader("✏️ Editar Usuário", key="edit_user_subheader")
        
        with st.form("edit_user_form", key="edit_user_form"):
            user_options = {user["username"]: user for user in users}
            selected_user = st.selectbox("Selecionar usuário:", list(user_options.keys()), key="select_user_to_edit")
            
            if selected_user:
                user_data = user_options[selected_user]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    new_points = st.number_input("Pontos:", value=user_data["points"], min_value=0, key="edit_user_points_input")
                
                with col2:
                    new_admin = st.checkbox("É Admin", value=bool(user_data["is_admin"]), key="edit_user_admin_checkbox")
                
                if st.form_submit_button("💾 Atualizar Usuário", key="update_user_button"):
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
        st.info("Nenhum usuário encontrado", key="no_users_found")

def manage_teams_players_page():
    st.header("🏆 Times e Jogadores")
    
    tab1, tab2 = st.tabs(["🏆 Times", "👤 Jogadores"], key="manage_teams_players_tabs")
    
    with tab1:
        teams = get_all_teams()
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📋 Times Existentes", key="existing_teams_subheader")
            for team_idx, team in enumerate(teams):
                st.write(f"• {team['name']}", key=f"existing_team_{team_idx}")
        
        with col2:
            st.subheader("➕ Adicionar Time", key="add_team_subheader")
            
            with st.form("add_team_form", key="add_team_form"):
                team_name = st.text_input("Nome do Time:", key="new_team_name_input")
                
                if st.form_submit_button("🏆 Adicionar", key="add_team_submit_button"):
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
            st.subheader("📋 Jogadores Existentes", key="existing_players_subheader")
            
            if players:
                for player_idx, player in enumerate(players):
                    team_name = get_team_name(player["team_id"])
                    st.write(f"• {player['name']} ({team_name})", key=f"existing_player_{player_idx}")
            else:
                st.write("Nenhum jogador cadastrado", key="no_players_registered")
        
        with col2:
            st.subheader("➕ Adicionar Jogador", key="add_player_subheader")
            
            if teams:
                with st.form("add_player_form", key="add_player_form"):
                    player_name = st.text_input("Nome do Jogador:", key="new_player_name_input")
                    
                    team_options = {team["name"]: team["id"] for team in teams}
                    selected_team = st.selectbox("Time:", list(team_options.keys()), key="new_player_team_select")
                    
                    if st.form_submit_button("👤 Adicionar", key="add_player_submit_button"):
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
                st.warning("Adicione times primeiro", key="add_teams_first_warning")

def reports_page():
    st.header("📈 Relatórios")
    
    # Betting statistics
    conn = sqlite3.connect("guimabet.db")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Estatísticas de Apostas", key="betting_stats_subheader")
        
        # Total bets by status
        bet_stats = pd.read_sql_query("""
        SELECT status, COUNT(*) as count, SUM(amount) as total_amount
        FROM bets
        GROUP BY status
        """, conn)
        
        if not bet_stats.empty:
            st.dataframe(bet_stats, key="bet_stats_dataframe")
        
        # Top bettors
        st.subheader("🏆 Maiores Apostadores", key="top_bettors_subheader")
        top_bettors = pd.read_sql_query("""
        SELECT user_id, COUNT(*) as total_bets, SUM(amount) as total_amount
        FROM bets
        GROUP BY user_id
        ORDER BY total_amount DESC
        LIMIT 10
        """, conn)
        
        if not top_bettors.empty:
            st.dataframe(top_bettors, key="top_bettors_dataframe")
    
    with col2:
        st.subheader("💰 Análise Financeira", key="financial_analysis_subheader")
        
        # Daily betting volume
        daily_volume = pd.read_sql_query("""
        SELECT DATE(timestamp) as date, COUNT(*) as bets, SUM(amount) as volume
        FROM bets
        WHERE timestamp >= date('now', '-30 days')
        GROUP BY DATE(timestamp)
        ORDER BY date DESC
        """, conn)
        
        if not daily_volume.empty:
            st.line_chart(daily_volume.set_index("date")["volume"], key="daily_volume_chart")
        
        # Win/Loss ratio
        win_loss = pd.read_sql_query("""
        SELECT 
            SUM(CASE WHEN status = 'won' THEN amount ELSE 0 END) as total_winnings,
            SUM(CASE WHEN status = 'lost' THEN amount ELSE 0 END) as total_losses,
            COUNT(CASE WHEN status = 'won' THEN 1 END) as wins,
            COUNT(CASE WHEN status = 'lost' THEN 1 END) as losses
        FROM bets
        WHERE status IN ('won', 'lost')
        """, conn)
        
        if not win_loss.empty and win_loss.iloc[0]["wins"] > 0:
            st.metric("Taxa de Vitória", f"{win_loss.iloc[0]['wins'] / (win_loss.iloc[0]['wins'] + win_loss.iloc[0]['losses']) * 100:.1f}%", key="win_rate_metric")
    
    conn.close()


