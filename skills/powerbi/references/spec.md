# Spec para `apply`

Um arquivo JSON descreve várias páginas e visuais; `CLI apply <projeto> spec.json` cria o que é novo
e altera o que tem `target`, em uma única gravação (um único backup/`undo`).

```json
{
  "pages": [
    {
      "displayName": "Visão geral",
      "width": 1280, "height": 720,
      "visuals": [
        {"type": "textbox", "text": "Vendas 2026", "position": {"x": 20, "y": 10, "width": 600, "height": 50}},
        {"type": "cardVisual", "title": "Receita", "roles": {"Data": "Medidas[Receita]", "ReferenceLabels": "Medidas[Receita AA]"}},
        {"type": "clusteredBarChart", "title": "Receita por região",
         "roles": {"Category": "Loja[Região]", "Y": ["Medidas[Receita]"]},
         "props": {"labels.show": true, "dataPoint.defaultColor": "#1F3A5F"}},
        {"type": "lineChart", "title": "Tendência mensal",
         "roles": {"Category": "Calendario[Mês]", "Y": ["Medidas[Receita]", "Medidas[Receita AA]"]},
         "position": {"width": 1240, "height": 300}}
      ]
    },
    {
      "name": "pg01Resumo",
      "visuals": [
        {"target": "Receita total", "title": "Receita (R$)", "props": {"calloutValue.labelDisplayUnits": 1000000}},
        {"target": "v03PrecoMedio", "type": "lineChart", "roles": {"Series": "Produto[Categoria]"}, "rolesMode": "append"},
        {"target": "v04Antigo", "delete": true}
      ]
    }
  ]
}
```

## Campos
- Página: `name` (pasta) ou `displayName`; se não existir, é criada. Opcionais: `width`, `height`,
  `type` (`tooltip`/`drillthrough`), `hidden`.
- Visual novo: `type` (obrigatório), `roles` (`{"Papel": "Tabela[Campo]" | [lista]}`), `title`, `text`
  (textbox), `props` (`{"objeto.propriedade": valor}`), `position` (parcial; sem `x/y` a CLI acha
  espaço livre), `name`.
- Visual existente: `target` (pasta ou título) + qualquer um de `type`, `roles`, `rolesMode`
  (`replace` padrão, `append`, `remove`), `title` (`""` oculta), `props`, `position`, `delete: true`.

Ordene os visuais na ordem de leitura (de cima para baixo, da esquerda para a direita): o
posicionamento automático preenche nessa ordem. Para layouts exatos, informe `position` completo
(ver `design.md`).
