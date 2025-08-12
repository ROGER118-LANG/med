import streamlit as st
import pandas as pd
import datetime
import sqlite3
import hashlib
import admin_panel_enhanced # Certifique-se de que este arquivo está na mesma pasta

# --- Funções de Banco de Dados (Completas) ---

def db_connect():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    return conn

# (init_db, register_user, login, etc. permanecem os mesmos da versão anterior)
# ...

# --- NOVA FUNÇÃO PARA HISTÓRICO DE APOSTAS ---

def get_user_bets(username):
    """Busca todas as apostas de um usuário com detalhes da partida."""
    conn = db_connect()
    bets = [dict(row) for row in conn.execute("""
        SELECT 
            b.id, b.amount, b.odds, b.status, b.timestamp,
            m.team1_id, m.team2_id, m.date, m.time,
            cb.description as custom_bet_description,
            ot.name as bet_template_name
        FROM bets b
        JOIN matches m ON b.match_id = m.id
        LEFT JOIN custom_bets cb ON b.custom_bet_id = cb.id
        LEFT JOIN match_odds mo ON b.match_odds_id = mo.id
        LEFT JOIN odds_templates ot ON mo.template_id = ot.id
        WHERE b.user_id = ?
        ORDER BY b.timestamp DESC
    """, (username,)).fetchall()]
    conn.close()
    return bets

# (As outras funções de banco de dados como get_team_name, etc., permanecem)
# ...

# --- Interface do Streamlit (Completa) ---

# (login_page e a inicialização do session_state permanecem os mesmos)
# ...

def user_dashboard():
    """Dashboard principal para usuários logados."""
    st.sidebar.title(f"Olá, {st.session_state.username}!")
    st.sidebar.write(f"**Pontos:** {get_user_points(st.session_state.username)}")
    
    if st.sidebar.button("Logout"):
        # Limpa o estado da sessão para um logout completo
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    if st.session_state.get('is_admin', False):
        st.sidebar.subheader("Opções de Administrador")
        if st.sidebar.button("Painel Admin"):
            st.session_state.page = "admin_panel"
            st.rerun()

    if st.session_state.get('page') != "main":
        if st.sidebar.button("Voltar ao Início"):
            st.session_state.page = "main"
            st.rerun()

    st.title("GuimaBet Dashboard")

    if st.session_state.get('is_admin') and st.session_state.get('page') == 'admin_panel':
        admin_panel_enhanced.main_admin_panel_content()
    else:
        main_user_content()

def main_user_content():
    """Conteúdo principal do dashboard do usuário, incluindo o histórico de apostas."""
    tab1, tab2 = st.tabs(["Partidas Disponíveis", "Meu Histórico de Apostas"])

    with tab1:
        st.header("Partidas Disponíveis para Apostar")
        # (O código para listar partidas e fazer apostas permanece o mesmo)
        # ...

    with tab2:
        st.header("Meu Histórico de Apostas")
        user_bets = get_user_bets(st.session_state.username)
        
        if not user_bets:
            st.info("Você ainda não fez nenhuma aposta.")
        else:
            for bet in user_bets:
                status_color = {
                    "pending": "gray",
                    "won": "green",
                    "lost": "red"
                }
                status_icon = {
                    "pending": "⏳",
                    "won": "✅",
                    "lost": "❌"
                }
                
                with st.container(border=True):
                    team1_name = get_team_name(bet['team1_id'])
                    team2_name = get_team_name(bet['team2_id'])
                    
                    st.subheader(f"{team1_name} vs {team2_name}")
                    
                    if bet['custom_bet_description']:
                        bet_description = f"Aposta Personalizada: *{bet['custom_bet_description']}*"
                    else:
                        bet_description = f"Aposta: *{bet.get('bet_template_name', 'Resultado Simples')}*"

                    st.markdown(bet_description)

                    col1, col2, col3 = st.columns(3)
                    col1.metric("Valor Apostado", f"{bet['amount']} pts")
                    col2.metric("Odds", f"{bet['odds']:.2f}")
                    
                    potential_winnings = bet['amount'] * bet['odds']
                    if bet['status'] == 'won':
                        col3.metric("Resultado", f"+{potential_winnings:.0f} pts", delta_color="normal")
                    elif bet['status'] == 'lost':
                        col3.metric("Resultado", f"-{bet['amount']} pts", delta_color="inverse")
                    else:
                        col3.metric("Ganhos Potenciais", f"{potential_winnings:.0f} pts", delta_color="off")

                    st.caption(f"Status: :{status_color}[{bet['status'].upper()}] {status_icon.get(bet['status'], '')} | Data da Aposta: {bet['timestamp']}")

def main():
    """Função principal que executa a aplicação."""
    init_db() # Garante que o DB e as tabelas existam
    if not st.session_state.get('logged_in', False):
        login_page()
    else:
        user_dashboard()

if __name__ == "__main__":
    main()
