# Formato PBIP / PBIR

## Pastas

```
Projeto/
  Projeto.pbip                       ponteiro para o relatório
  Projeto.Report/
    definition.pbir                  datasetReference: byPath (modelo local) ou byConnection (serviço)
    definition/
      version.json
      report.json                    tema, configurações, filtros do relatório
      pages/
        pages.json                   {"pageOrder": [...], "activePageName": "..."}
        <pagina>/page.json           name, displayName, width, height, displayOption, objects, filterConfig
        <pagina>/visuals/<visual>/visual.json
      bookmarks/ ...                 opcional
  Projeto.SemanticModel/
    definition/tables/*.tmdl         tabelas, colunas, medidas (texto TMDL)
  .pbir-backups/                     criado pela CLI (zip por gravação) — adicione ao .gitignore
```

O nome da pasta da página/visual deve ser igual ao campo `name` do JSON (máx. 50 caracteres).

## Anatomia do visual.json

```json
{
  "$schema": ".../visualContainer/2.7.0/schema.json",
  "name": "v02ReceitaPorCategoria",
  "position": {"x": 310, "y": 20, "z": 2000, "width": 600, "height": 360, "tabOrder": 1},
  "visual": {
    "visualType": "clusteredColumnChart",
    "query": {"queryState": {
      "Category": {"projections": [ <campo> ]},
      "Y":        {"projections": [ <campo>, <campo> ]}
    }},
    "objects": {"legend": [{"properties": {"show": {"expr": {"Literal": {"Value": "true"}}}}}]},
    "visualContainerObjects": {"title": [{"properties": {"text": {"expr": {"Literal": {"Value": "'Receita'"}}}}}]},
    "drillFilterOtherVisuals": true
  },
  "filterConfig": {"filters": []},
  "isHidden": false,
  "parentGroupName": "grupo opcional"
}
```

A CLI usa a versão de `$schema` que o Desktop já gravou no projeto (fallback 2.7.0).

## Campos (projections)

```json
{"field": {"Column":  {"Expression": {"SourceRef": {"Entity": "Produto"}}, "Property": "Categoria"}},
 "queryRef": "Produto.Categoria", "nativeQueryRef": "Categoria"}
{"field": {"Measure": {"Expression": {"SourceRef": {"Entity": "Medidas"}}, "Property": "Receita"}},
 "queryRef": "Medidas.Receita", "nativeQueryRef": "Receita"}
{"field": {"Aggregation": {"Expression": {"Column": {...}}, "Function": 0}},
 "queryRef": "Sum(Fato.Valor)", "nativeQueryRef": "Sum of Valor"}
```
Funções: 0 Sum, 1 Average, 2 Distinct count, 3 Min, 4 Max, 5 Count, 6 Median, 7 StdDev, 8 Variance.

## Literais

| Tipo | Valor |
|---|---|
| booleano | `"true"` |
| texto | `"'FitToPage'"` (aspas simples; `''` escapa) |
| inteiro | `"12L"` |
| decimal | `"0.5D"` |
| cor | `{"solid": {"color": {"expr": {"Literal": {"Value": "'#1F3A5F'"}}}}}` |
| cor por medida | `{"solid": {"color": {"expr": {"Measure": {...}}}}}` |

Cada objeto é uma lista de entradas `{"properties": {...}, "selector": {...}}`. Sem `selector` vale
para o visual todo; com `selector` (`{"metadata": "Medidas.Receita"}` ou `{"data": [...]}`) vale
para uma série/ponto — ex.: cor de uma série específica. A CLI edita a entrada sem seletor; para
seletores, edite o JSON e rode `validate`.

## Textbox

```json
"visual": {"visualType": "textbox", "objects": {"general": [{"properties": {"paragraphs": [
  {"textRuns": [{"value": "Painel de Vendas", "textStyle": {"fontSize": "20pt", "fontWeight": "bold"}}]}
]}}]}}
```

## Página

```json
{"name": "pg01Resumo", "displayName": "Resumo", "displayOption": "FitToPage", "width": 1280, "height": 720,
 "type": "Tooltip|Drillthrough (opcional)", "visibility": "HiddenInViewMode (opcional)",
 "objects": {"background": [{"properties": {"color": <cor>, "transparency": {"expr": {"Literal": {"Value": "0D"}}}}}]}}
```
