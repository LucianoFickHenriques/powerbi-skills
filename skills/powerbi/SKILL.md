---
name: powerbi
description: Cria, edita e organiza relatórios e dashboards do Power BI — páginas, visuais (gráficos, cartões, tabelas, matrizes, segmentações, caixas de texto), campos, formatação e layout — escrevendo os arquivos PBIR de um projeto .pbip, e cria/testa medidas DAX pelo powerbi-modeling-mcp ou TMDL. Use sempre que o usuário pedir para montar, alterar, mover, formatar, duplicar ou apagar visuais ou páginas de um relatório Power BI, criar um dashboard a partir de uma descrição, revisar o layout ou validar um projeto .pbip.
---

# Power BI — visuais e dashboards por IA

O Power BI Desktop guarda cada visual como um JSON declarativo (`visual.json`) quando o
relatório é salvo como **projeto .pbip no formato PBIR**. Esta skill edita esses arquivos por
uma CLI (`scripts/pbir.py`) que monta o JSON correto, confere campos contra o modelo, valida
nos schemas oficiais da Microsoft e no catálogo de propriedades extraído do Desktop
instalado, e faz backup antes de cada gravação. O porquê de cada regra está em
`references/arquitetura.md` (evidências da análise do Desktop).

`CLI` abaixo = `python -X utf8 "<pasta desta skill>/scripts/pbir.py"`.

## Regras que não podem ser quebradas

1. **Nunca crie um .pbip do zero.** O usuário cria no Desktop: *Arquivo > Salvar como > Projeto
   do Power BI (.pbip)*, com *Opções > Recursos de visualização prévia > Armazenar relatórios
   usando o formato PBIR* ligado. Se a CLI disser "PBIR-Legacy", peça isso ao usuário.
2. **O Desktop não recarrega arquivos alterados por fora** e sobrescreve tudo ao salvar. Antes de
   editar o relatório, o usuário salva e fecha o projeto; depois reabre o `.pbip`. A CLI bloqueia
   gravações se detectar o projeto aberto — não use `--force` sem o usuário pedir.
   Exceção: **medidas e colunas** podem ser criadas com o Desktop aberto via `powerbi-modeling-mcp`
   (aparecem na hora). Faça isso *antes* de fechar o Desktop para mexer nos visuais.
3. **Sempre edite pela CLI**, não à mão. Se precisar de algo que a CLI não cobre (ex.: filtros
   avançados, bookmarks), edite o JSON e rode `validate` em seguida.
4. **Nunca invente nomes de campos.** Leia o modelo primeiro (`model` ou MCP). A CLI recusa
   `Tabela[Campo]` inexistente.
5. Se a gravação terminar com ERRO de validação, corrija ou rode `undo` — não deixe o projeto quebrado.

## Fluxo

1. **Entender o projeto**
   - `CLI info <projeto>` → páginas, visuais (nome, tipo, título, posição, campos por papel).
   - `CLI model <projeto>` → tabelas, colunas e medidas (TMDL). Se o modelo for remoto/live,
     use o `powerbi-modeling-mcp` (`table_operations`, `measure_operations`).
   - `CLI layout <projeto> --page <p>` → mapa ASCII da página e sobreposições.
2. **Planejar** com o usuário quando o pedido for amplo ("faça um dashboard de vendas"): proponha
   páginas, KPIs e visuais em poucas linhas (ver `references/design.md`) antes de gravar.
3. **Medidas que faltam**
   - Desktop aberto: `powerbi-modeling-mcp` → `measure_operations` (criar) e
     `dax_query_operations` (testar com `EVALUATE ROW("x", [Medida])`). Preferido: o DAX é testado.
   - Desktop fechado: `CLI add-measure <projeto> --table T --name N --expression "..." --format "0.0%"`
     (DAX não é testado; teste pelo MCP quando o Desktop abrir).
4. **Usuário fecha o Desktop** (confirme antes de seguir).
5. **Gravar visuais**
   - Um visual: `add-visual` / `edit-visual` / `copy-visual` / `delete-visual`.
   - Vários de uma vez (dashboard inteiro): escreva um spec e rode `CLI apply <projeto> spec.json`
     (formato em `references/spec.md`). É o caminho preferido para pedidos grandes.
   - Organizar: `align --page P` (grade), `edit-visual --auto-place`, `set-page --height` se faltar espaço.
6. **Validar e entregar**: a CLI valida sozinha a cada gravação; rode `CLI validate <projeto>` no fim,
   resolva ERROS e explique AVISOS relevantes (sobreposição, propriedade desconhecida). Diga ao
   usuário para reabrir o `.pbip` e o que mudou. Ofereça `undo` se não gostar.

## Comandos principais

```
info <proj> [--page P] [--json]
model <proj> [--json]
layout <proj> --page P [--free 600x360]
add-page <proj> "Nome" [--width 1280 --height 720 --type tooltip|drillthrough --hidden]
set-page <proj> <pagina> [--display-name --width --height --background #F5F5F5 --active --move-to 1 --hidden true]
delete-page <proj> <pagina>
add-visual <proj> --page P --type <visualType> --role "Papel=Tabela[Campo], Tabela[Campo2]" ...
           [--title "..."] [--prop objeto.propriedade=valor ...] [--x --y --width --height] [--text "..."]
edit-visual <proj> <visual|titulo> [--page P] [--type] [--role Papel=...] [--add-role ...] [--remove-role Papel]
           [--title "" ] [--prop obj.prop=valor | obj.prop=] [--x --y --width --height --z] [--auto-place] [--hide true]
copy-visual <proj> <visual> [--to-page P] [--title]
delete-visual <proj> <visual>
align <proj> --page P [--gap 10]
style <proj> [--page P] [--visual V]          # aplica os padrões visuais (sem título de eixo, ranking)
apply <proj> spec.json
add-measure <proj> --table T --name N --expression DAX [--format] [--folder]
validate <proj>
undo <proj> [--list] [--to <backup>]
schema versions | list | <objeto ou termo>     # propriedades válidas do Desktop instalado
```

`<proj>` aceita a pasta do projeto, o arquivo `.pbip` ou a pasta `*.Report`.
Páginas e visuais podem ser referidos pelo nome da pasta, pelo nome de exibição/título ou (páginas) pelo número.

### Campos (`--role`)
- `Tabela[Campo]` — a CLI descobre no TMDL se é coluna ou medida. `'Tabela com espaço'[Campo]` também vale.
- `sum(Tabela[Coluna])`, `avg(...)`, `count(...)`, `distinctcount(...)`, `min`, `max`, `median` — coluna agregada.
- Sem TMDL local (modelo remoto): prefixe `m:` (medida) ou `c:` (coluna) — sem prefixo e sem agregação vira medida.
- Papéis por tipo de visual em `references/visuais.md` (ex.: barras = `Category`, `Y`, `Series`, `Tooltips`).

### Padrões visuais (automáticos)
- **Sem título de eixo X/Y**: todo gráfico com eixos criado pela CLI sai com
  `categoryAxis.showAxisTitle=false` e `valueAxis.showAxisTitle=false` (combo: também
  `valueAxis.secShowAxisTitle=false`). O título do visual já diz o que é medido; os títulos de
  eixo só poluem. Religue só se o usuário pedir (`--prop categoryAxis.showAxisTitle=true`).
- **Ranqueado pelo volume (maior → menor)**: barras, colunas, pizza, rosca, funil, treemap, combo e
  tabela saem ordenados de forma decrescente pela primeira medida. Não se aplica quando faz mais
  sentido outra ordem: eixo de **data/tempo** (dataType date/dateTime ou nomes como Data, Mês, Ano —
  fica cronológico), gráficos de linha/área, cascata, ou ordenação já escolhida pelo usuário.
  Para outra ordem, edite `query.sortDefinition` no JSON.
- Visuais que já existiam (ou criados no Desktop): `CLI style <proj> [--page P] [--visual V]`.

### Formatação (`--prop`)
- `objeto.propriedade=valor`. Valores: `true/false`, inteiros, decimais, texto, cor `#RRGGBB`,
  ou `measure:Tabela[Medida]` para cor condicional por medida. Valor vazio remove a propriedade.
- Objetos do contêiner (`title`, `subTitle`, `background`, `border`, `dropShadow`, `padding`,
  `visualHeader`...) vão para `visualContainerObjects` automaticamente; os demais (`legend`,
  `categoryAxis`, `valueAxis`, `labels`, `dataPoint`, `calloutValue`, `columnHeaders`...) para `objects`.
- Antes de usar uma propriedade incomum, confira: `CLI schema legend`, `CLI schema DisplayUnits`.
  A CLI avisa (com sugestão) quando o nome não existe no Desktop instalado.
- Detalhes do formato JSON: `references/pbir-formato.md`.

## Referências (leia sob demanda)
- `references/arquitetura.md` — como o Power BI Desktop funciona por dentro e por que esta skill funciona assim.
- `references/pbir-formato.md` — pastas do PBIP, anatomia do `visual.json`, campos, literais, agregações.
- `references/visuais.md` — `visualType`s, papéis de dados, tamanhos padrão, quando usar cada um.
- `references/spec.md` — formato do spec para `apply` (criar e editar em lote).
- `references/design.md` — boas práticas de layout e de dashboard.
- `references/manutencao.md` — atualizar schemas e catálogo quando o Desktop atualizar.
- `references/catalogo-propriedades.json` — objetos/propriedades extraídos do Desktop (gerado por `scripts/extract_catalog.py`).

## Limitações conhecidas
- Sem recarga ao vivo: cada rodada de edição exige fechar e reabrir o `.pbip`.
- Visuais personalizados (AppSource): a CLI grava, mas o catálogo não conhece as propriedades deles —
  copie de um visual existente (`info --json`) e ajuste.
- Filtros de visual/página, bookmarks, temas e interações entre visuais: edite o JSON seguindo os
  schemas em `schemas/` e valide.
- O catálogo diz quais propriedades existem, mas não em quais tipos de visual cada uma tem efeito.
