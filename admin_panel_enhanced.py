import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib

# --- Funções de Banco de Dados (versões específicas para o painel admin) ---
# É uma boa prática ter as funções que o painel usa aqui ou importá-las de um arquivo comum.

def get_all_users():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT username, points, is_admin FROM users ORDER BY points DESC")
    users = [dict(row) for row in c.fetchall()]
    conn.close()
    return users

def get_upcoming_matches():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE status = 'upcoming' ORDER BY date, time")
    matches = [dict(row) for row in c.fetchall()]
    conn.close()
    return matches

def get_match_history():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM matches WHERE status = 'completed' ORDER BY date DESC, time DESC")
    matches = [dict(row) for row in c.fetchall()]
    conn.close()
    return matches

def get_all_teams():
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT id, name FROM teams ORDER BY name")
    teams = [dict(row) for row in c.fetchall()]
    conn.close()
    return teams

def get_custom_bet_proposals(status='pending'):
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("""
        SELECT p.id, p.user_id, p.match_id, p.description, p.proposed_odds, u.username
        FROM custom_bet_proposals p
        JOIN users u ON p.user_id = u.username
        WHERE p.status = ?
    """, (status,))
    proposals = [dict(row) for row in c.fetchall()]
    conn.close()
    return proposals

def add_match(team1_id, team2_id, date, time):
    conn = sqlite3.connect('guimabet.db')
    c = conn.cursor()
    try:
        c.execute("INSERT INTO matches (team1_id, team2_id, date, time, status) VALUES (?, ?, ?, ?, 'upcoming')",
                  (team1_id, team2_id, date, time))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar partida: {e}")
        return False
    finally:
        conn.close()

# --- Páginas do Painel de Administrador ---

def dashboard_page():
    """Exibe o dashboard principal com métricas."""
    st.header("📊 Dashboard do Administrador")
    st.write("Visão geral do estado atual da plataforma.")

    col1, col2, col3 = st.columns(3)

    with col1:
        users = get_all_users()
        # CORRIGIDO: Removido o argumento 'key'
        st.metric("Total de Usuários", len(users))

    with col2:
        matches = get_upcoming_matches() + get_match_history()
        # CORRIGIDO: Removido o argumento 'key'
        st.metric("Total de Partidas", len(matches))

    with col3:
        conn = sqlite3.connect("guimabet.db")
        try:
            total_bets = conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
            # CORRIGIDO: Removido o argumento 'key'
            st.metric("Total de Apostas", total_bets)
        finally:
            conn.close()

    st.subheader("Atividade Recente")
    # Placeholder para gráficos ou tabelas de atividade
    st.info("Gráficos e atividades recentes serão exibidos aqui em breve.")


def manage_matches_page():
    """Página para gerenciar partidas."""
    st.header("⚽ Gerenciar Partidas")

    st.subheader("Adicionar Nova Partida")
    teams = get_all_teams()
    team_dict = {team['name']: team['id'] for team in teams}

    if not teams or len(teams) < 2:
        st.warning("Você precisa de pelo menos dois times cadastrados para criar uma partida.")
        return

    with st.form("add_match_form", clear_on_submit=True):
        team1_name = st.selectbox("Time da Casa", options=list(team_dict.keys()), key="team1_select")
        team2_name = st.selectbox("Time Visitante", options=list(team_dict.keys()), key="team2_select")
        match_date = st.date_input("Data da Partida", min_value=datetime.date.today())
        match_time = st.time_input("Hora da Partida")

        submitted = st.form_submit_button("Adicionar Partida")

        if submitted:
            if team1_name == team2_name:
                st.error("Os times da casa e visitante não podem ser os mesmos.")
            else:
                team1_id = team_dict[team1_name]
                team2_id = team_dict[team2_name]
                if add_match(team1_id, team2_id, match_date.strftime("%Y-%m-%d"), match_time.strftime("%H:%M")):
                    st.success(f"Partida '{team1_name} vs {team2_name}' adicionada com sucesso!")
                else:
                    st.error("Falha ao adicionar a partida.")

    st.divider()

    st.subheader("Partidas Futuras")
    upcoming_matches = get_upcoming_matches()
    if upcoming_matches:
        df_upcoming = pd.DataFrame(upcoming_matches)
        st.dataframe(df_upcoming, use_container_width=True)
    else:
        # CORRIGIDO: Removido o argumento 'key'
        st.info("Nenhuma partida futura cadastrada.")


def manage_odds_page():
    """Página para gerenciar odds."""
    st.header("🎯 Gerenciar Odds")
    st.info("A funcionalidade de gerenciamento de odds será implementada aqui.")
    # Placeholder para a lógica de gerenciamento de odds


def manage_custom_bets_page():
    """Página para gerenciar apostas personalizadas."""
    st.header("🎲 Apostas Personalizadas")
    st.info("A funcionalidade de gerenciamento de apostas personalizadas será implementada aqui.")
    # Placeholder para a lógica de gerenciamento de apostas personalizadas


def manage_proposals_page():
    """Página para gerenciar propostas de apostas dos usuários."""
    st.header("💡 Propostas de Usuários")
    proposals = get_custom_bet_proposals("pending")

    if not proposals:
        # CORRIGIDO: Removido o argumento 'key'
        st.info("Nenhuma proposta pendente no momento.")
        return

    for idx, proposal in enumerate(proposals):
        with st.container(border=True):
            st.write(f"**Proposta de:** {proposal['username']}")
            st.write(f"**Partida ID:** {proposal['match_id']}")
            st.write(f"**Descrição:** {proposal['description']}")
            st.write(f"**Odd Proposta:** {proposal['proposed_odds']}")

            with st.form(f"review_proposal_{idx}"):
                admin_response = st.text_area("Resposta/Justificativa (opcional)", key=f"response_{idx}")
                final_odds = st.number_input("Odd Final (se aprovada)", value=proposal['proposed_odds'], min_value=1.01, step=0.1, key=f"odds_{idx}")

                col1, col2 = st.columns(2)
                with col1:
                    approve_button = st.form_submit_button("Aprovar Proposta", use_container_width=True)
                with col2:
                    reject_button = st.form_submit_button("Rejeitar Proposta", type="secondary", use_container_width=True)

                if approve_button:
                    # Lógica para aprovar (placeholder)
                    st.success(f"Proposta {proposal['id']} aprovada com odds de {final_odds}.")
                    # Aqui você chamaria a função para atualizar o status no DB
                    st.rerun()

                if reject_button:
                    # Lógica para rejeitar (placeholder)
                    st.warning(f"Proposta {proposal['id']} rejeitada.")
                    # Aqui você chamaria a função para atualizar o status no DB
                    st.rerun()


def manage_users_page():
    """Página para gerenciar usuários."""
    st.header("👥 Gerenciar Usuários")
    users = get_all_users()
    if users:
        df_users = pd.DataFrame(users)
        st.dataframe(df_users, use_container_width=True)
    else:
        # CORRIGIDO: Removido o argumento 'key'
        st.info("Nenhum usuário encontrado.")


def manage_teams_players_page():
    """Página para gerenciar times e jogadores."""
    st.header("🏆 Times e Jogadores")
    st.info("A funcionalidade de gerenciamento de times e jogadores será implementada aqui.")
    # Placeholder para a lógica de gerenciamento


def main_admin_panel_content():
    """Função principal que renderiza o painel de admin e suas páginas."""
    st.title("Painel de Administração")

    with st.sidebar:
        selected_page = st.radio(
            "Navegação do Admin",
            ["📊 Dashboard", "⚽ Gerenciar Partidas", "🎯 Gerenciar Odds", "🎲 Apostas Personalizadas",
             "💡 Propostas de Usuários", "👥 Gerenciar Usuários", "🏆 Times e Jogadores"],
            key="admin_nav"
        )

    # Roteamento de página
    if selected_page == "📊 Dashboard":
        dashboard_page()
    elif selected_page == "⚽ Gerenciar Partidas":
        manage_matches_page()
    elif selected_page == "🎯 Gerenciar Odds":
        manage_odds_page()
    elif selected_page == "🎲 Apostas Personalizadas":
        manage_custom_bets_page()
    elif selected_page == "💡 Propostas de Usuários":
        manage_proposals_page()
    elif selected_page == "👥 Gerenciar Usuários":
        manage_users_page()
    elif selected_page == "🏆 Times e Jogadores":
        manage_teams_players_page()

