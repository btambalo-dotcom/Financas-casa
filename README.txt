Controle Financeiro Familiar - PRO V2 (multi-telas + upgrades)

✅ Login (admin + esposa)
✅ Editar lançamento
✅ Relatórios
✅ Exportar CSV/Excel/PDF
✅ Importar CSV (conciliação simples)
✅ PWA básico (instalável)

LOGIN PADRÃO
- admin / admin123
- esposa / esposa123
(Depois troque em Configurações)

RODAR NO WINDOWS (PowerShell)
1) Crie e ative o venv:
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
2) Rode:
   python run.py
3) Abra:
   http://127.0.0.1:5000

Obs:
- Excluir lançamento: só admin
- Importar CSV: só admin

V3:
- Criar/Excluir usuários (admin)
- Export PDF/Excel mais profissional


V4:
- Orçamento padrão (templates) reutilizado automaticamente todo mês
- Exceções por mês (opcional)
- Despesas/Receitas recorrentes (geram automaticamente todo mês)

IMPORTANTE: Se você já tiver um finance.db antigo e quiser começar limpo, apague o arquivo finance.db na pasta do projeto.
