# Como o Power BI Desktop funciona (evidências)

Análise estática de `C:\Program Files\Microsoft Power BI Desktop\bin`, versão
2.157.1354.0 (26.08), 438 arquivos. Serve de base para as regras da skill.

## Camadas

| Camada | Evidência | Papel |
|---|---|---|
| Host .NET/WinForms | `PBIDesktop.exe`, `Microsoft.PowerBI.Client.Windows.dll`, `Microsoft.Web.WebView2.WinForms.dll` | Janela, arquivos .pbix/.pbip, ponte JS↔C# |
| Front-end web "minerva" | `WebView2Resources\minerva\` (2.493 scripts; `desktop.min.js` 17,6 MB; `reportView.html`, `modelView.html`, `daxQueryView.html`, `tmdlView.html`) | Canvas do relatório, painéis, visuais, Copilot |
| Motor analítico | `msmdsrv.exe` (Analysis Services/VertiPaq), `tmapi.dll`, `msolap.dll` | Modelo tabular em memória; executa DAX |
| ETL | `Microsoft.MashupEngine.dll`, `Microsoft.Mashup.Container.NetFX45.exe`, pastas `ODBC/ADBC Drivers` | Power Query (linguagem M), conectores |

## Fatos que definem a skill

- **Visual = JSON declarativo.** O bundle referencia `visualContainer` (1.373×), `singleVisual`,
  `prototypeQuery`, `projections`, `objects`, `dataViewMappings`. Cada visual descreve tipo, campos
  por papel e formatação; não contém código. → A IA só precisa gerar/editar esse JSON.
- **O visual não executa DAX.** `SemanticQueryHostService.executeSemanticQuery` chama
  `host.invokeCsFunc("SemanticQueryHostService","ExecuteSemanticQuery",...)` via
  `window.chrome.webview` (postMessage). O host traduz a *SemanticQuery* em DAX e consulta o
  `msmdsrv.exe`. → Por isso os campos no `visual.json` são referências semânticas
  (`Entity`/`Property`), e medidas novas precisam existir no modelo.
- **Visuais são chunks D3/SVG** (`desktop.CartesianVisuals.min.js`: 197× `d3.`, 86× `svg`;
  `DonutChartVisuals`, `CardVisual`, `PivotTableVisuals`...). Visuais personalizados rodam isolados
  em `visualSandbox.html`.
- **Propriedades de formatação** aparecem nos bundles como
  `{objectName:"categoryAxis",propertyName:"labelDisplayUnits"}`. O schema oficial
  `visualConfiguration` aceita *qualquer* propriedade em `visual.objects` (só `visualContainerObjects`
  é estrito), então o catálogo extraído desses pares (`scripts/extract_catalog.py`, 170 objetos /
  1.762 propriedades em 26.08) é a única checagem real de nomes.
- **O motor é acessível ao vivo.** A instância local do `msmdsrv.exe` é o que o
  `powerbi-modeling-mcp` usa: medidas/colunas criadas por ele aparecem na hora; arquivos do
  relatório (`visual.json`) não são relidos até reabrir o projeto.
- **Códigos de agregação** (schema `semanticQuery` 1.4.0, `QueryAggregateFunction`):
  0 Sum, 1 Average, 2 Distinct count, 3 Min, 4 Max, 5 Count (não nulos), 6 Median,
  7 Desvio padrão, 8 Variância.
