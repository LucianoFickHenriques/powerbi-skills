# Power BI Skills para Claude

**Versão 1.0.0** · Autor: **[Luciano Fick Henriques](https://github.com/LucianoFickHenriques)** · Licença MIT

Skill para o [Claude Code](https://claude.com/claude-code) que permite à IA **criar, editar e
organizar relatórios e dashboards do Power BI**: páginas, gráficos, cartões de KPI, tabelas,
matrizes, segmentações, caixas de texto, campos, formatação, cores e layout. Também cria e testa
medidas DAX.

**Construída a partir de engenharia reversa do Power BI Desktop.** Em vez de depender de
documentação parcial, estudamos o próprio aplicativo instalado — seus binários .NET, o front-end
web embarcado (mais de 2.400 scripts), o motor analítico e a ponte entre eles — para entender
exatamente como um visual é representado, consultado e renderizado. A skill foi desenhada sobre
essas evidências: ela escreve visuais no mesmo formato que o Desktop grava, valida cada
propriedade contra um **catálogo de 1.762 propriedades extraído do código do próprio Power BI**
e respeita as regras internas descobertas na análise (como o Desktop sobrescrever arquivos
alterados por fora).

Você descreve o que quer ("crie uma página com os KPIs de vendas e um gráfico por região, nas cores
da empresa") e o Claude lê o modelo de dados, cria as medidas que faltam, monta os visuais e valida
tudo antes de você reabrir o relatório.

---

## Como funciona

O Power BI Desktop, quando o relatório é salvo como **projeto (.pbip) no formato PBIR**, guarda
cada visual como um arquivo JSON declarativo (`visual.json`): tipo do visual, campos por papel
(eixo, valores, legenda), posição e formatação. A skill edita esses arquivos através de uma CLI
em Python que:

1. **lê o projeto e o modelo semântico** (tabelas, colunas e medidas do TMDL);
2. **monta o JSON correto** de cada visual a partir de comandos simples ou de um spec;
3. **confere todos os campos** contra o modelo — não deixa referenciar coluna/medida inexistente;
4. **valida** cada arquivo contra os **schemas oficiais da Microsoft** e contra um **catálogo de
   propriedades de formatação extraído do próprio Power BI Desktop instalado**;
5. **faz backup** (zip) antes de cada gravação, com `undo` para voltar;
6. **impede gravar** enquanto o Desktop está com o projeto aberto (ele sobrescreveria as mudanças).

Para medidas, a skill usa o [Power BI Modeling MCP](https://github.com/microsoft/powerbi-modeling-mcp)
quando o Desktop está aberto (cria e **testa o DAX** ao vivo) ou escreve direto no TMDL com ele fechado.

## Engenharia reversa: o que descobrimos

A análise do Power BI Desktop 2.157 (26.08) — 438 arquivos em `bin` — revelou quatro camadas:

| Camada | Componente | Papel |
|---|---|---|
| Host nativo | `PBIDesktop.exe` (.NET/WinForms) | janela, arquivos .pbix/.pbip, ponte JS↔C# |
| Front-end web | `WebView2Resources\minerva` (Edge WebView2) | canvas do relatório, visuais em D3/SVG, Copilot |
| Motor analítico | `msmdsrv.exe` (Analysis Services / VertiPaq) | modelo tabular em memória, executa DAX |
| ETL | Mashup Engine (Power Query / M) | conectores e transformações |

As descobertas que moldaram a skill:

- **Um visual é JSON declarativo**, não código: tipo, campos por papel, consulta semântica e
  formatação. Por isso a IA só precisa gerar e editar esse JSON.
- **O visual não executa DAX.** O front-end envia uma *SemanticQuery* ao host
  (`SemanticQueryHostService.ExecuteSemanticQuery` via `chrome.webview`), que a traduz em DAX para
  o motor. Por isso os campos são referências semânticas e precisam existir no modelo — a skill
  confere cada um.
- **O schema oficial não valida a formatação dos visuais** (aceita qualquer propriedade), mas o
  código do Desktop declara cada uma como `{objectName, propertyName}`. Extraímos esses pares e
  geramos o catálogo usado na validação (`scripts/extract_catalog.py`, reexecutável a cada versão).
- **O motor fica acessível ao vivo** pela instância local do `msmdsrv.exe`: medidas criadas por
  ali aparecem na hora, enquanto arquivos de relatório só são relidos ao reabrir o projeto.

Evidências detalhadas em [`skills/powerbi/references/arquitetura.md`](skills/powerbi/references/arquitetura.md).

## O que a skill faz

| Área | Recursos |
|---|---|
| Leitura | lista páginas, visuais, campos por papel e posições (`info`); lista tabelas/colunas/medidas (`model`); mapa ASCII da página com sobreposições (`layout`) |
| Páginas | criar, renomear, redimensionar, fundo, ordem, ocultar, tooltip e drillthrough, apagar |
| Visuais | criar, editar (tipo, campos, título, formatação, posição), duplicar entre páginas, ocultar, apagar |
| Lote | `apply` cria/edita um dashboard inteiro a partir de um spec JSON numa única gravação |
| Layout | encaixe automático em espaço livre, reorganização em grade (`align`), aviso de sobreposição e de visual fora da página |
| Formatação | `objeto.propriedade=valor` (cores, legendas, rótulos, eixos, títulos), cor condicional por medida, sugestão de nome quando a propriedade não existe |
| Padrões visuais | gráficos **sem título de eixo X/Y** e **ranqueados do maior para o menor** (exceto eixos de data/tempo); `style` aplica isso a visuais existentes |
| Modelo | medidas via MCP (testadas) ou TMDL; checagem de duplicidade |
| Segurança | validação por schema oficial, conferência de campos, backup zip e `undo`, bloqueio com o Desktop aberto |

Tipos de visual suportados: cartão (novo e antigo), KPI, medidor, colunas/barras (agrupadas,
empilhadas, 100%), linha, área, faixa, cascata, combo, pizza, rosca, funil, treemap, dispersão,
tabela, matriz, segmentação, mapas, árvore de decomposição, caixa de texto, formas, imagem e botões.
Lista e papéis de dados em [`references/visuais.md`](skills/powerbi/references/visuais.md).

## Requisitos

- **Power BI Desktop** (testado na versão 2.157 / 26.08) no Windows.
- **Claude Code** (CLI, app desktop ou extensão de IDE).
- **Python 3.10+** com `jsonschema`:
  ```bash
  pip install jsonschema
  ```
- Opcional, recomendado: **Power BI Modeling MCP** configurado no Claude Code, para criar e testar
  medidas com o Desktop aberto.

## Instalação

Copie a pasta `skills/powerbi` para a pasta de skills do Claude Code:

- para todos os projetos: `%USERPROFILE%\.claude\skills\powerbi`
- ou só para um projeto: `<projeto>\.claude\skills\powerbi`

```bash
git clone https://github.com/LucianoFickHenriques/powerbi-skills
```

```bash
xcopy /E /I powerbi-skills\skills\powerbi "%USERPROFILE%\.claude\skills\powerbi"
```

O Claude passa a usar a skill sozinho quando você pedir algo sobre relatórios Power BI.

## Preparando o relatório

1. No Power BI Desktop: *Arquivo > Opções e configurações > Opções > Recursos de visualização
   prévia* → marque **"Armazenar relatórios usando o formato PBIR"**.
2. *Arquivo > Salvar como* → tipo **"Arquivos de projeto do Power BI (\*.pbip)"**.
3. Peça ao Claude o que quer. Quando ele for gravar os visuais, **feche o Desktop**; depois
   **reabra o .pbip** para ver o resultado. (O Desktop não recarrega arquivos alterados por fora.)

## Exemplos de pedido

- "Crie uma página Visão Geral com 4 KPIs no topo, vendas por mês e um ranking por região, nas cores da empresa."
- "Troque o gráfico 'Receita por região' para barras horizontais e mostre os rótulos."
- "Duplique os filtros da Página 1 para a página nova."
- "Organize a página Detalhe em grade e tire as sobreposições."
- "Valide o projeto e me diga o que está quebrado."

## Uso direto da CLI

A CLI também pode ser usada sem o Claude:

```bash
python -X utf8 skills/powerbi/scripts/pbir.py info "C:\caminho\Relatorio.pbip"
```

```bash
python -X utf8 skills/powerbi/scripts/pbir.py add-visual "C:\caminho\Relatorio.pbip" --page "Resumo" --type clusteredBarChart --role "Category=Loja[Região]" --role "Y=Medidas[Receita]" --title "Receita por região" --prop dataPoint.defaultColor=#1F3A5F
```

```bash
python -X utf8 skills/powerbi/scripts/pbir.py apply "C:\caminho\Relatorio.pbip" examples/spec-dashboard.json
```

Todos os comandos: `python skills/powerbi/scripts/pbir.py -h`. Referência completa em
[`skills/powerbi/SKILL.md`](skills/powerbi/SKILL.md).

## Estrutura

```
skills/powerbi/
  SKILL.md                         instruções que o Claude segue (regras, fluxo, comandos)
  scripts/pbir.py                  CLI: ler, criar, editar, validar, desfazer
  scripts/extract_catalog.py       extrai do Power BI Desktop o catálogo de propriedades
  schemas/                         schemas oficiais PBIR da Microsoft (MIT)
  references/
    arquitetura.md                 como o Power BI Desktop funciona por dentro (evidências)
    pbir-formato.md                anatomia do PBIP/PBIR, campos, literais, agregações
    visuais.md                     tipos de visual, papéis de dados, quando usar cada um
    spec.md                        formato do spec para o comando apply
    design.md                      boas práticas de layout e dashboards
    manutencao.md                  como atualizar schemas e catálogo
    catalogo-propriedades.json     170 objetos / 1.762 propriedades (Desktop 26.08)
examples/spec-dashboard.json       exemplo de spec
```

## Limitações (v1)

- Sem recarga ao vivo: cada rodada de edição exige fechar e reabrir o `.pbip`.
- Filtros de visual/página, bookmarks, temas e cores por série (seletores) exigem edição do JSON
  seguida de `validate`.
- Visuais personalizados (AppSource) são gravados, mas o catálogo não conhece as propriedades deles.
- O catálogo de propriedades é incompleto: algumas propriedades gravadas pelo próprio Desktop
  aparecem como "fora do catálogo" (falso positivo, sinalizado como tal).
- Detecção do Desktop aberto só no Windows.

## Créditos

- **Autor:** [Luciano Fick Henriques](https://github.com/LucianoFickHenriques) — concepção, engenharia reversa do Power BI Desktop, direção e testes em relatórios reais.
- Desenvolvido com o [Claude Code](https://claude.com/claude-code).
- Schemas PBIR: [microsoft/json-schemas](https://github.com/microsoft/json-schemas) (licença MIT,
  ver `skills/powerbi/schemas/LICENSE-microsoft-json-schemas.txt`).

Power BI é marca registrada da Microsoft. Este projeto não é afiliado à Microsoft.
