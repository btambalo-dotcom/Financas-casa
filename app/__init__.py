from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path
import os

db = SQLAlchemy()

def _is_production():
    # Render sets several env vars; FLASK_ENV may also be "production"
    return (
        os.getenv("RENDER") is not None
        or os.getenv("RENDER_SERVICE_ID") is not None
        or os.getenv("FLASK_ENV", "").lower() == "production"
        or os.getenv("ENV", "").lower() == "production"
    )

def _normalize_database_url(url: str) -> str:
    # Render / older providers may use "postgres://", SQLAlchemy expects "postgresql://"
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url

def create_app():
    app = Flask(__name__)

    # SECRET_KEY: use env in production; fallback for local dev
    app.secret_key = os.getenv("SECRET_KEY", "change-me-local")

    base_dir = Path(__file__).resolve().parent.parent
    app.config["BASE_DIR"] = str(base_dir)

    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        db_url = _normalize_database_url(db_url)

    if _is_production():
        # In production (Render), NEVER allow SQLite (it will be wiped on redeploy/restart).
        if not db_url:
            raise RuntimeError(
                "DATABASE_URL não está configurada. No Render, crie/ligue um PostgreSQL e "
                "adicione a variável DATABASE_URL no Web Service."
            )
        if db_url.startswith("sqlite"):
            raise RuntimeError(
                "Banco está apontando para SQLite em produção (isso apaga dados no Render). "
                "Configure DATABASE_URL para PostgreSQL."
            )
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    else:
        # Local dev: if no DATABASE_URL, use SQLite in instance/ (persist on your machine)
        if not db_url:
            instance_dir = base_dir / "instance"
            instance_dir.mkdir(exist_ok=True)
            db_url = f"sqlite:///{(instance_dir / 'finance.db')}"
        app.config["SQLALCHEMY_DATABASE_URI"] = db_url

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Pasta temporária para exportações (PDF/Excel/CSV) - segura no Render
    app.config["EXPORT_FOLDER"] = os.environ.get("EXPORT_FOLDER", "/tmp/exports")
    os.makedirs(app.config["EXPORT_FOLDER"], exist_ok=True)

    # Mais estabilidade em Postgres no Render (evita quedas/EOF)
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_timeout": 30,
    }

    # Uploads (comprovantes)
    uploads = base_dir / "uploads"
    uploads.mkdir(exist_ok=True)
    app.config["UPLOAD_FOLDER"] = str(uploads)
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB

    # PWA
    app.config["PWA_NAME"] = "Finanças da Casa"

    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    # Create tables + seed defaults (safe with Postgres)
    with app.app_context():
        from .models import seed_if_empty
        db.create_all()
        seed_if_empty()

    return app
