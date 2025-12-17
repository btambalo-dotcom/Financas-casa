from app.db.session import db

def count_safe(model):
    try:
        return db.session.query(model).count()
    except Exception:
        db.session.rollback()
        return "erro"
    finally:
        db.session.remove()
