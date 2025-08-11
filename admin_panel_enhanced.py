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

def add_custom_bet(match_id, description, odds):
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
    conn = db_connect()
    bets = [dict(row) for row in conn.execute("SELECT * FROM custom_bets WHERE status = 'pending' ORDER BY id DESC").fetchall()]
    conn.close()
    return bets

def resolve_custom_bet(bet_id, result):
    conn = db_connect()
    c = conn.cursor()
    try:
        bet_info = c.execute("SELECT odds FROM custom_bets WHERE id = ?", (bet_id,)).fetchone()
        if not bet_info:
            st.error("Aposta personalizada não encontrada.")
            return False
        odds = bet_info['odds']
        c.execute("UPDATE custom_bets SET status = ? WHERE id = ?", (result, bet_id))
        if result == 'won':
            user_bets = c.execute("SELECT id, user_id, amount FROM bets WHERE custom_bet_id = ? AND status = 'pending'", (bet_id,)).fetchall()
            for user_bet in user_bets:
                winnings = user_bet['amount'] * odds
                c.execute("UPDATE users SET points = points + ? WHERE username = ?", (winnings, user_bet['user_id']))
                c.execute("UPDATE bets SET status = 'won' WHERE id = ?", (user_bet['id'],))
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

def add_team(name):
    if not name: return False, "O nome do time não pode ser vazio."
    conn = db_connect()
    try:
        conn.execute("INSERT INTO teams (name) VALUES (?)", (name,))
        conn.commit()
        return True, f"Time '{name}' adicionado com sucesso."
    except sqlite3.IntegrityError: return False, f"O time '{name}' já existe."
    except Exception as e: return False, f"Erro ao adicionar time: {e}"
    finally: conn.close()

def update_team_name(team_id, new_name):
    if not new_name: return False, "O novo nome não pode ser vazio."
    conn = db_connect()
    try:
        conn.execute("UPDATE teams SET name = ? WHERE id = ?", (new_name, team_id))
        conn.commit()
        return True, "Nome do time atualizado com sucesso."
    except sqlite3.IntegrityError: return False, f"O nome '{new_name}' já pertence a outro time."
    except Exception as e: return False, f"Erro ao atualizar o nome: {e}"
    finally: conn.close()

def delete_team(team_id):
    conn = db_connect()
    try:
        in_match = conn.execute("SELECT COUNT(*) FROM matches WHERE (team1_id = ? OR team2_id = ?) AND status = 'upcoming'", (team_id, team_id)).fetchone()[0]
        if in_match > 0: return False, "Não é possível deletar o time, pois ele está escalado em uma partida futura."
        conn.execute("DELETE FROM players WHERE team_id = ?", (team_id,))
        conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
        conn.commit()
        return True, "Time e jogadores associados foram deletados com sucesso."
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao deletar o time: {e}"
    finally: conn.close()

# --- NOVAS FUNÇÕES PARA GERENCIAR ODDS ---

def get_match_odds(match_id):
    """Busca as odds de uma partida específica, incluindo nomes de templates e categorias."""
    conn = db_connect()
    odds = [dict(row) for row in conn.execute("""
        SELECT mo.id, mo.odds_value, ot.name as template_name, oc.name as category_name, p.name as player_name
        FROM match_odds mo
        JOIN odds_templates ot ON mo.template_id = ot.id
        JOIN odds_categories oc ON ot.category_id = oc.id
        LEFT JOIN players p ON mo.player_id = p.id
        WHERE mo.match_id = ?
        ORDER BY oc.name, ot.name, p.name
    """, (match_id,)).fetchall()]
    conn.close()
    return odds

def update_match_odd(odd_id, new_value, admin_user, reason):
    """Atualiza o valor de uma odd e registra a mudança no histórico."""
    if not reason:
        return False, "O motivo da alteração é obrigatório."
    conn = db_connect()
    try:
        current_value = conn.execute("SELECT odds_value FROM match_odds WHERE id = ?", (odd_id,)).fetchone()[0]
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn.execute("UPDATE match_odds SET odds_value = ?, updated_at = ? WHERE id = ?", (new_value, timestamp, odd_id))
        conn.execute("""
            INSERT INTO odds_history (match_odds_id, old_value, new_value, changed_by, changed_at, reason)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (odd_id, current_value, new_value, admin_user, timestamp, reason))
        
        conn.commit()
        return True, "Odd atualizada com sucesso."
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao atualizar a odd: {e}"
    finally:
        conn.close()

def get_odd_history(odd_id):
    """Busca o histórico de alterações de uma odd específica."""
    conn = db_connect()
    history = [dict(row) for row in conn.execute("SELECT * FROM odds_history WHERE match_odds_id = ? ORDER BY changed_at DESC", (odd_id,)).fetchall()]
    conn.close()
    return history

def generate_default_odds_for_match(match_id):
    """Gera o conjunto padrão de odds para uma partida se não existirem."""
    conn = db_connect()
    try:
        # Verifica se já existem odds para não duplicar
        existing_odds = conn.execute("SELECT COUNT(*) FROM match_odds WHERE match_id = ?", (match_id,)).fetchone()[0]
        if existing_odds > 0:
            return False, "As odds para esta partida já existem."

        # Busca todos os templates de odds
        templates = conn.execute("SELECT * FROM odds_templates WHERE is_active = 1").fetchall()
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for template in templates:
            # Lógica simplificada para gerar odds (pode ser mais complexa)
            odds_value = template['default_odds']
            conn.execute("""
                INSERT INTO match_odds (match_id, template_id, odds_value, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (match_id, template['id'], odds_value, timestamp, timestamp))
        
        conn.commit()
        return True, "Odds padrão geradas com sucesso para a partida."
    except Exception as e:
        conn.rollback()
        return False, f"Erro ao gerar odds: {e}"
    finally:
        conn.close()


# --- Páginas do Painel de Administrador (com manage_odds_page implementada) ---

def dashboard_page():
    st.header("📊 Dashboard do Administrador")
    st.write("Visão geral do estado atual da plataforma.")
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Total de Usuários", len(get_all_users()))
    with col2: st.metric("Total de Partidas", len(get_upcoming_matches()) + len(get_match_history()))
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
        team1_name = st.selectbox("Time da Casa", options=list(team_dict.keys()), index=0)
        team2_name = st.selectbox("Time Visitante", options=list(team_dict.keys()), index=1)
        match_date = st.date_input("Data da Partida", min_value=datetime.date.today())
        match_time = st.time_input("Hora da Partida")
        submitted = st.form_submit_button("Adicionar Partida")
        if submitted:
            if team1_name == team2_name: st.error("Os times não podem ser os mesmos.")
            else:
                if add_match(team_dict[team1_name], team_dict[team2_name], match_date.strftime("%Y-%m-%d"), match_time.strftime("%H:%M")):
                    st.success(f"Partida '{team1_name} vs {team2_name}' adicionada!")
                    st.rerun()
    st.divider()
    st.subheader("Partidas Futuras")
    upcoming_matches = get_upcoming_matches()
    if upcoming_matches: st.dataframe(pd.DataFrame(upcoming_matches), use_container_width=True)
    else: st.info("Nenhuma partida futura cadastrada.")

# --- PÁGINA DE GERENCIAR ODDS IMPLEMENTADA ---
def manage_odds_page():
    st.header("🎯 Gerenciar Odds")

    upcoming_matches = get_upcoming_matches()
    if not upcoming_matches:
        st.warning("Nenhuma partida futura disponível para gerenciar odds.")
        return

    # 1. Selecionar a partida
    match_dict = {f"ID {m['id']}: {get_team_name(m['team1_id'])} vs {get_team_name(m['team2_id'])}": m['id'] for m in upcoming_matches}
    selected_match_str = st.selectbox("Selecione uma partida para gerenciar as odds", options=list(match_dict.keys()))
    
    if not selected_match_str:
        return
        
    match_id = match_dict[selected_match_str]
    
    # 2. Visualizar e gerenciar as odds da partida selecionada
    match_odds = get_match_odds(match_id)

    if not match_odds:
        st.info("Nenhuma odd encontrada para esta partida.")
        if st.button("Gerar Odds Padrão"):
            success, message = generate_default_odds_for_match(match_id)
            if success:
                st.success(message)
            else:
                st.error(message)
            st.rerun()
    else:
        st.subheader(f"Odds para: {selected_match_str}")
        df_odds = pd.DataFrame(match_odds)
        
        # Agrupar por categoria para melhor visualização
        categories = df_odds['category_name'].unique()
        for category in categories:
            with st.expander(f"**Categoria: {category}**", expanded=True):
                category_odds = df_odds[df_odds['category_name'] == category]
                for _, odd in category_odds.iterrows():
                    odd_id = odd['id']
                    odd_name = odd['template_name']
                    odd_value = odd['odds_value']
                    
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"{odd_name}")
                    with col2:
                        st.metric(label="Valor Atual", value=f"{odd_value:.2f}", label_visibility="collapsed")
                    with col3:
                        if st.button("📝 Editar", key=f"edit_{odd_id}"):
                            st.session_state[f'edit_mode_{odd_id}'] = not st.session_state.get(f'edit_mode_{odd_id}', False)

                    # Formulário de edição que aparece ao clicar no botão
                    if st.session_state.get(f'edit_mode_{odd_id}'):
                        with st.form(f"form_edit_{odd_id}", border=True):
                            st.write(f"Editando: **{odd_name}**")
                            new_odd_value = st.number_input("Novo Valor da Odd", value=odd_value, min_value=1.01, step=0.01, format="%.2f")
                            reason = st.text_input("Motivo da Alteração (obrigatório)", placeholder="Ex: Lesão de jogador chave")
                            
                            submitted = st.form_submit_button("Salvar Alteração")
                            if submitted:
                                success, message = update_match_odd(odd_id, new_odd_value, st.session_state['username'], reason)
                                if success:
                                    st.success(message)
                                    st.session_state[f'edit_mode_{odd_id}'] = False # Fecha o formulário
                                    st.rerun()
                                else:
                                    st.error(message)
                        
                        # Mostrar histórico da odd
                        history = get_odd_history(odd_id)
                        if history:
                            with st.container():
                                st.write("📜 **Histórico de Alterações:**")
                                for record in history:
                                    st.caption(f"{record['changed_at']}: {record['old_value']} → {record['new_value']} por '{record['changed_by']}'. Motivo: {record['reason']}")


def manage_custom_bets_page():
    st.header("🎲 Gerenciar Apostas Personalizadas")
    st.subheader("Criar Nova Aposta Personalizada")
    upcoming_matches = get_upcoming_matches()
    if not upcoming_matches:
        st.warning("Nenhuma partida futura disponível.")
    else:
        match_dict = {f"ID {m['id']}: {get_team_name(m['team1_id'])} vs {get_team_name(m['team2_id'])}": m['id'] for m in upcoming_matches}
        with st.form("create_custom_bet_form", clear_on_submit=True):
            selected_match_str = st.selectbox("Selecione a Partida", options=list(match_dict.keys()))
            description = st.text_input("Descrição da Aposta")
            odds = st.number_input("Odds", min_value=1.01, value=2.0, step=0.1)
            if st.form_submit_button("Criar Aposta"):
                if not description: st.error("A descrição não pode ser vazia.")
                else:
                    if add_custom_bet(match_dict[selected_match_str], description, odds):
                        st.success("Aposta personalizada criada!"); st.rerun()
    st.divider()
    st.subheader("Apostas Personalizadas Ativas")
    active_bets = get_active_custom_bets()
    if not active_bets: st.info("Nenhuma aposta personalizada ativa.")
    else:
        for bet in active_bets:
            with st.container(border=True):
                st.write(f"**ID:** {bet['id']} | **Partida ID:** {bet['match_id']} | **Descrição:** {bet['description']} | **Odds:** {bet['odds']}")
                col1, col2 = st.columns(2)
                if col1.button("✔️ GANHA", key=f"win_{bet['id']}", use_container_width=True):
                    if resolve_custom_bet(bet['id'], 'won'): st.success(f"Aposta {bet['id']} resolvida."); st.rerun()
                if col2.button("❌ PERDIDA", key=f"lose_{bet['id']}", use_container_width=True):
                    if resolve_custom_bet(bet['id'], 'lost'): st.warning(f"Aposta {bet['id']} resolvida."); st.rerun()

def manage_proposals_page():
    st.header("💡 Propostas de Usuários")
    proposals = get_custom_bet_proposals("pending")
    if not proposals: st.info("Nenhuma proposta pendente.")
    else:
        for idx, proposal in enumerate(proposals):
            with st.container(border=True):
                st.write(f"**De:** {proposal['username']} | **Partida ID:** {proposal['match_id']} | **Descrição:** {proposal['description']} | **Odd Proposta:** {proposal['proposed_odds']}")
                with st.form(f"review_proposal_{idx}"):
                    final_odds = st.number_input("Odd Final", value=proposal['proposed_odds'], min_value=1.01, step=0.1)
                    col1, col2 = st.columns(2)
                    if col1.form_submit_button("Aprovar", use_container_width=True): st.success(f"Proposta {proposal['id']} aprovada."); st.rerun()
                    if col2.form_submit_button("Rejeitar", type="secondary", use_container_width=True): st.warning(f"Proposta {proposal['id']} rejeitada."); st.rerun()

def manage_users_page():
    st.header("👥 Gerenciar Usuários")
    users = get_all_users()
    if users: st.dataframe(pd.DataFrame(users), use_container_width=True)
    else: st.info("Nenhum usuário encontrado.")

def manage_teams_players_page():
    st.header("🏆 Gerenciar Times")
    st.subheader("Adicionar Novo Time")
    with st.form("add_team_form", clear_on_submit=True):
        new_team_name = st.text_input("Nome do Novo Time")
        if st.form_submit_button("Adicionar Time"):
            success, message = add_team(new_team_name)
            if success: st.success(message); st.rerun()
            else: st.error(message)
    st.divider()
    st.subheader("Times Existentes")
    teams = get_all_teams()
    if not teams: st.info("Nenhum time cadastrado.")
    else:
        for team in teams:
            team_id = team['id']
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    with st.form(f"edit_team_{team_id}"):
                        new_name = st.text_input("Editar nome", value=team['name'], label_visibility="collapsed")
                        if st.form_submit_button("Salvar"):
                            if new_name != team['name']:
                                success, message = update_team_name(team_id, new_name)
                                if success: st.success(message); st.rerun()
                                else: st.error(message)
                with col2:
                    if st.button("🗑️ Deletar", key=f"delete_{team_id}", use_container_width=True):
                        st.session_state[f'confirm_delete_{team_id}'] = True
                if st.session_state.get(f'confirm_delete_{team_id}'):
                    st.warning(f"**Atenção:** Deletar o time '{team['name']}'?")
                    c1, c2, c3 = st.columns([1, 1, 2])
                    if c1.button("Sim", key=f"confirm_yes_{team_id}", type="primary"):
                        success, message = delete_team(team_id)
                        if success: st.success(message)
                        else: st.error(message)
                        del st.session_state[f'confirm_delete_{team_id}']
                        st.rerun()
                    if c2.button("Não", key=f"confirm_no_{team_id}"):
                        del st.session_state[f'confirm_delete_{team_id}']
                        st.rerun()
    st.divider()
    st.header("Jogadores")
    st.info("O gerenciamento de jogadores será implementado aqui.")

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
