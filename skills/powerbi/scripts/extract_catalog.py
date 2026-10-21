#!/usr/bin/env python3
"""Extrai do Power BI Desktop instalado o catalogo de objetos/propriedades de formatacao.

O schema oficial (visualConfiguration) aceita qualquer propriedade em visual.objects,
entao a unica fonte confiavel dos nomes validos e o proprio front-end do Desktop
(WebView2Resources/minerva/scripts), onde cada propriedade aparece como
  {objectName:"categoryAxis",propertyName:"labelDisplayUnits"}
Rode de novo sempre que o Desktop for atualizado:
  python extract_catalog.py ["C:\\Program Files\\Microsoft Power BI Desktop\\bin"]
Gera ../references/catalogo-propriedades.json
"""
import json
import re
import sys
from pathlib import Path

DEFAULT_BIN = Path(r"C:\Program Files\Microsoft Power BI Desktop\bin")
OUT = Path(__file__).resolve().parent.parent / "references" / "catalogo-propriedades.json"
PAIR = re.compile(rb'objectName:"([A-Za-z0-9_]+)",propertyName:"([A-Za-z0-9_]+)"')
# chunk de visual -> nome do arquivo (desktop.<Chunk>.min.js)
CHUNK = re.compile(r"^desktop\.(.+?)\.min\.js$")
VISUAL_TYPES = [
    "cardVisual", "card", "multiRowCard", "kpi", "gauge", "clusteredBarChart", "clusteredColumnChart",
    "barChart", "columnChart", "hundredPercentStackedBarChart", "hundredPercentStackedColumnChart",
    "lineChart", "areaChart", "stackedAreaChart", "hundredPercentStackedAreaChart", "ribbonChart",
    "waterfallChart", "lineStackedColumnComboChart", "lineClusteredColumnComboChart", "pieChart",
    "donutChart", "funnel", "treemap", "scatterChart", "tableEx", "pivotTable", "slicer",
    "advancedSlicerVisual", "listSlicer", "textSlicer", "map", "filledMap", "shapeMap", "azureMap",
    "decompositionTreeVisual", "keyDriversVisual", "qnaVisual", "aiNarratives", "textbox", "shape",
    "basicShape", "image", "actionButton", "pageNavigator", "bookmarkNavigator", "scriptVisual",
    "pythonVisual", "paginatedReportVisual", "esriVisual", "rdlVisual"]


def main():
    bin_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_BIN
    scripts = bin_dir / "WebView2Resources" / "minerva" / "scripts"
    if not scripts.exists():
        sys.exit(f"Nao encontrei {scripts}")
    version = None
    exe = bin_dir / "PBIDesktop.exe"
    files = sorted(f for f in scripts.glob("desktop*.js") if ".min." in f.name or f.name == "desktop.js")
    objects, by_chunk = {}, {}
    types_seen = set()
    for f in files:
        data = f.read_bytes()
        m = CHUNK.match(f.name)
        chunk = m.group(1) if m else "core"
        for o, p in PAIR.findall(data):
            o, p = o.decode(), p.decode()
            objects.setdefault(o, set()).add(p)
            by_chunk.setdefault(chunk, set()).add(o)
        for t in VISUAL_TYPES:
            if f'"{t}"'.encode() in data:
                types_seen.add(t)
    try:
        import subprocess
        version = subprocess.run(["powershell", "-NoProfile", "-Command",
                                  f"(Get-Item '{exe}').VersionInfo.ProductVersion"],
                                 capture_output=True, text=True, timeout=30).stdout.strip() or None
    except Exception:
        pass
    out = {
        "_fonte": str(scripts),
        "_versaoDesktop": version,
        "_nota": "Pares objeto->propriedades achados no front-end do Desktop. Nao diz quais visuais "
                 "usam cada objeto; para isso veja 'objetosPorChunk' (chunk = arquivo do visual).",
        "visualTypesEncontrados": sorted(types_seen),
        "objetos": {o: sorted(ps) for o, ps in sorted(objects.items())},
        "objetosPorChunk": {c: sorted(os_) for c, os_ in sorted(by_chunk.items())},
    }
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(objects)} objetos, {sum(len(v) for v in objects.values())} propriedades, "
          f"{len(types_seen)} visualTypes -> {OUT}")


if __name__ == "__main__":
    main()
