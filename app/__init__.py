import os
from flask import Flask
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.environ.get("SECRET_KEY", "dev")

    from app.routes import bp
    app.register_blueprint(bp)

    scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")
    scheduler.add_job(
        func=_run_agent,
        trigger="interval",
        hours=1,
        id="ical_check"
    )
    scheduler.start()

    return app

def _run_agent():
    try:
        from agent.ical_agent import verificar_feeds
        verificar_feeds()
    except Exception as e:
        print(f"[Scheduler] Erro: {e}")
