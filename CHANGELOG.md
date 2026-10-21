# Changelog

## 1.0.0 — 2026-10-21

Primeira versão pública, construída a partir da engenharia reversa do Power BI Desktop 26.08.

- CLI `pbir.py`: `info`, `model`, `layout`, `validate`, `add-page`, `set-page`, `delete-page`,
  `add-visual`, `edit-visual`, `copy-visual`, `delete-visual`, `align`, `style`, `apply`,
  `add-measure`, `undo`, `schema`.
- Validação contra os schemas oficiais PBIR da Microsoft e conferência de campos no modelo TMDL.
- Catálogo de 170 objetos / 1.762 propriedades extraído do Power BI Desktop 2.157 (26.08)
  (`extract_catalog.py`), com sugestão de nomes.
- Padrões visuais: gráficos sem título de eixo X/Y e ranqueados do maior para o menor
  (eixos de data/tempo ficam cronológicos).
- Backup zip a cada gravação e `undo`; bloqueio quando o Desktop está com o projeto aberto.
- Integração com o Power BI Modeling MCP para criar e testar medidas DAX ao vivo.
- Testada em relatório real (página de KPIs com cartões, linha, barras e colunas).
