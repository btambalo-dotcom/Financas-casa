PATCH (v11) - Correções rápidas

O que este patch corrige:
1) Relatórios: alinhamento do campo 'Mês' (formulário com alinhamento melhor)
2) Exportação PDF: evita erro 500 convertendo todos os valores (data/None/etc) para texto antes de gerar a tabela.

Como aplicar:
- No seu repositório/projeto, substitua APENAS estes arquivos:
  - app/exporters.py
  - app/templates/reports.html

Depois faça o deploy no Render (Deploy latest commit).
