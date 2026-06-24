import os
from datetime import timedelta
from flask import Flask
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-mude")
    app.permanent_session_lifetime = timedelta(days=30)

    from app.routes import bp
    from app.auth import auth_bp
    app.register_blueprint(bp)
    app.register_blueprint(auth_bp)

    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(func=_run_email_monitor, trigger="interval", minutes=5, id="email_check")
    scheduler.add_job(func=_run_agent, trigger="interval", hours=6, id="ical_check")
    scheduler.start()
    print("[Scheduler] Iniciado com sucesso")

    return app

def _run_agent():
    try:
        from agent.ical_agent import verificar_feeds
        verificar_feeds()
    except Exception as e:
        print(f"[Scheduler] Erro iCal: {e}")

def _run_email_monitor():
    try:
        from agent.email_monitor import verificar_emails_novos
        verificar_emails_novos()
    except Exception as e:
        print(f"[Scheduler] Erro email: {e}")
