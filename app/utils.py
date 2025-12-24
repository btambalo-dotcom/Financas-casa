from datetime import date, datetime
from functools import wraps
from flask import session, redirect, url_for, flash, request

def month_now() -> str:
    return datetime.now().strftime("%Y-%m")

def month_first_day(ym: str) -> date:
    y, m = ym.split("-")
    return date(int(y), int(m), 1)

def next_month_first_day(ym: str) -> date:
    y, m = map(int, ym.split("-"))
    if m == 12:
        return date(y + 1, 1, 1)
    return date(y, m + 1, 1)

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("bp.login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("bp.login", next=request.path))
        if session.get("role") != "admin":
            flash("Acesso restrito ao administrador.", "danger")
            return redirect(url_for("bp.dashboard"))
        return fn(*args, **kwargs)
    return wrapper

def format_currency(value):
    """Formata números como moeda brasileira (R$ 1.234,56).

    Usado como filtro Jinja: {{ valor|currency }}.
    Funciona mesmo se o valor vier como None ou string vazia.
    """
    try:
        if value is None:
            value = 0
        value = float(value)
    except (TypeError, ValueError):
        return "R$ 0,00"
    # Usa separador de milhar com ponto e decimal com vírgula
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {formatted}"
