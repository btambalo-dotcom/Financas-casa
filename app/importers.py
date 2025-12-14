import csv
from datetime import datetime, date

def parse_bank_csv(file_stream):
    """
    Import simples:
      Espera colunas: date, description, amount, type(optional), account(optional), category(optional)
    - date: YYYY-MM-DD
    - amount: número (despesa como negativo ou use type=expense)
    """
    file_stream.seek(0)
    text = file_stream.read().decode("utf-8", errors="ignore").splitlines()
    reader = csv.DictReader(text)
    rows = []
    for r in reader:
        rows.append(r)
    return rows

def coerce_date(s: str) -> date:
    s = (s or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return date.today()

def coerce_float(s: str) -> float:
    s = (s or "").strip().replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0