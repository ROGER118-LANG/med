from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import requests
import json
from datetime import datetime
import uuid
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'sua-chave-secreta-aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///survey_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# Modelos do Banco de Dados
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    surveys = db.relationship('Survey', backref='company', lazy=True)


class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    public_id = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    questions = db.relationship('Question', backref='survey', lazy=True, cascade='all, delete-orphan')
    responses = db.relationship('Response', backref='survey', lazy=True, cascade='all, delete-orphan')


class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    question_type = db.Column(db.String(50), default='text')  # text, multiple_choice, rating
    options = db.Column(db.Text)  # JSON string para opções múltiplas
    importance = db.Column(db.Integer, default=1)  # 1-5 scale
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        """Converte o objeto Question para dicionário"""
        return {
            'id': self.id,
            'text': self.text,
            'question_type': self.question_type,
            'options': self.options,
            'importance': self.importance,
            'order': self.order
        }


class Response(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    respondent_id = db.Column(db.String(36), default=lambda: str(uuid.uuid4()))
    responses_data = db.Column(db.Text, nullable=False)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ai_analysis = db.Column(db.Text)  # Análise individual da resposta


class AIAnalysis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    survey_id = db.Column(db.Integer, db.ForeignKey('survey.id'), nullable=False)
    analysis_data = db.Column(db.Text, nullable=False)  # JSON string
    analysis_type = db.Column(db.String(50), default='general')  # general, individual
    response_id = db.Column(db.Integer, db.ForeignKey('response.id'), nullable=True)  # Para análises individuais
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# OpenAI API Configuration
OPENAI_API_KEY = "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"


def safe_json_serialize(obj):
    """Função auxiliar para serialização segura de objetos"""
    if hasattr(obj, 'to_dict'):
        return obj.to_dict()
    elif hasattr(obj, '__dict__'):
        # Para objetos SQLAlchemy sem to_dict
        return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    else:
        return str(obj)


def analyze_with_openai(survey_data, responses_data, analysis_type='general'):
    """Analisa respostas usando OpenAI API"""
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }

        # Garantir que os dados são serializáveis
        try:
            responses_json = json.dumps(responses_data, indent=2, ensure_ascii=False, default=safe_json_serialize)
        except Exception as e:
            print(f"Erro na serialização: {e}")
            responses_json = str(responses_data)

        if analysis_type == 'general':
            # Análise geral de todas as respostas
            prompt = f"""
            Analise as seguintes respostas de pesquisa e forneça insights detalhados de forma limpa e organizada:

            **Pesquisa:** {survey_data['title']}
            **Descrição:** {survey_data['description']}
            **Total de Respostas:** {len(responses_data) if isinstance(responses_data, list) else 1}

            **Dados das respostas:**
            {responses_json}

            Por favor, forneça uma análise estruturada com:

            **1. RESUMO GERAL**
            - Visão geral dos resultados principais

            **2. TENDÊNCIAS IDENTIFICADAS**
            - Padrões encontrados nas respostas
            - Comportamentos recorrentes

            **3. PONTOS DE ATENÇÃO**
            - Problemas ou preocupações identificadas
            - Áreas que necessitam atenção

            **4. RECOMENDAÇÕES**
            - Ações sugeridas baseadas nos dados
            - Próximos passos recomendados

            **5. ANÁLISE DE SENTIMENTO**
            - Sentimento geral dos respondentes
            - Nível de satisfação percebido

            Responda em formato HTML limpo e bem estruturado, sem usar aspas ou caracteres de escape.
            Use tags HTML como <h4>, <p>, <ul>, <li>, <strong> para uma apresentação clara.
            """
        else:
            # Análise individual de uma resposta específica
            prompt = f"""
            Analise esta resposta individual de pesquisa e forneça insights detalhados:

            **Pesquisa:** {survey_data['title']}
            **Resposta Individual:**
            {responses_json}

            Por favor, forneça uma análise individual estruturada com:

            **1. PERFIL DO RESPONDENTE**
            - Características identificadas nas respostas

            **2. ANÁLISE DETALHADA**
            - Avaliação de cada resposta fornecida
            - Coerência e qualidade das respostas

            **3. INSIGHTS ESPECÍFICOS**
            - Pontos únicos desta resposta
            - Diferenciadores em relação ao padrão geral

            **4. RECOMENDAÇÕES PERSONALIZADAS**
            - Ações específicas baseadas nesta resposta
            - Áreas de foco para este respondente

            Responda em formato HTML limpo e bem estruturado, sem usar aspas ou caracteres de escape.
            Use tags HTML como <h4>, <p>, <ul>, <li>, <strong> para uma apresentação clara.
            """

        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data
        )

        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"<p>Erro na análise: {response.status_code}</p>"

    except Exception as e:
        return f"<p>Erro ao conectar com OpenAI: {str(e)}</p>"


# Rotas da aplicação
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        # Verifica se email já existe
        if Company.query.filter_by(email=email).first():
            flash('Email já cadastrado!', 'error')
            return render_template('register.html')

        # Cria nova empresa
        company = Company(
            name=name,
            email=email,
            password_hash=generate_password_hash(password)
        )
        db.session.add(company)
        db.session.commit()

        flash('Cadastro realizado com sucesso!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        company = Company.query.filter_by(email=email).first()

        if company and check_password_hash(company.password_hash, password):
            session['company_id'] = company.id
            session['company_name'] = company.name
            return redirect(url_for('dashboard'))
        else:
            flash('Email ou senha inválidos!', 'error')

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/dashboard')
def dashboard():
    if 'company_id' not in session:
        return redirect(url_for('login'))

    company_id = session['company_id']
    surveys = Survey.query.filter_by(company_id=company_id).all()

    # Estatísticas gerais
    total_surveys = len(surveys)
    total_responses = sum([len(survey.responses) for survey in surveys])

    return render_template('dashboard.html',
                           surveys=surveys,
                           total_surveys=total_surveys,
                           total_responses=total_responses)


@app.route('/survey/new', methods=['GET', 'POST'])
def new_survey():
    if 'company_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']

        survey = Survey(
            title=title,
            description=description,
            company_id=session['company_id']
        )
        db.session.add(survey)
        db.session.commit()

        flash('Pesquisa criada com sucesso!', 'success')
        return redirect(url_for('edit_survey', survey_id=survey.id))

    return render_template('new_survey.html')


@app.route('/survey/<int:survey_id>/edit')
def edit_survey(survey_id):
    if 'company_id' not in session:
        return redirect(url_for('login'))

    survey = Survey.query.filter_by(id=survey_id, company_id=session['company_id']).first_or_404()
    questions = Question.query.filter_by(survey_id=survey_id).order_by(Question.order).all()

    return render_template('edit_survey.html', survey=survey, questions=questions)


@app.route('/survey/<int:survey_id>/add_question', methods=['POST'])
def add_question(survey_id):
    if 'company_id' not in session:
        return redirect(url_for('login'))

    survey = Survey.query.filter_by(id=survey_id, company_id=session['company_id']).first_or_404()

    text = request.form['text']
    question_type = request.form['question_type']
    importance = int(request.form['importance'])
    options = request.form.get('options', '')

    # Conta questões existentes para ordem
    question_count = Question.query.filter_by(survey_id=survey_id).count()

    question = Question(
        survey_id=survey_id,
        text=text,
        question_type=question_type,
        options=options,
        importance=importance,
        order=question_count + 1
    )
    db.session.add(question)
    db.session.commit()

    return redirect(url_for('edit_survey', survey_id=survey_id))


@app.route('/survey/<public_id>')
def public_survey(public_id):
    survey = Survey.query.filter_by(public_id=public_id, is_active=True).first_or_404()
    questions = Question.query.filter_by(survey_id=survey.id).order_by(Question.order).all()

    return render_template('public_survey.html', survey=survey, questions=questions)


@app.route('/survey/<public_id>/submit', methods=['POST'])
def submit_survey(public_id):
    survey = Survey.query.filter_by(public_id=public_id, is_active=True).first_or_404()

    # Coleta respostas
    responses_data = {}
    for key, value in request.form.items():
        if key.startswith('question_'):
            question_id = key.replace('question_', '')
            responses_data[question_id] = value

    # Salva resposta
    response = Response(
        survey_id=survey.id,
        responses_data=json.dumps(responses_data)
    )
    db.session.add(response)
    db.session.commit()

    # Gera análise individual da resposta
    generate_individual_analysis(response.id)

    # Trigger análise geral (async would be better in production)
    update_general_analysis(survey.id)

    return render_template('survey_submitted.html', survey=survey)


@app.route('/survey/<int:survey_id>/analytics')
def survey_analytics(survey_id):
    if 'company_id' not in session:
        return redirect(url_for('login'))

    survey = Survey.query.filter_by(id=survey_id, company_id=session['company_id']).first_or_404()
    responses = Response.query.filter_by(survey_id=survey_id).all()
    questions = Question.query.filter_by(survey_id=survey_id).all()

    # Busca análise geral mais recente
    general_analysis = AIAnalysis.query.filter_by(
        survey_id=survey_id,
        analysis_type='general'
    ).order_by(AIAnalysis.updated_at.desc()).first()

    return render_template('analytics.html',
                           survey=survey,
                           responses=responses,
                           questions=questions,
                           ai_analysis=general_analysis)


@app.route('/api/survey/<int:survey_id>/data')
def api_survey_data(survey_id):
    if 'company_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    survey = Survey.query.filter_by(id=survey_id, company_id=session['company_id']).first_or_404()
    responses = Response.query.filter_by(survey_id=survey_id).all()
    questions = Question.query.filter_by(survey_id=survey_id).all()

    # Processa dados para gráficos
    chart_data = {
        'total_responses': len(responses),
        'responses_over_time': [],
        'question_analytics': {}
    }

    # Dados por data
    date_counts = {}
    for response in responses:
        date_key = response.created_at.strftime('%Y-%m-%d')
        date_counts[date_key] = date_counts.get(date_key, 0) + 1

    chart_data['responses_over_time'] = [
        {'date': date, 'count': count}
        for date, count in sorted(date_counts.items())
    ]

    return jsonify(chart_data)


# Nova rota para análise individual de resposta
@app.route('/api/response/<int:response_id>/analysis')
def api_individual_analysis(response_id):
    if 'company_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    response = Response.query.get_or_404(response_id)
    survey = Survey.query.get(response.survey_id)

    # Verifica se a empresa tem acesso a esta pesquisa
    if survey.company_id != session['company_id']:
        return jsonify({'error': 'Unauthorized'}), 401

    # Busca análise individual existente
    individual_analysis = AIAnalysis.query.filter_by(
        response_id=response_id,
        analysis_type='individual'
    ).first()

    if not individual_analysis:
        # Gera análise se não existir
        generate_individual_analysis(response_id)
        individual_analysis = AIAnalysis.query.filter_by(
            response_id=response_id,
            analysis_type='individual'
        ).first()

    return jsonify({
        'analysis': individual_analysis.analysis_data if individual_analysis else 'Análise não disponível',
        'response_data': json.loads(response.responses_data),
        'created_at': response.created_at.strftime('%d/%m/%Y %H:%M')
    })


# Nova rota para forçar atualização da análise geral
@app.route('/api/survey/<int:survey_id>/refresh-analysis', methods=['POST'])
def refresh_general_analysis(survey_id):
    if 'company_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    survey = Survey.query.filter_by(id=survey_id, company_id=session['company_id']).first_or_404()

    # Força atualização da análise geral
    update_general_analysis(survey_id)

    return jsonify({'status': 'success', 'message': 'Análise atualizada com sucesso!'})


def generate_individual_analysis(response_id):
    """Gera análise individual para uma resposta específica"""
    try:
        print(f"Iniciando análise individual para response_id: {response_id}")

        response = Response.query.get(response_id)
        if not response:
            print("Response não encontrado")
            return

        survey = Survey.query.get(response.survey_id)
        questions = Question.query.filter_by(survey_id=survey.id).all()

        print(f"Survey: {survey.title}, Questions: {len(questions)}")

        # Prepara dados para análise individual - CORRIGIDO
        survey_data = {
            'title': survey.title,
            'description': survey.description,
            'questions': [{'id': q.id, 'text': q.text, 'importance': q.importance} for q in questions]
        }

        print("Survey_data preparado com sucesso")

        response_data = json.loads(response.responses_data)
        print(f"Response_data carregado: {response_data}")

        # Mapeia respostas com perguntas
        mapped_responses = {}
        for question_key, answer in response_data.items():
            question_id = question_key.replace('question_', '')
            question = next((q for q in questions if str(q.id) == question_id), None)
            if question:
                mapped_responses[question.text] = answer

        print(f"Mapped responses: {mapped_responses}")

        # Chama OpenAI para análise individual
        print("Chamando OpenAI para análise...")
        analysis_result = analyze_with_openai(survey_data, mapped_responses, 'individual')
        print("Análise OpenAI concluída")

        # Salva análise individual
        individual_analysis = AIAnalysis(
            survey_id=survey.id,
            response_id=response_id,
            analysis_data=analysis_result,
            analysis_type='individual'
        )
        db.session.add(individual_analysis)
        db.session.commit()
        print("Análise individual salva com sucesso")

    except Exception as e:
        print(f"Erro ao gerar análise individual: {str(e)}")
        import traceback
        traceback.print_exc()


def update_general_analysis(survey_id):
    """Atualiza análise geral para uma pesquisa"""
    try:
        print(f"Iniciando análise geral para survey_id: {survey_id}")

        survey = Survey.query.get(survey_id)
        if not survey:
            print("Survey não encontrado")
            return

        responses = Response.query.filter_by(survey_id=survey_id).all()
        questions = Question.query.filter_by(survey_id=survey_id).all()

        if not responses:
            print("Nenhuma resposta encontrada")
            return

        print(f"Survey: {survey.title}, Responses: {len(responses)}, Questions: {len(questions)}")

        # Prepara dados para análise geral - CORRIGIDO
        survey_data = {
            'title': survey.title,
            'description': survey.description,
            'questions': [{'text': q.text, 'importance': q.importance} for q in questions]  # Convertido manualmente
        }

        print("Survey_data preparado com sucesso")

        responses_data = []
        for response in responses:
            try:
                response_dict = json.loads(response.responses_data)
                # Mapeia respostas com perguntas
                mapped_response = {}
                for question_key, answer in response_dict.items():
                    question_id = question_key.replace('question_', '')
                    question = next((q for q in questions if str(q.id) == question_id), None)
                    if question:
                        mapped_response[question.text] = answer

                responses_data.append({
                    'id': response.id,
                    'date': response.created_at.isoformat(),
                    'answers': mapped_response
                })
            except Exception as e:
                print(f"Erro ao processar resposta {response.id}: {str(e)}")
                continue

        print(f"Responses_data preparado: {len(responses_data)} respostas processadas")

        # Chama OpenAI para análise geral
        print("Chamando OpenAI para análise geral...")
        analysis_result = analyze_with_openai(survey_data, responses_data, 'general')
        print("Análise OpenAI concluída")

        # Salva ou atualiza análise geral
        existing_analysis = AIAnalysis.query.filter_by(
            survey_id=survey_id,
            analysis_type='general'
        ).first()

        if existing_analysis:
            existing_analysis.analysis_data = analysis_result
            existing_analysis.updated_at = datetime.utcnow()
            print("Análise geral atualizada")
        else:
            new_analysis = AIAnalysis(
                survey_id=survey_id,
                analysis_data=analysis_result,
                analysis_type='general'
            )
            db.session.add(new_analysis)
            print("Nova análise geral criada")

        db.session.commit()
        print("Análise geral salva com sucesso")

    except Exception as e:
        print(f"Erro ao atualizar análise geral: {str(e)}")
        import traceback
        traceback.print_exc()


# Inicialização
app.jinja_env.auto_reload = False
app.config['TEMPLATES_AUTO_RELOAD'] = False

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Cria as tabelas antes de rodar o servidor
    app.run(debug=True, host='0.0.0.0', port=5000)
