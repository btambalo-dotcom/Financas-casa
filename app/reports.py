
from flask import Blueprint, request, make_response
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from .db import safe_execute

reports_bp = Blueprint("reports", __name__)

@reports_bp.route("/reports/export/pdf")
@safe_execute
def export_pdf(session):
    month = request.args.get("month")
    category_id = request.args.get("category_id")

    try:
        category_id = int(category_id) if category_id else None
    except ValueError:
        category_id = None

    data = []

    c = canvas.Canvas(None, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, height - 40, "Relatório Financeiro")

    c.setFont("Helvetica", 10)
    c.drawString(40, height - 60, f"Mês: {month or 'Todos'}")
    c.drawString(40, height - 75, f"Categoria: {category_id or 'Todas'}")

    y = height - 110
    if not data:
        c.setFont("Helvetica-Oblique", 11)
        c.drawString(40, y, "Nenhum lançamento encontrado para os filtros selecionados.")
    else:
        for row in data:
            c.drawString(40, y, str(row))
            y -= 14

    c.showPage()
    c.save()

    response = make_response(c.getpdfdata())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=relatorio.pdf"
    return response
