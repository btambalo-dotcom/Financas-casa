import os
from datetime import datetime, date
from pathlib import Path

from flask import Blueprint, render_template, request, redirect, url_for, flash, send_from_directory, session
from werkzeug.utils import secure_filename
from sqlalchemy import text

from . import db
from .models import Transaction, Budget, BudgetTemplate, RecurringTransaction, Category, Account, User
from .utils import month_now, month_first_day, next_month_first_day, login_required, admin_required
from .exporters import export_csv, export_xlsx_professional, export_pdf_professional
from .importers import parse_bank_csv, coerce_date, coerce_float

bp = Blueprint("bp", __name__)

def ensure_recurring_for_month(ym: str):
    """Gera lançamentos recorrentes (uma vez por mês)"""
    items = RecurringTransaction.query.filter_by(is_active=True).all()
    if not items:
        return
    # datas do mês
    y, m = map(int, ym.split("-"))
    last_day = __import__("calendar").monthrange(y, m)[1]
    for r in items:
        if r.last_generated_month == ym:
            continue
        day = max(1, min(int(r.day_of_month or 1), last_day))
        d = date(y, m, day)
        # evita duplicar: procura por mesmo recorrente no mês
        exists = Transaction.query.filter_by(
            txn_type=r.txn_type,
            category_id=r.category_id,
            account_id=r.account_id,
            amount=r.amount,
            txn_date=d,
        ).filter(Transaction.description.like(f"%[REC:{r.id}]%")).first()
        if exists:
            r.last_generated_month = ym
            continue

        desc = (r.description or r.name or "").strip()
        tag = f"[REC:{r.id}]"
        if tag not in desc:
            desc = (desc + " " + tag).strip()

        db.session.add(Transaction(
            txn_type=r.txn_type,
            category_id=r.category_id,
            account_id=r.account_id,
            amount=float(r.amount),
            description=desc,
            txn_date=d,
            receipt_filename=""
        ))
        r.last_generated_month = ym
    db.session.commit()

def get_effective_budgets(ym: str):
    """Retorna dict category_name -> planned_amount (template + overrides do mês)."""
    planned = {}
    # templates
    templates = BudgetTemplate.query.all()
    for t in templates:
        planned[t.category.name] = float(t.planned_amount)
    # overrides (se existir para o mês)
    overrides = Budget.query.filter_by(month=ym).all()
    for o in overrides:
        planned[o.category.name] = float(o.planned_amount)
    return planned


# ---------------- AUTH ----------------
@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username","").strip()
        password = request.form.get("password","").strip()
        user = User.query.filter_by(username=username, is_active=True).first()
        if not user or not user.check_password(password):
            flash("Usuário ou senha inválidos.", "danger")
            return redirect(url_for("bp.login"))
        session["user_id"] = user.id
        session["username"] = user.username
        session["role"] = user.role
        flash(f"Bem-vindo, {user.name}!", "success")
        nxt = request.args.get("next") or url_for("bp.dashboard")
        return redirect(nxt)
    return render_template("login.html")

@bp.route("/logout")
def logout():
    session.clear()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("bp.login"))

@bp.route("/")
def root():
    if not session.get("user_id"):
        return redirect(url_for("bp.login"))
    return redirect(url_for("bp.dashboard"))

# ---------------- DASHBOARD ----------------
@bp.route("/dashboard")
@login_required
def dashboard():
    ym = request.args.get("month") or month_now()
    ensure_recurring_for_month(ym)
    start = month_first_day(ym)
    end = next_month_first_day(ym)

    txs = Transaction.query.filter(Transaction.txn_date >= start, Transaction.txn_date < end).all()
    spent = sum(t.amount for t in txs if t.txn_type == "expense")
    income = sum(t.amount for t in txs if t.txn_type == "income")

    effective = get_effective_budgets(ym)
    planned = sum(effective.values())
    budgets = Budget.query.filter_by(month=ym).all()

    spent_by_cat = {}
    for t in txs:
        if t.txn_type != "expense":
            continue
        spent_by_cat[t.category.name] = spent_by_cat.get(t.category.name, 0) + t.amount

    budget_rows = []
    for cat, plan in effective.items():
        s = spent_by_cat.get(cat, 0.0)
        budget_rows.append({"category": cat, "planned": plan, "spent": s, "remaining": plan - s})
    budget_rows.sort(key=lambda r: r["remaining"])

    recent = Transaction.query.order_by(Transaction.txn_date.desc(), Transaction.id.desc()).limit(10).all()

    return render_template(
        "dashboard.html",
        month=ym,
        planned=planned,
        spent=spent,
        income=income,
        balance=income - spent,
        budget_balance=planned - spent,
        budget_rows=budget_rows,
        recent=recent
    )

# ---------------- TRANSACTIONS ----------------
@bp.route("/transactions")
@login_required
def transactions_list():
    ym = request.args.get("month") or month_now()
    ensure_recurring_for_month(ym)
    start = month_first_day(ym)
    end = next_month_first_day(ym)
    txs = Transaction.query.filter(Transaction.txn_date >= start, Transaction.txn_date < end).order_by(Transaction.txn_date.desc(), Transaction.id.desc()).all()
    return render_template("transactions_list.html", month=ym, txs=txs)

@bp.route("/transactions/new", methods=["GET", "POST"])
@login_required
def transactions_new():
    if request.method == "POST":
        return _save_transaction()
    return _transaction_form()

@bp.route("/transactions/<int:tid>/edit", methods=["GET", "POST"])
@login_required
def transactions_edit(tid: int):
    t = Transaction.query.get_or_404(tid)
    if request.method == "POST":
        return _save_transaction(existing=t)
    return _transaction_form(existing=t)

@bp.route("/transactions/<int:tid>/delete", methods=["POST"])
@admin_required
def transactions_delete(tid: int):
    t = Transaction.query.get_or_404(tid)
    ym = t.txn_date.strftime("%Y-%m")
    db.session.delete(t)
    db.session.commit()
    flash("Lançamento removido.", "warning")
    return redirect(url_for("bp.transactions_list", month=ym))

def _transaction_form(existing=None):
    cats_income = Category.query.filter_by(kind="income", is_active=True).order_by(Category.name.asc()).all()
    cats_expense = Category.query.filter_by(kind="expense", is_active=True).order_by(Category.name.asc()).all()
    accounts = Account.query.filter_by(is_active=True).order_by(Account.name.asc()).all()
    return render_template("transactions_form.html", existing=existing, cats_income=cats_income, cats_expense=cats_expense, accounts=accounts)

def _save_transaction(existing=None):
    txn_type = request.form.get("txn_type", "expense")
    category_id = request.form.get("category_id")
    account_id = request.form.get("account_id")
    amount = request.form.get("amount", "").strip()
    description = request.form.get("description", "").strip()
    txn_date_str = request.form.get("txn_date", "").strip()

    if txn_type not in ("income", "expense"):
        flash("Tipo inválido.", "danger")
        return redirect(request.path)

    try:
        amount_f = float(amount)
    except ValueError:
        flash("Valor inválido.", "danger")
        return redirect(request.path)

    try:
        d = datetime.strptime(txn_date_str, "%Y-%m-%d").date() if txn_date_str else date.today()
    except ValueError:
        d = date.today()

    if not category_id or not account_id:
        flash("Selecione categoria e conta.", "danger")
        return redirect(request.path)

    receipt_filename = existing.receipt_filename if existing else ""
    f = request.files.get("receipt")
    if f and f.filename:
        safe = secure_filename(f.filename)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        receipt_filename = f"{ts}_{safe}"
        f.save(os.path.join(current_upload_dir(), receipt_filename))

    if existing:
        existing.txn_type = txn_type
        existing.category_id = int(category_id)
        existing.account_id = int(account_id)
        existing.amount = amount_f
        existing.description = description
        existing.txn_date = d
        existing.receipt_filename = receipt_filename
        flash("Lançamento atualizado.", "success")
    else:
        t = Transaction(
            txn_type=txn_type,
            category_id=int(category_id),
            account_id=int(account_id),
            amount=amount_f,
            description=description,
            txn_date=d,
            receipt_filename=receipt_filename
        )
        db.session.add(t)
        flash("Lançamento salvo.", "success")

    db.session.commit()
    return redirect(url_for("bp.transactions_list", month=d.strftime("%Y-%m")))

# ---------------- BUDGETS ----------------
@bp.route("/budgets", methods=["GET", "POST"])
@login_required
def budgets():
    ym = request.args.get("month") or month_now()

    if request.method == "POST":
        month = request.form.get("month", ym).strip()
        category_id = request.form.get("category_id")
        amount = request.form.get("planned_amount", "0").strip()
        scope = request.form.get("scope", "template").strip()  # template / month

        if not category_id:
            flash("Selecione a categoria.", "danger")
            return redirect(url_for("bp.budgets", month=month))
        try:
            planned = float(amount)
        except ValueError:
            flash("Valor inválido.", "danger")
            return redirect(url_for("bp.budgets", month=month))

        if scope == "month":
            existing = Budget.query.filter_by(month=month, category_id=int(category_id)).first()
            if existing:
                existing.planned_amount = planned
            else:
                db.session.add(Budget(month=month, category_id=int(category_id), planned_amount=planned))
            db.session.commit()
            flash("Orçamento salvo apenas para este mês.", "success")
        else:
            tmpl = BudgetTemplate.query.filter_by(category_id=int(category_id)).first()
            if tmpl:
                tmpl.planned_amount = planned
            else:
                db.session.add(BudgetTemplate(category_id=int(category_id), planned_amount=planned))
            db.session.commit()
            flash("Orçamento salvo como padrão (vale para todos os meses).", "success")

        return redirect(url_for("bp.budgets", month=month))

    # mostrar template + overrides do mês
    templates = BudgetTemplate.query.all()
    overrides = {b.category_id: b for b in Budget.query.filter_by(month=ym).all()}
    rows = []
    for t in sorted(templates, key=lambda x: x.category.name):
        ov = overrides.get(t.category_id)
        rows.append({
            "category_id": t.category_id,
            "category": t.category.name,
            "template_amount": float(t.planned_amount),
            "month_amount": float(ov.planned_amount) if ov else None,
            "effective_amount": float(ov.planned_amount) if ov else float(t.planned_amount),
            "has_override": bool(ov),
        })

    cats_expense = Category.query.filter_by(kind="expense", is_active=True).order_by(Category.name.asc()).all()
    return render_template("budgets.html", month=ym, rows=rows, cats_expense=cats_expense)

# ---------------- RECEIPTS ----------------
@bp.route("/receipts")
@login_required
def receipts():
    txs = Transaction.query.filter(Transaction.receipt_filename != "").order_by(Transaction.txn_date.desc()).limit(200).all()
    return render_template("receipts.html", txs=txs)

@bp.route("/uploads/<path:filename>")
@login_required
def uploads(filename):
    return send_from_directory(current_upload_dir(), filename, as_attachment=False)

def current_upload_dir():
    from flask import current_app
    return current_app.config["UPLOAD_FOLDER"]

# ---------------- REPORTS ----------------
@bp.route("/reports")
@login_required
def reports():
    ym = request.args.get("month") or month_now()
    start = month_first_day(ym)
    end = next_month_first_day(ym)
    txs = Transaction.query.filter(Transaction.txn_date >= start, Transaction.txn_date < end).all()

    by_cat = {}
    by_acc = {}
    for t in txs:
        key_c = f"{t.txn_type}:{t.category.name}"
        by_cat[key_c] = by_cat.get(key_c, 0) + t.amount
        key_a = f"{t.txn_type}:{t.account.name}"
        by_acc[key_a] = by_acc.get(key_a, 0) + t.amount

    # ordenar
    cat_rows = sorted([(k.split(":",1)[0], k.split(":",1)[1], v) for k,v in by_cat.items()], key=lambda x: (x[0], -x[2]))
    acc_rows = sorted([(k.split(":",1)[0], k.split(":",1)[1], v) for k,v in by_acc.items()], key=lambda x: (x[0], -x[2]))

    return render_template("reports.html", month=ym, cat_rows=cat_rows, acc_rows=acc_rows)

@bp.route("/reports/export/<fmt>")
@login_required
def reports_export(fmt: str):
    ym = request.args.get("month") or month_now()
    start = month_first_day(ym)
    end = next_month_first_day(ym)
    txs = Transaction.query.filter(Transaction.txn_date >= start, Transaction.txn_date < end).order_by(Transaction.txn_date.asc()).all()

    headers = ["Data", "Tipo", "Categoria", "Conta", "Descrição", "Valor", "Comprovante"]
    rows = []
    total_income = 0.0
    total_expense = 0.0
    for t in txs:
        sign = 1.0
        if t.txn_type == "expense":
            total_expense += t.amount
        else:
            total_income += t.amount
        rows.append([t.txn_date, t.txn_type, t.category.name, t.account.name, t.description, float(t.amount), t.receipt_filename])

    net = total_income - total_expense

    from flask import current_app
    export_dir = Path(current_app.config["EXPORT_FOLDER"])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    meta = {
        "Mês": ym,
        "Total receitas": f"${total_income:,.2f}",
        "Total despesas": f"${total_expense:,.2f}",
        "Saldo (líquido)": f"${net:,.2f}",
    }

    if fmt == "csv":
        out = export_dir / f"lancamentos_{ym}_{ts}.csv"
        export_csv(out, [[str(r[0]), r[1], r[2], r[3], r[4], f"{r[5]:.2f}", r[6]] for r in rows], headers)
        return send_from_directory(str(export_dir), out.name, as_attachment=True)

    if fmt == "xlsx":
        out = export_dir / f"lancamentos_{ym}_{ts}.xlsx"
        export_xlsx_professional(out, rows, headers, title=f"Lançamentos • {ym}", meta=meta)
        return send_from_directory(str(export_dir), out.name, as_attachment=True)

    if fmt == "pdf":
        out = export_dir / f"lancamentos_{ym}_{ts}.pdf"
        pdf_rows = []
        for r in rows:
            pdf_rows.append([
                r[0].strftime("%Y-%m-%d"),
                "Receita" if r[1]=="income" else "Despesa",
                r[2],
                r[3],
                (r[4] or "")[:35],
                f"${r[5]:,.2f}",
                ("Sim" if r[6] else "Não")
            ])
        export_pdf_professional(out, f"Lançamentos • {ym}", ["Data","Tipo","Categoria","Conta","Descrição","Valor","Comp."], pdf_rows, meta=meta)
        return send_from_directory(str(export_dir), out.name, as_attachment=True)

    flash("Formato inválido.", "danger")
    return redirect(url_for("bp.reports", month=ym))


# ---------------- IMPORT (CSV) ----------------
@bp.route("/import", methods=["GET", "POST"])
@admin_required
def import_csv():
    preview = []
    if request.method == "POST":
        f = request.files.get("file")
        if not f or not f.filename:
            flash("Selecione um arquivo CSV.", "danger")
            return redirect(url_for("bp.import_csv"))
        rows = parse_bank_csv(f.stream)
        preview = rows[:20]
        # modo "importar"
        if request.form.get("do_import") == "1":
            account_name = request.form.get("account_name","Conta Corrente").strip() or "Conta Corrente"
            account = Account.query.filter_by(name=account_name).first()
            if not account:
                account = Account(name=account_name, kind="checking", is_active=True)
                db.session.add(account)
                db.session.commit()

            # categoria fallback
            fallback_cat = Category.query.filter_by(name="Contas").first() or Category.query.filter_by(kind="expense").first()

            imported = 0
            for r in rows:
                d = coerce_date(r.get("date") or r.get("Date") or r.get("DATA"))
                desc = (r.get("description") or r.get("Description") or r.get("HISTORICO") or "").strip()
                amt = coerce_float(r.get("amount") or r.get("Amount") or r.get("VALOR"))
                typ = (r.get("type") or r.get("Type") or "").strip().lower()

                # se valor negativo, é despesa
                txn_type = "expense"
                if typ in ("income","receita"):
                    txn_type = "income"
                elif typ in ("expense","despesa"):
                    txn_type = "expense"
                else:
                    txn_type = "income" if amt > 0 else "expense"
                amt_abs = abs(amt)

                # categoria opcional
                cat_name = (r.get("category") or r.get("Category") or "").strip()
                cat = Category.query.filter_by(name=cat_name).first() if cat_name else None
                if not cat:
                    cat = fallback_cat

                db.session.add(Transaction(
                    txn_type=txn_type,
                    category_id=cat.id,
                    account_id=account.id,
                    amount=amt_abs,
                    description=desc,
                    txn_date=d,
                    receipt_filename=""
                ))
                imported += 1
            db.session.commit()
            flash(f"Importação concluída: {imported} registros.", "success")
            return redirect(url_for("bp.transactions_list", month=month_now()))

    return render_template("import.html", preview=preview)

# ---------------- SETTINGS ----------------
@bp.route("/settings")
@admin_required
def settings():
    cats = Category.query.order_by(Category.kind.asc(), Category.name.asc()).all()
    accs = Account.query.order_by(Account.name.asc()).all()
    users = User.query.order_by(User.role.desc(), User.username.asc()).all()
    recurring = RecurringTransaction.query.order_by(RecurringTransaction.id.desc()).all()
    cats_expense = Category.query.filter_by(kind="expense", is_active=True).order_by(Category.name.asc()).all()
    cats_income = Category.query.filter_by(kind="income", is_active=True).order_by(Category.name.asc()).all()
    return render_template("settings.html", cats=cats, accs=accs, users=users, recurring=recurring, cats_expense=cats_expense, cats_income=cats_income)

@bp.route("/settings/category", methods=["POST"])
@admin_required
def add_category():
    name = request.form.get("name","").strip()
    kind = request.form.get("kind","expense").strip()
    if not name or kind not in ("income","expense"):
        flash("Categoria inválida.", "danger")
        return redirect(url_for("bp.settings"))
    if Category.query.filter_by(name=name).first():
        flash("Categoria já existe.", "warning")
        return redirect(url_for("bp.settings"))
    db.session.add(Category(name=name, kind=kind, is_active=True))
    db.session.commit()
    flash("Categoria adicionada.", "success")
    return redirect(url_for("bp.settings"))

@bp.route("/settings/account", methods=["POST"])
@admin_required
def add_account():
    name = request.form.get("name","").strip()
    kind = request.form.get("kind","checking").strip()
    if not name:
        flash("Conta inválida.", "danger")
        return redirect(url_for("bp.settings"))
    if Account.query.filter_by(name=name).first():
        flash("Conta já existe.", "warning")
        return redirect(url_for("bp.settings"))
    db.session.add(Account(name=name, kind=kind, is_active=True))
    db.session.commit()
    flash("Conta adicionada.", "success")
    return redirect(url_for("bp.settings"))

@bp.route("/settings/user/password", methods=["POST"])
@admin_required
def set_user_password():
    uid = request.form.get("user_id")
    pw = request.form.get("new_password","").strip()
    if not uid or not pw or len(pw) < 4:
        flash("Senha inválida (mín. 4).", "danger")
        return redirect(url_for("bp.settings"))
    u = User.query.get_or_404(int(uid))
    u.set_password(pw)
    db.session.commit()
    flash(f"Senha atualizada para {u.username}.", "success")
    return redirect(url_for("bp.settings"))

@bp.route("/settings/user", methods=["POST"])
@admin_required
def add_user():
    name = request.form.get("name","").strip()
    username = request.form.get("username","").strip()
    password = request.form.get("password","").strip()
    role = request.form.get("role","user").strip()
    if not name or not username or not password:
        flash("Preencha nome, usuário e senha.", "danger")
        return redirect(url_for("bp.settings"))
    if role not in ("admin","user"):
        role = "user"
    if User.query.filter_by(username=username).first():
        flash("Usuário já existe.", "warning")
        return redirect(url_for("bp.settings"))
    u = User(name=name, username=username, role=role, is_active=True, password_hash="")
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    flash("Usuário criado.", "success")
    return redirect(url_for("bp.settings"))

@bp.route("/settings/user/<int:uid>/delete", methods=["POST"])
@admin_required
def delete_user(uid: int):
    u = User.query.get_or_404(uid)
    # não permitir deletar a si mesmo
    if session.get("user_id") == u.id:
        flash("Você não pode excluir o usuário logado.", "danger")
        return redirect(url_for("bp.settings"))
    # não permitir remover o último admin
    if u.role == "admin":
        admins = User.query.filter_by(role="admin", is_active=True).count()
        if admins <= 1:
            flash("Não é possível excluir o último administrador.", "danger")
            return redirect(url_for("bp.settings"))
    db.session.delete(u)
    db.session.commit()
    flash("Usuário excluído.", "warning")
    return redirect(url_for("bp.settings"))



# ---------------- DIAGNÓSTICO (ADMIN) ----------------
@bp.route("/admin/diagnostico")
@admin_required
def admin_diagnostico():
    """Página de diagnóstico para confirmar DB conectado e contagens.
    NÃO mostra senhas. Útil quando 'sumiu' dados ou após deploy.
    """
    info = {
        "db_url": None,
        "db_name": None,
        "db_user": None,
        "db_host": None,
        "db_driver": None,
        "tables": [],
        "errors": []
    }

    # URL do engine (sem senha)
    try:
        url_obj = db.engine.url
        # render_as_string existe no SQLAlchemy 1.4+/2.x
        try:
            info["db_url"] = url_obj.render_as_string(hide_password=True)
        except Exception:
            info["db_url"] = str(url_obj)
        info["db_name"] = getattr(url_obj, "database", None)
        info["db_user"] = getattr(url_obj, "username", None)
        info["db_host"] = getattr(url_obj, "host", None)
        info["db_driver"] = getattr(url_obj, "drivername", None)
    except Exception as e:
        info["errors"].append(f"Falha ao ler URL do banco: {e}")

    # Tabelas (Postgres: schema public)
    try:
        rows = db.session.execute(text(
            """SELECT table_name
                 FROM information_schema.tables
                 WHERE table_schema='public'
                 ORDER BY table_name"""
        )).fetchall()
        info["tables"] = [r[0] for r in rows]
    except Exception as e:
        # Fallback (SQLite)
        try:
            rows = db.session.execute(text(
                """SELECT name FROM sqlite_master
                     WHERE type='table'
                     ORDER BY name"""
            )).fetchall()
            info["tables"] = [r[0] for r in rows]
        except Exception as e2:
            info["errors"].append(f"Falha ao listar tabelas: {e} / {e2}")

    counts = {}
    try: counts["users_total"] = User.query.count()
    except Exception as e: info["errors"].append(f"users count: {e}")
    try: counts["transactions_total"] = Transaction.query.count()
    except Exception as e: info["errors"].append(f"transactions count: {e}")
    try: counts["budgets_total"] = Budget.query.count()
    except Exception as e: info["errors"].append(f"budgets count: {e}")
    try: counts["budget_templates_total"] = BudgetTemplate.query.count()
    except Exception as e: info["errors"].append(f"budget_templates count: {e}")
    try: counts["recurring_total"] = RecurringTransaction.query.count()
    except Exception as e: info["errors"].append(f"recurring count: {e}")
    try: counts["categories_total"] = Category.query.count()
    except Exception as e: info["errors"].append(f"categories count: {e}")
    try: counts["accounts_total"] = Account.query.count()
    except Exception as e: info["errors"].append(f"accounts count: {e}")

    # Datas e meses das transações
    stats = {"min_date": None, "max_date": None, "months": []}
    try:
        row = db.session.execute(text("SELECT MIN(txn_date), MAX(txn_date) FROM transactions")).fetchone()
        stats["min_date"], stats["max_date"] = row[0], row[1]
    except Exception as e:
        info["errors"].append(f"min/max txn_date: {e}")

    try:
        # Postgres
        rows = db.session.execute(text(
            """SELECT TO_CHAR(txn_date, 'YYYY-MM') AS ym, COUNT(*) 
                 FROM transactions
                 GROUP BY ym
                 ORDER BY ym DESC
                 LIMIT 24"""
        )).fetchall()
        stats["months"] = [{"month": r[0], "count": int(r[1])} for r in rows]
    except Exception:
        # SQLite fallback
        try:
            rows = db.session.execute(text(
                """SELECT substr(txn_date,1,7) AS ym, COUNT(*) 
                     FROM transactions
                     GROUP BY ym
                     ORDER BY ym DESC
                     LIMIT 24"""
            )).fetchall()
            stats["months"] = [{"month": r[0], "count": int(r[1])} for r in rows]
        except Exception as e2:
            info["errors"].append(f"months group: {e2}")

    last_txns = []
    try:
        last = Transaction.query.order_by(Transaction.id.desc()).limit(10).all()
        for t in last:
            last_txns.append({
                "id": t.id,
                "date": t.txn_date.isoformat() if t.txn_date else "",
                "type": t.txn_type,
                "amount": float(t.amount) if t.amount is not None else 0,
                "category": getattr(t.category, "name", "") if getattr(t, "category", None) else "",
                "account": getattr(t.account, "name", "") if getattr(t, "account", None) else "",
                "desc": (t.description or "")[:80]
            })
    except Exception as e:
        info["errors"].append(f"last transactions: {e}")

    return render_template(
        "admin_diagnostico.html",
        info=info,
        counts=counts,
        stats=stats,
        last_txns=last_txns
    )


# ---------------- RECURRING ----------------
@bp.route("/settings/recurring", methods=["POST"])
@admin_required
def add_recurring():
    name = request.form.get("name","").strip()
    amount = request.form.get("amount","").strip()
    day = request.form.get("day_of_month","1").strip()
    txn_type = request.form.get("txn_type","expense").strip()
    category_id = request.form.get("category_id")
    account_id = request.form.get("account_id")

    if not name or not amount or not category_id or not account_id:
        flash("Preencha nome, valor, categoria e conta.", "danger")
        return redirect(url_for("bp.settings"))

    try:
        amount_f = float(amount)
    except ValueError:
        flash("Valor inválido.", "danger")
        return redirect(url_for("bp.settings"))

    try:
        day_i = int(day)
    except ValueError:
        day_i = 1
    day_i = max(1, min(day_i, 31))

    if txn_type not in ("income","expense"):
        txn_type = "expense"

    desc = request.form.get("description","").strip()

    db.session.add(RecurringTransaction(
        name=name,
        txn_type=txn_type,
        category_id=int(category_id),
        account_id=int(account_id),
        amount=amount_f,
        day_of_month=day_i,
        description=desc,
        is_active=True,
        last_generated_month=""
    ))
    db.session.commit()
    flash("Despesa/receita recorrente criada.", "success")
    return redirect(url_for("bp.settings"))

@bp.route("/settings/recurring/<int:rid>/delete", methods=["POST"])
@admin_required
def delete_recurring(rid: int):
    r = RecurringTransaction.query.get_or_404(rid)
    db.session.delete(r)
    db.session.commit()
    flash("Recorrência removida.", "warning")
    return redirect(url_for("bp.settings"))

# ---------------- PWA files ----------------
@bp.route("/manifest.json")
def manifest():
    from flask import current_app
    return {
        "name": current_app.config.get("PWA_NAME","Finanças da Casa"),
        "short_name": "Finanças",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0b1220",
        "theme_color": "#0b1220",
        "icons": []
    }