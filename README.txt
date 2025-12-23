Controle Financeiro Familiar - PRO V10 (Render/PostgreSQL seguro) (multi-telas + upgrades)

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



DEPLOY NO RENDER (Plano Pago)
- Build Command:
  pip install -r requirements.txt
- Start Command (recomendado):
  gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120

Env Vars:
- FLASK_ENV=production
- SECRET_KEY=uma-chave-segura

Notas:
- Não suba a pasta .venv nem o arquivo finance.db para o GitHub.
- Este projeto inclui wsgi.py + Procfile + render.yaml para facilitar.



IMPORTANTE (Render): PostgreSQL obrigatório
- Em produção (Render), o app NÃO inicia se estiver em SQLite.
- Motivo: SQLite no Render é apagado em deploy/restart e você perde tudo.

Como configurar no Render:
1) Render -> New -> PostgreSQL (ou use o seu financas-casa-db existente)
2) Web Service -> Environment -> crie/cole:
   DATABASE_URL = postgresql://USER:SENHA@HOST:5432/NOME_DO_BANCO
   (Se vier postgres://, tudo bem: o app converte automaticamente.)
3) Web Service -> Environment -> defina SECRET_KEY (uma chave segura)
4) Deploy latest commit

Verificação:
- Entre como admin -> Configurações -> Diagnóstico
- Deve mostrar Driver: postgresql

PERSISTÊNCIA DE DADOS (para não perder ao atualizar)
Recomendado (Render pago): usar PostgreSQL.
1) No Render: New -> PostgreSQL (crie um banco)
2) No seu Web Service: Environment -> adicione a variável DATABASE_URL (Render fornece)
3) Redeploy. Os dados ficam no banco e NÃO se perdem em novas versões.
Obs: não faça commit do finance.db; use DATABASE_URL em produção.
