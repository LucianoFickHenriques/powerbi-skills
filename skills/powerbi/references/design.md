# Design de dashboards

## Estrutura de página (1280×720)
- Margem 20 px, espaçamento 10–20 px entre visuais. Use múltiplos de 10 para alinhar.
- Faixa superior (y 10–70): título (`textbox`) à esquerda e segmentações à direita.
- Linha de KPIs (y ~80, altura 120–150): 3 a 5 `cardVisual` de mesma largura.
  Largura = (1240 − espaços) / n — ex.: 4 cartões → 4 × 295 com 20 de espaço.
- Corpo: 2 visuais lado a lado (610×~250) e/ou um visual largo (1240×~260) embaixo.
- Se não couber, aumente a página (`set-page --height 1080`) em vez de espremer visuais.

Grade de exemplo para 4 KPIs + 2 gráficos + 1 tendência:
```
título  (20,10, 800x50)                    slicer (1040,10, 220x60)
KPI1 (20,80,295x130) KPI2 (335,80) KPI3 (650,80) KPI4 (965,80)
gráfico A (20,230, 610x230)    gráfico B (650,230, 610x230)
tendência (20,480, 1240x220)
```

## Conteúdo
- Comece pela pergunta de negócio: cada página responde a uma pergunta.
- KPIs no topo e com comparação (AA, meta, variação %); detalhes embaixo.
- No máximo ~8 visuais por página; um título claro em cada visual (diga o que mostra, não o nome do campo).
- Sem títulos de eixo X/Y (padrão da CLI): o título do visual já explica o gráfico.
- Ranqueie por volume, do maior para o menor (padrão da CLI), exceto eixos de tempo (cronológico)
  e categorias com ordem natural (faixas, etapas de funil definidas pelo negócio).
- Barras horizontais para categorias com nomes longos.
- Evite pizza com mais de 5 fatias; use barras.
- Cores: uma cor principal para valores atuais, cinza para comparação, verde/vermelho só para
  variação (ex.: atual `#1F3A5F`, comparação `#BFBFBF`, positivo `#2E9E5B`, negativo `#D64545`).
  Prefira o tema do relatório; só force cores quando o usuário pedir ou para destacar.
- Unidades legíveis: `labelDisplayUnits` 1000000 para milhões, `labelPrecision` 1.
- Segmentações de data e das dimensões principais; mantenha `drillFilterOtherVisuals` (padrão da CLI).

## Checagem final
`CLI layout --page P` sem `#` (sobreposição), `CLI validate` sem erros, títulos em todos os visuais
de dados, mesmo tamanho para visuais da mesma linha.
