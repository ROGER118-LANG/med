import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib

# --- Funções de Banco de Dados (Adicionadas e Atualizadas) ---

def db_connect():
    """Cria e retorna uma conexão com o banco de dados."""
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_all_users():
    conn = db_connect()
    users = [dict(row) for row in conn.execute("SELECT username, points, is_admin FROM users ORDER BY points DESC").fetchall()]
    conn.close()
    return users

def get_upcoming_matches():
    conn = db_connect()
    matches = [dict(row) for row in conn.execute("SELECT * FROM matches WHERE status = 'upcoming' ORDER BY date, time").fetchall()]
    conn.close()
    return matches

def get_match_history():
    conn = db_connect()
    matches = [dict(row) for row in conn.execute("SELECT * FROM matches WHERE status = 'completed' ORDER BY date DESC, time DESC").fetchall()]
    conn.close()
    return matches

def get_all_teams():
    conn = db_connect()
    teams = [dict(row) for row in conn.execute("SELECT id, name FROM teams ORDER BY name").fetchall()]
    conn.close()
    return teams

def get_team_name(team_id):
    conn = db_connect()
    name = conn.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
    conn.close()
    return name['name'] if name else "Desconhecido"

def get_custom_bet_proposals(status='pending'):
    conn = db_connect()
    proposals = [dict(row) for row in conn.execute("""
        SELECT p.id, p.user_id, p.match_id, p.description, p.proposed_odds, u.username
        FROM custom_bet_proposals p JOIN users u ON p.user_id = u.username
        WHERE p.status = ?
    """, (status,)).fetchall()]
    conn.close()
    return proposals

def add_match(team1_id, team2_id, date, time):
    conn = db_connect()
    try:
        conn.execute("INSERT INTO matches (team1_id, team2_id, date, time, status) VALUES (?, ?, ?, ?, 'upcoming')",
                     (team1_id, team2_id, date, time))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao adicionar partida: {e}")
        return False
    finally:
        conn.close()

# --- NOVAS FUNÇÕES PARA APOSTAS PERSONALIZADAS ---

def add_custom_bet(match_id, description, odds):
    """Adiciona uma nova aposta personalizada criada pelo admin."""
    conn = db_connect()
    try:
        conn.execute("INSERT INTO custom_bets (match_id, description, odds, status) VALUES (?, ?, ?, 'pending')",
                     (match_id, description, odds))
        conn.commit()
        return True
    except Exception as e:
        st.error(f"Erro ao criar aposta personalizada: {e}")
        return False
    finally:
        conn.close()

def get_active_custom_bets():
    """Busca todas as apostas personalizadas com status 'pending'."""
    conn = db_connect()
    bets = [dict(row) for row in conn.execute("SELECT * FROM custom_bets WHERE status = 'pending' ORDER BY id DESC").fetchall()]
    conn.close()
    return bets

def resolve_custom_bet(bet_id, result):
    """Resolve uma aposta personalizada e atualiza as apostas dos usuários."""
    conn = db_connect()
    c = conn.cursor()
    try:
        # Pega a odd da aposta personalizada
        bet_info = c.execute("SELECT odds FROM custom_bets WHERE id = ?", (bet_id,)).fetchone()
        if not bet_info:
            st.error("Aposta personalizada não encontrada.")
            return False
        
        odds = bet_info['odds']

        # Atualiza o status da aposta personalizada
        c.execute("UPDATE custom_bets SET status = ? WHERE id = ?", (result, bet_id))

        # Se o resultado for 'ganha', paga os usuários
        if result == 'won':
            # Encontra todas as apostas de usuários para esta aposta personalizada
            user_bets = c.execute("SELECT id, user_id, amount FROM bets WHERE custom_bet_id = ? AND status = 'pending'", (bet_id,)).fetchall()
            for user_bet in user_bets:
                winnings = user_bet['amount'] * odds
                # Devolve o valor apostado + o lucro
                c.execute("UPDATE users SET points = points + ? WHERE username = ?", (winnings, user_bet['user_id']))
                c.execute("UPDATE bets SET status = 'won' WHERE id = ?", (user_bet['id'],))
        
        # Se for 'lost', apenas atualiza o status das apostas dos usuários
        elif result == 'lost':
            c.execute("UPDATE bets SET status = 'lost' WHERE custom_bet_id = ? AND status = 'pending'", (bet_id,))

        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Erro ao resolver aposta: {e}")
        return False
    finally:
        conn.close()


# --- Páginas do Painel de Administrador (com manage_custom_bets_page implementada) ---

def dashboard_page():
    st.header("📊 Dashboard do Administrador")
    st.write("Visão geral do estado atual da plataforma.")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total de Usuários", len(get_all_users()))
    with col2:
        st.metric("Total de Partidas", len(get_upcoming_matches()) + len(get_match_history()))
    with col3:
        conn = db_connect()
        total_bets = conn.execute("SELECT COUNT(*) FROM bets").fetchone()[0]
        conn.close()
        st.metric("Total de Apostas", total_bets)
    st.subheader("Atividade Recente")
    st.info("Gráficos e atividades recentes serão exibidos aqui em breve.")

def manage_matches_page():
    st.header("⚽ Gerenciar Partidas")
    st.subheader("Adicionar Nova Partida")
    teams = get_all_teams()
    team_dict = {team['name']: team['id'] for team in teams}
    if not teams or len(teams) < 2:
        st.warning("Você precisa de pelo menos dois times cadastrados para criar uma partida.")
        return
    with st.form("add_match_form", clear_on_submit=True):
        team1_name = st.selectbox("Time da Casa", options=list(team_dict.keys()), index=0, key="team1_select")
        team2_name = st.selectbox("Time Visitante", options=list(team_dict.keys()), index=1, key="team2_select")
        match_date = st.date_input("Data da Partida", min_value=datetime.date.today())
        match_time = st.time_input("Hora da Partida")
        submitted = st.form_submit_button("Adicionar Partida")
        if submitted:
            if team1_name == team2_name:
                st.error("Os times da casa e visitante não podem ser os mesmos.")
            else:
                if add_match(team_dict[team1_name], team_dict[team2_name], match_date.strftime("%Y-%m-%d"), match_time.strftime("%H:%M")):
                    st.success(f"Partida '{team1_name} vs {team2_name}' adicionada com sucesso!")
                    st.rerun()
    st.divider()
    st.subheader("Partidas Futuras")
    upcoming_matches = get_upcoming_matches()
    if upcoming_matches:
        st.dataframe(pd.DataFrame(upcoming_matches), use_container_width=True)
    else:
        st.info("Nenhuma partida futura cadastrada.")

def manage_odds_page():
    st.header("🎯 Gerenciar Odds")
    st.info("A funcionalidade de gerenciamento de odds será implementada aqui.")

# --- PÁGINA DE APOSTAS PERSONALIZADAS IMPLEMENTADA ---
def manage_custom_bets_page():
    st.header("🎲 Gerenciar Apostas Personalizadas")

    # 1. Formulário para criar uma nova aposta personalizada
    st.subheader("Criar Nova Aposta Personalizada")
    upcoming_matches = get_upcoming_matches()
    if not upcoming_matches:
        st.warning("Nenhuma partida futura disponível para criar uma aposta personalizada.")
    else:
        match_dict = {f"ID {m['id']}: {get_team_name(m['team1_id'])} vs {get_team_name(m['team2_id'])}": m['id'] for m in upcoming_matches}
        with st.form("create_custom_bet_form", clear_on_submit=True):
            selected_match_str = st.selectbox("Selecione a Partida", options=list(match_dict.keys()))
            description = st.text_input("Descrição da Aposta", placeholder="Ex: Algum jogador vai marcar um gol de bicicleta?")
            odds = st.number_input("Odds", min_value=1.01, value=2.0, step=0.1)
            
            submitted = st.form_submit_button("Criar Aposta")
            if submitted:
                if not description:
                    st.error("A descrição não pode estar vazia.")
                else:
                    match_id = match_dict[selected_match_str]
                    if add_custom_bet(match_id, description, odds):
                        st.success("Aposta personalizada criada com sucesso!")
                        st.rerun()

    st.divider()

    # 2. Listar e resolver apostas personalizadas ativas
    st.subheader("Apostas Personalizadas Ativas")
    active_bets = get_active_custom_bets()
    if not active_bets:
        st.info("Nenhuma aposta personalizada ativa no momento.")
    else:
        for bet in active_bets:
            with st.container(border=True):
                st.write(f"**ID da Aposta:** {bet['id']} | **Partida ID:** {bet['match_id']}")
                st.write(f"**Descrição:** {bet['description']}")
                st.write(f"**Odds:** {bet['odds']}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✔️ Marcar como GANHA", key=f"win_{bet['id']}", use_container_width=True):
                        if resolve_custom_bet(bet['id'], 'won'):
                            st.success(f"Aposta {bet['id']} resolvida como 'Ganha'. Pagamentos processados.")
                            st.rerun()
                with col2:
                    if st.button("❌ Marcar como PERDIDA", key=f"lose_{bet['id']}", use_container_width=True):
                        if resolve_custom_bet(bet['id'], 'lost'):
                            st.warning(f"Aposta {bet['id']} resolvida como 'Perdida'.")
                            st.rerun()

def manage_proposals_page():
    st.header("💡 Propostas de Usuários")
    proposals = get_custom_bet_proposals("pending")
    if not proposals:
        st.info("Nenhuma proposta pendente no momento.")
        return
    for idx, proposal in enumerate(proposals):
        with st.container(border=True):
            st.write(f"**Proposta de:** {proposal['username']} | **Partida ID:** {proposal['match_id']}")
            st.write(f"**Descrição:** {proposal['description']} | **Odd Proposta:** {proposal['proposed_odds']}")
            with st.form(f"review_proposal_{idx}"):
                final_odds = st.number_input("Odd Final", value=proposal['proposed_odds'], min_value=1.01, step=0.1, key=f"odds_{idx}")
                col1, col2 = st.columns(2)
                if col1.form_submit_button("Aprovar", use_container_width=True):
                    st.success(f"Proposta {proposal['id']} aprovada.")
                    st.rerun()
                if col2.form_submit_button("Rejeitar", type="secondary", use_container_width=True):
                    st.warning(f"Proposta {proposal['id']} rejeitada.")
                    st.rerun()

def manage_users_page():
    st.header("👥 Gerenciar Usuários")
    users = get_all_users()
    if users:
        st.dataframe(pd.DataFrame(users), use_container_width=True)
    else:
        st.info("Nenhum usuário encontrado.")

def manage_teams_players_page():
    st.header("🏆 Times e Jogadores")
    st.info("A funcionalidade de gerenciamento de times e jogadores será implementada aqui.")

def main_admin_panel_content():
    st.title("Painel de Administração")
    with st.sidebar:
        selected_page = st.radio(
            "Navegação do Admin",
            ["📊 Dashboard", "⚽ Gerenciar Partidas", "🎯 Gerenciar Odds", "🎲 Apostas Personalizadas",
             "💡 Propostas de Usuários", "👥 Gerenciar Usuários", "🏆 Times e Jogadores"],
            key="admin_nav"
        )
    page_map = {
        "📊 Dashboard": dashboard_page,
        "⚽ Gerenciar Partidas": manage_matches_page,
        "🎯 Gerenciar Odds": manage_odds_page,
        "🎲 Apostas Personalizadas": manage_custom_bets_page,
        "💡 Propostas de Usuários": manage_proposals_page,
        "👥 Gerenciar Usuários": manage_users_page,
        "🏆 Times e Jogadores": manage_teams_players_page,
    }
    page_function = page_map.get(selected_page)
    if page_function:
        page_function()

