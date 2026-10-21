# Manutenção

## Quando o Power BI Desktop atualizar
1. Regerar o catálogo de propriedades a partir do Desktop instalado:
   `python -X utf8 scripts/extract_catalog.py` (aceita outro caminho de `bin` como argumento).
2. Se `validate` avisar "schema ... mais novo que a cópia local", atualize `schemas/`:
   ```
   git clone --depth 1 --filter=blob:none --sparse https://github.com/microsoft/json-schemas ms
   cd ms && git sparse-checkout set fabric/item/report
   ```
   e copie `fabric/item/report/definition/*` para `schemas/` (licença MIT em
   `schemas/LICENSE-microsoft-json-schemas.txt`).

## Requisitos
- Python 3.10+ e `pip install jsonschema` (sem ele só a sintaxe JSON é checada).
- Windows para a detecção do Desktop aberto (em outros sistemas a checagem é ignorada).

## Backups
Cada gravação cria `.pbir-backups/<data>_<comando>.zip` na pasta do projeto (relatório + TMDL).
`undo` restaura o mais recente e o remove; `undo --list` / `undo --to <nome>`.
Apague a pasta quando quiser; inclua no `.gitignore`.
