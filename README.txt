
PATCH – CORREÇÃO ERRO 500 (EXPORT_FOLDER)

O erro:
KeyError: 'EXPORT_FOLDER'

Correção:
- Define EXPORT_FOLDER com valor padrão
- Cria pasta automaticamente

Como aplicar:
1) Copie app/config.py para o seu projeto (substituir)
2) Garanta que app/__init__.py importa config
3) Redeploy no Render

Não afeta banco de dados.
