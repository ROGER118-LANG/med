import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib
import os
import random
import json

# Import all functions from the enhanced module
from guimabet_melhorado import *

# Import the refactored admin panel module
import admin_panel_enhanced

# Configure page
st.set_page_config(
    page_title="GuimaBet - Sistema de Apostas",
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

def login_page():
    st.title("🏆 GuimaBet - Sistema de Apostas Esportivas")
    
    tab1, tab2 = st.tabs(["🔐 Login", "📝 Cadastro"])
    
    with tab1:
        st.subheader("Entrar na sua conta")
        
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar")
            
            if submit:
                user = login(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.session_state.is_admin = bool(user[3])
                    st.success("Login realizado com sucesso!")
                    st.rerun()
                else:
                    st.error("Credenciais inválidas")
    
    with tab2:
        st.subheader("Criar nova conta")
        
        with st.form("register_form"):
            new_username = st.text_input("Novo usuário")
            new_password = st.text_input("Nova senha", type="password")
            confirm_password = st.text_input("Confirmar senha", type="password")
            submit_register = st.form_submit_button("Cadastrar")
            
            if submit_register:
                if new_password != confirm_password:
                    st.error("Senhas não coincidem")
                elif len(new_password) < 3:
                    st.error("Senha deve ter pelo menos 3 caracteres")
                elif register(new_username, new_password):
                    st.success("Conta criada com sucesso! Faça login.")
                else:
                    st.error("Erro ao criar conta. Usuário pode já existir.")

def user_dashboard():
    st.title(f"🏆 Bem-vindo, {st.session_state.username}!")
    
    # Get user info
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE username = ?", (st.session_state.username,))
    user_points = c.fetchone()[0]
    conn.close()
    
    # Sidebar
    st.sidebar.title("Menu")
    st.sidebar.write(f"💰 Pontos: {user_points}")
    
    menu_options = ["🎯 Apostar", "📊 Minhas Apostas", "📈 Histórico", "💡 Propor Aposta"]
    
    if st.session_state.is_admin:
        menu_options.append("⚙️ Painel Admin")
    
    selected_page = st.sidebar.selectbox("Navegar:", menu_options)
    
    if st.sidebar.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False
        st.rerun()
    
    # Page routing
    if selected_page == "🎯 Apostar":
        betting_page()
    elif selected_page == "📊 Minhas Apostas":
        my_bets_page()
    elif selected_page == "📈 Histórico":
        history_page()
    elif selected_page == "💡 Propor Aposta":
        propose_bet_page()
    elif selected_page == "⚙️ Painel Admin" and st.session_state.is_admin:
        admin_panel_enhanced.main_admin_panel_content()

def betting_page():
    st.header("🎯 Fazer Apostas")
    
    matches = get_upcoming_matches()
    
    if not matches:
        st.warning("Nenhuma partida disponível para apostas no momento.")
        return
    
    for match in matches:
        team1_name = get_team_name(match['team1_id'])
        team2_name = get_team_name(match['team2_id'])
        
        with st.expander(f"⚽ {team1_name} vs {team2_name} - {match['date']} {match['time']} ({match['status']})"):
            
            # Get enhanced odds for this match
            match_odds = get_match_odds(match['id'])
            custom_bets = get_custom_bets(match['id'])
            
            if match_odds or custom_bets or (match.get('team1_win') and match.get('draw') and match.get('team2_win')):
                
                # Enhanced odds section
                if match_odds:
                    st.subheader("🎯 Apostas Disponíveis")
                    
                    # Group odds by category
                    odds_by_category = {}
                    for odd in match_odds:
                        category = odd['category_name']
                        if category not in odds_by_category:
                            odds_by_category[category] = []
                        odds_by_category[category].append(odd)
                    
                    for category, odds_list in odds_by_category.items():
                        st.write(f"**📂 {category}**")
                        
                        cols = st.columns(min(3, len(odds_list)))
                        
                        for i, odd in enumerate(odds_list):
                            with cols[i % 3]:
                                display_name = odd['template_name']
                                if odd['player_name']:
                                    display_name += f" ({odd['player_name']})"
                                
                                st.write(f"**{display_name}**")
                                st.write(f"_{odd['description']}_")
                                st.write(f"**Odds: {odd['odds_value']}**")
                                
                                amount = st.number_input(
                                    "Valor da aposta:", 
                                    min_value=1, 
                                    max_value=1000, 
                                    value=10,
                                    key=f"amount_enhanced_{odd['id']}"
                                )
                                
                                potential_win = amount * odd['odds_value']
                                st.write(f"💰 Ganho potencial: {potential_win:.2f} pontos")
                                
                                if st.button(f"🎯 Apostar", key=f"bet_enhanced_{odd['id']}"):
                                    success, message = place_enhanced_bet(
                                        st.session_state.username,
                                        match['id'],
                                        odd['bet_type'],
                                        amount,
                                        match_odds_id=odd['id'],
                                        player_id=odd['player_id']
                                    )
                                    
                                    if success:
                                        st.success(message)
                                        st.rerun()
                                    else:
                                        st.error(message)
                        
                        st.divider()
                
                # Legacy odds section (for backward compatibility)
                if match.get('team1_win') and match.get('draw') and match.get('team2_win'):
                    st.subheader("🏆 Apostas Clássicas")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.write(f"**{team1_name} Vence**")
                        st.write(f"Odds: {match['team1_win']}")
                        amount1 = st.number_input("Valor:", min_value=1, max_value=1000, value=10, key=f"amount1_{match['id']}")
                        if st.button("Apostar", key=f"bet1_{match['id']}"):
                            success, message = place_bet(st.session_state.username, match['id'], 'team1_win', amount1)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    
                    with col2:
                        st.write("**Empate**")
                        st.write(f"Odds: {match['draw']}")
                        amount_draw = st.number_input("Valor:", min_value=1, max_value=1000, value=10, key=f"amount_draw_{match['id']}")
                        if st.button("Apostar", key=f"bet_draw_{match['id']}"):
                            success, message = place_bet(st.session_state.username, match['id'], 'draw', amount_draw)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    
                    with col3:
                        st.write(f"**{team2_name} Vence**")
                        st.write(f"Odds: {match['team2_win']}")
                        amount2 = st.number_input("Valor:", min_value=1, max_value=1000, value=10, key=f"amount2_{match['id']}")
                        if st.button("Apostar", key=f"bet2_{match['id']}"):
                            success, message = place_bet(st.session_state.username, match['id'], 'team2_win', amount2)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                
                # Custom bets section
                if custom_bets:
                    st.subheader("🎲 Apostas Especiais")
                    
                    for custom_bet in custom_bets:
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write(f"**{custom_bet['description']}**")
                            st.write(f"Odds: {custom_bet['odds']}")
                            if custom_bet['player_id']:
                                player_name = get_player_name(custom_bet['player_id'])
                                st.write(f"Jogador: {player_name}")
                        
                        with col2:
                            amount_custom = st.number_input(
                                "Valor:", 
                                min_value=1, 
                                max_value=1000, 
                                value=10, 
                                key=f"amount_custom_{custom_bet['id']}"
                            )
                            
                            potential_win = amount_custom * custom_bet['odds']
                            st.write(f"💰 Ganho: {potential_win:.2f}")
                            
                            if st.button("🎲 Apostar", key=f"bet_custom_{custom_bet['id']}"):
                                success, message = place_bet(
                                    st.session_state.username, 
                                    match['id'], 
                                    'custom', 
                                    amount_custom, 
                                    custom_bet_id=custom_bet['id']
                                )
                                
                                if success:
                                    st.success(message)
                                    st.rerun()
                                else:
                                    st.error(message)
                        
                        st.divider()
            
            else:
                st.info("Odds ainda não disponíveis para esta partida.")

def my_bets_page():
    st.header("📊 Minhas Apostas")
    
    bets = get_user_bets(st.session_state.username)
    
    if not bets:
        st.info("Você ainda não fez nenhuma aposta.")
        return
    
    # Filter options
    status_filter = st.selectbox("Filtrar por status:", ["Todas", "pending", "won", "lost"])
    
    filtered_bets = bets
    if status_filter != "Todas":
        filtered_bets = [bet for bet in bets if bet['status'] == status_filter]
    
    # Statistics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_bets = len(bets)
        st.metric("Total de Apostas", total_bets)
    
    with col2:
        won_bets = len([bet for bet in bets if bet['status'] == 'won'])
        st.metric("Apostas Ganhas", won_bets)
    
    with col3:
        total_amount = sum(bet['amount'] for bet in bets)
        st.metric("Total Apostado", f"{total_amount} pts")
    
    with col4:
        if total_bets > 0:
            win_rate = (won_bets / total_bets) * 100
            st.metric("Taxa de Acerto", f"{win_rate:.1f}%")
    
    # Display bets
    for bet in filtered_bets:
        team1_name = get_team_name(bet['team1_id'])
        team2_name = get_team_name(bet['team2_id'])
        
        # Status color
        status_color = {
            'pending': '🟡',
            'won': '🟢',
            'lost': '🔴'
        }.get(bet['status'], '⚪')
        
        with st.expander(f"{status_color} {team1_name} vs {team2_name} - {bet['bet_type']} ({bet['status']})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Partida:** {team1_name} vs {team2_name}")
                st.write(f"**Data:** {bet['date']} {bet['time']}")
                st.write(f"**Tipo de Aposta:** {bet['bet_type']}")
                st.write(f"**Valor Apostado:** {bet['amount']} pontos")
                st.write(f"**Status:** {bet['status']}")
                st.write(f"**Data da Aposta:** {bet['timestamp']}")
            
            with col2:
                if bet['potential_winnings'] > 0:
                    st.write(f"**Ganho Potencial:** {bet['potential_winnings']:.2f} pontos")
                
                if bet['custom_bet_id']:
                    st.write("**Tipo:** Aposta Personalizada")
                elif bet['match_odds_id']:
                    st.write("**Tipo:** Aposta Avançada")
                else:
                    st.write("**Tipo:** Aposta Clássica")
                
                if bet['player_id']:
                    player_name = get_player_name(bet['player_id'])
                    st.write(f"**Jogador:** {player_name}")
                
                if bet['match_status'] == 'completed':
                    if bet['team1_score'] is not None and bet['team2_score'] is not None:
                        st.write(f"**Resultado:** {bet['team1_score']} - {bet['team2_score']}")

def history_page():
    st.header("📈 Histórico de Partidas")
    
    history = get_match_history()
    
    if not history:
        st.info("Nenhuma partida finalizada ainda.")
        return
    
    for match in history:
        team1_name = get_team_name(match['team1_id'])
        team2_name = get_team_name(match['team2_id'])
        
        # Determine winner
        if match['team1_score'] > match['team2_score']:
            winner = f"🏆 {team1_name}"
        elif match['team1_score'] < match['team2_score']:
            winner = f"🏆 {team2_name}"
        else:
            winner = "🤝 Empate"
        
        with st.expander(f"⚽ {team1_name} {match['team1_score']} - {match['team2_score']} {team2_name} ({match['date']})"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Resultado:** {match['team1_score']} - {match['team2_score']}")
                st.write(f"**Vencedor:** {winner}")
                st.write(f"**Data:** {match['date']} {match['time']}")
            
            with col2:
                if match.get('team1_win'):
                    st.write("**Odds da partida:**")
                    st.write(f"• {team1_name}: {match['team1_win']}")
                    st.write(f"• Empate: {match['draw']}")
                    st.write(f"• {team2_name}: {match['team2_win']}")

def propose_bet_page():
    st.header("💡 Propor Aposta Personalizada")
    
    st.info("Aqui você pode sugerir apostas personalizadas para a administração revisar.")
    
    matches = get_upcoming_matches()
    
    if not matches:
        st.warning("Nenhuma partida disponível para propor apostas no momento.")
        return
    
    with st.form("propose_bet_form"):
        match_options = {}
        for match in matches:
            team1 = get_team_name(match['team1_id'])
            team2 = get_team_name(match['team2_id'])
            match_key = f"{team1} vs {team2} - {match['date']} {match['time']}"
            match_options[match_key] = match['id']
        
        selected_match_key = st.selectbox("Selecione a partida:", list(match_options.keys()))
        selected_match_id = match_options[selected_match_key]
        
        description = st.text_area("Descreva sua aposta (ex: 'Jogador X marcará mais de 2 gols'):")
        proposed_odds = st.number_input("Odds propostas (ex: 2.50):", min_value=1.01, value=2.0, step=0.01)
        
        submit_proposal = st.form_submit_button("Propor Aposta")
        
        if submit_proposal:
            if description:
                success, message = add_custom_bet_proposal(
                    st.session_state.username, 
                    selected_match_id, 
                    description, 
                    proposed_odds
                )
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("A descrição da aposta é obrigatória.")

def main():
    if not st.session_state.logged_in:
        login_page()
    else:
        user_dashboard()

if __name__ == "__main__":
    main()


