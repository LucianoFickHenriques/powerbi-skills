# Tipos de visual e papéis de dados

Papéis confirmados no bundle do Desktop 26.08: `Category`, `Y`, `Series`, `Values`, `Tooltips`,
`Group`, `Details`, `Gradient`. Os demais vêm de relatórios reais — em caso de dúvida, crie o
visual uma vez no Desktop e leia com `info --json`.

| visualType | Visual | Papéis | Tamanho padrão da CLI |
|---|---|---|---|
| `cardVisual` | Cartão (novo) | `Data`, `ReferenceLabels` | 280×140 |
| `card` | Cartão (antigo) | `Values` | 220×120 |
| `multiRowCard` | Cartão de várias linhas | `Values` | 300×160 |
| `kpi` | KPI | `Indicator`, `TrendLine`, `Goal` | 260×160 |
| `gauge` | Medidor | `Y`, `MinValue`, `MaxValue`, `TargetValue` | 300×220 |
| `clusteredColumnChart` / `clusteredBarChart` | Colunas/barras agrupadas | `Category`, `Y`, `Series`, `Tooltips` | 600×360 |
| `columnChart` / `barChart` | Empilhadas | `Category`, `Y`, `Series`, `Tooltips` | 600×360 |
| `hundredPercentStackedColumnChart` / `...BarChart` | 100% empilhadas | idem | 600×360 |
| `lineChart` | Linhas | `Category`, `Y`, `Y2`, `Series`, `Tooltips` | 600×360 |
| `areaChart` / `stackedAreaChart` | Áreas | `Category`, `Y`, `Series`, `Tooltips` | 600×360 |
| `lineClusteredColumnComboChart` / `lineStackedColumnComboChart` | Combo | `Category`, `ColumnY`, `LineY`, `Series`, `Tooltips` | 600×360 |
| `ribbonChart` | Faixa | `Category`, `Y`, `Series` | 600×360 |
| `waterfallChart` | Cascata | `Category`, `Y`, `Breakdown` | 600×360 |
| `pieChart` / `donutChart` | Pizza/rosca | `Category`, `Y`, `Tooltips` | 380×320 |
| `funnel` | Funil | `Category`, `Y` | 600×360 |
| `treemap` | Treemap | `Group`, `Details`, `Values` | 600×360 |
| `scatterChart` | Dispersão | `Category`, `X`, `Y`, `Size`, `Series`, `Play` | 600×360 |
| `tableEx` | Tabela | `Values` | 600×360 |
| `pivotTable` | Matriz | `Rows`, `Columns`, `Values` | 600×360 |
| `slicer` | Segmentação | `Values` | 240×120 |
| `advancedSlicerVisual` | Segmentação de botões | `Values` | 240×120 |
| `map` / `filledMap` / `azureMap` | Mapas | `Category`/`Location`, `Size`, `Series` | 600×400 |
| `decompositionTreeVisual` | Árvore de decomposição | `Analyze`, `ExplainBy` | 600×360 |
| `textbox` | Caixa de texto | — (`--text`) | 400×60 |
| `shape`, `image`, `actionButton` | Decorativos | — | variados |

Lista completa de `visualType`s encontrados no Desktop instalado:
`references/catalogo-propriedades.json` → `visualTypesEncontrados`.

## Qual usar
- Um número com comparação → `cardVisual` (+ `ReferenceLabels` para AA/meta).
- Evolução no tempo → `lineChart` (ou `lineClusteredColumnComboChart` para valor + %).
- Ranking/comparação de categorias → `clusteredBarChart` (rótulos longos) ou `clusteredColumnChart`.
- Composição → `columnChart` empilhado ou `donutChart` (até ~5 fatias).
- Ponte entre dois valores → `waterfallChart`.
- Detalhe → `tableEx` / `pivotTable`.
- Filtros → `slicer` no topo ou na lateral.

## Propriedades comuns
`legend.show`, `legend.position` (`Top`, `Bottom`, `Right`...), `labels.show`, `labels.color`,
`labels.labelDisplayUnits` (0 auto, 1 nenhum, 1000 mil, 1000000 mi), `categoryAxis.show`,
`valueAxis.show`, `valueAxis.gridlineShow`, `dataPoint.defaultColor`, `calloutValue.color`,
`calloutValue.labelDisplayUnits`, `title.text`, `title.fontSize`, `background.color`,
`border.show`, `dropShadow.show`. Confira sempre com `CLI schema <objeto>`.
