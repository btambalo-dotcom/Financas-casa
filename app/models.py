from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from . import db

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # admin/user
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def set_password(self, pw: str):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw: str) -> bool:
        return check_password_hash(self.password_hash, pw)

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    kind = db.Column(db.String(10), nullable=False)  # income/expense
    is_active = db.Column(db.Boolean, default=True, nullable=False)

class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    kind = db.Column(db.String(20), nullable=False)  # checking/credit/cash/savings
    is_active = db.Column(db.Boolean, default=True, nullable=False)

class BudgetTemplate(db.Model):
    __tablename__ = "budget_templates"
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, unique=True)
    planned_amount = db.Column(db.Float, nullable=False, default=0)
    category = db.relationship("Category")

class Budget(db.Model):
    __tablename__ = "budgets"
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    planned_amount = db.Column(db.Float, nullable=False, default=0)
    category = db.relationship("Category")

class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    txn_date = db.Column(db.Date, default=date.today, nullable=False)

    txn_type = db.Column(db.String(10), nullable=False)  # income/expense
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200), default="")
    receipt_filename = db.Column(db.String(260), default="")

    category = db.relationship("Category")
    account = db.relationship("Account")

class RecurringTransaction(db.Model):
    __tablename__ = "recurring_transactions"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)  # Ex: Aluguel
    txn_type = db.Column(db.String(10), nullable=False, default="expense")  # income/expense
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0)
    day_of_month = db.Column(db.Integer, nullable=False, default=1)  # 1..31
    description = db.Column(db.String(200), default="")
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_generated_month = db.Column(db.String(7), default="", nullable=False)  # YYYY-MM

    category = db.relationship("Category")
    account = db.relationship("Account")

def seed_if_empty():

    # Usuários padrão (troque as senhas na primeira entrada)
    if User.query.count() == 0:
        admin = User(name="Administrador", username="admin", password_hash=generate_password_hash("admin123"), role="admin")
        spouse = User(name="Esposa", username="esposa", password_hash=generate_password_hash("esposa123"), role="user")
        db.session.add(admin)
        db.session.add(spouse)

    if Category.query.count() == 0:
        defaults = [
            ("Salário", "income"), ("Extra/Bônus", "income"), ("Reembolso", "income"),
            ("Moradia", "expense"), ("Contas", "expense"), ("Mercado", "expense"),
            ("Transporte", "expense"), ("Saúde", "expense"), ("Escola/Crianças", "expense"),
            ("Alimentação fora", "expense"), ("Lazer", "expense"), ("Compras", "expense"),
            ("Serviços", "expense"), ("Cartão (pagamento)", "expense"), ("Poupança/Reserva", "expense"),
        ]
        for name, kind in defaults:
            db.session.add(Category(name=name, kind=kind, is_active=True))

    if Account.query.count() == 0:
        accs = [
            ("Conta Corrente", "checking"),
            ("Cartão de Crédito", "credit"),
            ("Dinheiro", "cash"),
            ("Poupança", "savings"),
        ]
        for name, kind in accs:
            db.session.add(Account(name=name, kind=kind, is_active=True))

    # seed budget templates (orçamento padrão)
    from sqlalchemy import desc
    if BudgetTemplate.query.count() == 0:
        latest = Budget.query.order_by(desc(Budget.month)).first()
        if latest:
            items = Budget.query.filter_by(month=latest.month).all()
            for b in items:
                if b.category and b.category.kind == "expense":
                    db.session.add(BudgetTemplate(category_id=b.category_id, planned_amount=b.planned_amount))
        else:
            expenses = Category.query.filter_by(kind="expense", is_active=True).all()
            for c in expenses:
                db.session.add(BudgetTemplate(category_id=c.id, planned_amount=0))

    db.session.commit()
