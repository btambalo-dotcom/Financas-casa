from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from pathlib import Path

db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.secret_key = "change-me"  # troque em produção

    base_dir = Path(__file__).resolve().parent.parent
    app.config["BASE_DIR"] = str(base_dir)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{(base_dir / 'finance.db')}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    uploads = base_dir / "uploads"
    exports = base_dir / "exports"
    uploads.mkdir(exist_ok=True)
    exports.mkdir(exist_ok=True)

    app.config["UPLOAD_FOLDER"] = str(uploads)
    app.config["EXPORT_FOLDER"] = str(exports)
    app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024  # 20MB

    # PWA
    app.config["PWA_NAME"] = "Finanças da Casa"

    db.init_app(app)

    from .routes import bp
    app.register_blueprint(bp)

    with app.app_context():
        from .models import seed_if_empty
        db.create_all()
        seed_if_empty()

    return app