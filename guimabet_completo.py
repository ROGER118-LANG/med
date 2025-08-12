# app.py
import streamlit as st
import sqlite3
import pandas as pd
import datetime
import hashlib

# Importa o painel de administração de um arquivo separado (opcional, mas bom para organização)
# Para simplificar, vamos colocar tudo em um só arquivo, como solicitado.

# ==============================================================================
# FUNÇÕES DE BANCO DE DADOS (DB)
# ==============================================================================

def db_connect():
    """Cria e retorna uma conexão com o banco de dados com row_factory."""
    conn = sqlite3.connect('guimabet.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_user(username, password):
    """Valida o login do usuário comparando a senha criptografada."""
    conn = db_connect()
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    user = conn.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, hashed_password)).fetchone()
    conn.close()
    return user

def register_user(username, password):
    """Registra um novo usuário com senha criptografada."""
    if not username or not password:
        return False, "Usuário e senha não podem ser vazios."
    conn = db_connect()
    try:
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        conn.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_password))
        conn.commit()
        return True, "Conta criada com sucesso! Faça o login."
    except sqlite3.IntegrityError:
        return False, "Este nome de usuário já existe."
    finally:
        conn.close()

def get_user_points(username):
    """Busca os pontos de um usuário."""
    conn = db_connect()
    points = conn.execute("SELECT points FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    return points['points'] if points else 0

def get_team_name(team_id):
    """Busca o nome de um time pelo ID."""
    conn = db_connect()
    name = conn.execute("SELECT name FROM teams WHERE id = ?", (team_id,)).fetchone()
    conn.close()
    return name['name'] if name else "Desconhecido"

def get_upcoming_matches_with_names():
    """Busca partidas futuras com nomes dos times."""
    conn = db_connect()
    matches = [dict(row) for row in conn.execute("""
        SELECT m.id, m.date, m.time, t1.name as team1_name, t2.name as team2_name
        FROM matches m
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        WHERE m.status = 'upcoming' ORDER BY m.date, m.time
    """).fetchall()]
    conn.close()
    return matches

def get_match_odds(match_id):
    """Busca as odds de uma partida específica."""
    conn = db_connect()
    odds = [dict(row) for row in conn.execute("""
        SELECT mo.id, mo.odds_value, ot.name as template_name, ot.description
        FROM match_odds mo
        JOIN odds_templates ot ON mo.template_id = ot.id
        WHERE mo.match_id = ? AND mo.is_active = 1
    """, (match_id,)).fetchall()]
    conn.close()
    return odds

# Em app.py

def place_bet(username, match_id, match_odds_id, amount):
    """Registra uma aposta de um usuário de forma segura."""
    conn = db_connect()
    try:
        # Busca o registro completo do usuário
        user_row = conn.execute("SELECT points FROM users WHERE username = ?", (username,)).fetchone()
        
        # --- CORREÇÃO ADICIONADA AQUI ---
        # Verifica se o usuário foi encontrado antes de prosseguir
        if user_row is None:
            return False, "Erro: Usuário não encontrado no banco de dados."
            
        user_points = user_row['points']
        
        # Agora a verificação é segura, pois sabemos que user_points é um número
        if user_points < amount:
            return False, "Pontos insuficientes."
        
        odd_info = conn.execute("SELECT odds_value FROM match_odds WHERE id = ?", (match_odds_id,)).fetchone()
        if not odd_info:
            return False, "Odd não encontrada."
        
        # Deduz os pontos e insere a aposta
        conn.execute("UPDATE users SET points = points - ? WHERE username = ?", (amount, username))
        conn.execute("""
            INSERT INTO bets (user_id, match_id, amount, odds, match_odds_id, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (username, match_id, amount, odd_info['odds_value'], match_odds_id, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        
        conn.commit()
        return True, "Aposta realizada com sucesso!"
    except Exception as e:
        conn.rollback()
        # Fornece um erro mais detalhado para depuração
        return False, f"Erro interno ao realizar aposta: {e}"
    finally:
        conn.close()


def get_user_bets(username):
    """Busca o histórico de apostas de um usuário."""
    conn = db_connect()
    bets = [dict(row) for row in conn.execute("""
        SELECT 
            b.amount, b.odds, b.status, b.timestamp,
            m.date, t1.name as team1_name, t2.name as team2_name,
            ot.name as bet_name
        FROM bets b
        JOIN matches m ON b.match_id = m.id
        JOIN teams t1 ON m.team1_id = t1.id
        JOIN teams t2 ON m.team2_id = t2.id
        LEFT JOIN match_odds mo ON b.match_odds_id = mo.id
        LEFT JOIN odds_templates ot ON mo.template_id = ot.id
        WHERE b.user_id = ? ORDER BY b.timestamp DESC
    """, (username,)).fetchall()]
    conn.close()
    return bets

# ==============================================================================
# INTERFACE DO USUÁRIO (UI)
# ==============================================================================

def login_page():
    """Página de login e registro."""
    st.title("Bem-vindo ao GuimaBet!")
    tab1, tab2 = st.tabs(["Entrar", "Registrar"])
    
    with tab1:
        with st.form("login_form"):
            username = st.text_input("Usuário")
            password = st.text_input("Senha", type="password")
            if st.form_submit_button("Entrar"):
                user = login_user(username, password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.username = user['username']
                    st.session_state.is_admin = bool(user['is_admin'])
                    st.success("Login bem-sucedido!")
                    st.rerun()
                else:
                    st.error("Usuário ou senha inválidos.")
    
    with tab2:
        with st.form("register_form"):
            new_username = st.text_input("Escolha um nome de usuário")
            new_password = st.text_input("Crie uma senha", type="password")
            if st.form_submit_button("Registrar"):
                success, message = register_user(new_username, new_password)
                if success:
                    st.success(message)
                else:
                    st.error(message)

def main_dashboard():
    """Dashboard principal para usuários logados."""
    st.sidebar.title(f"Olá, {st.session_state.username}!")
    st.sidebar.metric("Seus Pontos", get_user_points(st.session_state.username))
    
    if st.sidebar.button("Logout"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    # Navegação principal
    pages = ["Apostar", "Minhas Apostas"]
    if st.session_state.is_admin:
        pages.append("Painel do Admin")
    
    selection = st.sidebar.radio("Navegação", pages)

    if selection == "Apostar":
        betting_page()
    elif selection == "Minhas Apostas":
        my_bets_page()
    elif selection == "Painel do Admin" and st.session_state.is_admin:
        # Aqui poderíamos chamar um módulo separado, mas por simplicidade, vamos definir aqui.
        # admin_panel() 
        st.title("Funcionalidade de Admin movida para o arquivo `admin_panel.py`")
        st.info("Para um projeto mais robusto, o ideal é separar o painel de admin em seu próprio arquivo.")


def betting_page():
    """Página para visualizar partidas e fazer apostas."""
    st.title("Partidas Disponíveis")
    matches = get_upcoming_matches_with_names()
    if not matches:
        st.info("Nenhuma partida futura disponível no momento.")
        return

    for match in matches:
        with st.expander(f"{match['team1_name']} vs {match['team2_name']} ({match['date']} {match['time']})"):
            odds = get_match_odds(match['id'])
            if not odds:
                st.write("Odds para esta partida ainda não foram definidas.")
                continue
            
            with st.form(f"bet_form_{match['id']}"):
                odds_dict = {f"{o['template_name']} ({o['odds_value']:.2f})": o['id'] for o in odds}
                selected_odd_str = st.selectbox("Escolha sua aposta:", options=list(odds_dict.keys()))
                amount = st.number_input("Valor da aposta (pontos)", min_value=1, step=1)
                
                if st.form_submit_button("Fazer Aposta"):
                    selected_odd_id = odds_dict[selected_odd_str]
                    success, message = place_bet(st.session_state.username, match['id'], selected_odd_id, amount)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

def my_bets_page():
    """Página para o usuário ver seu histórico de apostas."""
    st.title("Meu Histórico de Apostas")
    bets = get_user_bets(st.session_state.username)
    if not bets:
        st.info("Você ainda não fez nenhuma aposta.")
        return

    for bet in bets:
        status_color = {"pending": "grey", "won": "green", "lost": "red"}
        status_icon = {"pending": "⏳", "won": "✅", "lost": "❌"}
        
        with st.container(border=True):
            st.write(f"**{bet['team1_name']} vs {bet['team2_name']}**")
            st.write(f"Sua aposta: *{bet['bet_name']}*")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Apostado", f"{bet['amount']} pts")
            col2.metric("Odds", f"{bet['odds']:.2f}")
            
            status = bet['status']
            winnings = bet['amount'] * bet['odds']
            if status == 'won':
                col3.metric("Resultado", f"+{winnings:.0f} pts", delta_color="normal")
            elif status == 'lost':
                col3.metric("Resultado", f"-{bet['amount']} pts", delta_color="inverse")
            else:
                col3.metric("Ganhos Potenciais", f"{winnings:.0f} pts", delta_color="off")
            
            st.caption(f"Status: :{status_color.get(status, 'grey')}[{status.upper()}] {status_icon.get(status, '')} | Data: {bet['timestamp']}")

# ==============================================================================
# LÓGICA PRINCIPAL DA APLICAÇÃO
# ==============================================================================

def main():
    """Função principal que controla o fluxo da aplicação."""
    # Inicializa o estado da sessão
    if 'logged_in' not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.is_admin = False

    # Controla qual página é exibida
    if not st.session_state.logged_in:
        login_page()
    else:
        main_dashboard()

if __name__ == "__main__":
    # Uma verificação para garantir que o DB existe antes de rodar o app.
    try:
        with open('guimabet.db', 'r') as f:
            pass
    except FileNotFoundError:
        st.error("Banco de dados 'guimabet.db' não encontrado!")
        st.info("Por favor, rode o script 'guimabet_database.py' primeiro para criar o banco de dados.")
        st.stop()
        
    main()
