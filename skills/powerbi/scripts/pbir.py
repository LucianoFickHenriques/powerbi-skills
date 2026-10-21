#!/usr/bin/env python3
"""pbir.py - CLI para ler e editar relatorios Power BI salvos como PBIP (formato PBIR).

Toda escrita faz backup automatico da pasta definition/ (desfazer com `undo`) e
valida o resultado contra os schemas oficiais da Microsoft em ../schemas.

Uso rapido:
  python pbir.py info    <projeto>                 # paginas, visuais, campos
  python pbir.py model   <projeto>                 # tabelas/colunas/medidas (TMDL)
  python pbir.py add-visual <projeto> --page P --type clusteredColumnChart \
        --role "Category=Produto[Categoria]" --role "Y=Medidas[Receita]" --title "Receita"
  python pbir.py apply   <projeto> spec.json       # cria/edita varios visuais de uma vez
  python pbir.py validate <projeto>
  python pbir.py undo    <projeto>
Rode `python pbir.py <comando> -h` para as opcoes de cada comando.
"""
__version__ = "1.0.0"

import argparse
import copy
import datetime
import json
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCHEMA_DIR = SKILL_DIR / "schemas"
SCHEMA_BASE = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
DEFAULT_VERSIONS = {"visualContainer": "2.7.0", "page": "2.1.0", "pagesMetadata": "1.0.0"}

# Codigos de QueryAggregateFunction (semanticQuery schema 1.4.0)
AGGREGATIONS = {"sum": 0, "avg": 1, "average": 1, "distinctcount": 2, "countdistinct": 2,
                "min": 3, "max": 4, "count": 5, "median": 6, "stdev": 7, "var": 8}
AGG_LABEL = {0: ("Sum", "Sum of"), 1: ("Avg", "Average of"), 2: ("CountDistinct", "Count of"),
             3: ("Min", "Min of"), 4: ("Max", "Max of"), 5: ("Count", "Count of"),
             6: ("Median", "Median of"), 7: ("StandardDeviation", "Standard deviation of"),
             8: ("Variance", "Variance of")}
# Objetos de formatacao que pertencem ao container (visualContainerObjects), nao ao visual
CONTAINER_OBJECTS = {"title", "subTitle", "background", "border", "dropShadow", "padding",
                     "visualHeader", "visualHeaderTooltip", "visualTooltip", "visualLink",
                     "lockAspect", "general", "stylePreset", "divider", "spacing"}
# "general" existe nos dois lugares; para textbox o conteudo fica em visual.objects.general
VISUAL_GENERAL_TYPES = {"textbox"}

CATALOG_FILE = SKILL_DIR / "references" / "catalogo-propriedades.json"
_catalog = None


def catalog():
    """Objetos/propriedades extraidos do Desktop instalado (scripts/extract_catalog.py)."""
    global _catalog
    if _catalog is None:
        _catalog = load_json(CATALOG_FILE)["objetos"] if CATALOG_FILE.exists() else {}
    return _catalog


def check_prop(obj, prop):
    import difflib
    cat = catalog()
    if not cat:
        return None
    if obj not in cat:
        near = difflib.get_close_matches(obj, cat, 3)
        return f"objeto '{obj}' nao existe no Desktop instalado" + (f" (quis dizer {', '.join(near)}?)" if near else "")
    if prop not in cat[obj]:
        near = difflib.get_close_matches(prop, cat[obj], 3)
        return f"propriedade '{obj}.{prop}' nao existe no Desktop instalado" + (
            f" (quis dizer {', '.join(near)}?)" if near else "")
    return None


GAP = 10      # espaco minimo entre visuais (px)
MARGIN = 20   # margem da pagina (px)


class PbirError(Exception):
    pass


# ---------------------------------------------------------------------------
# Projeto
# ---------------------------------------------------------------------------
class Project:
    def __init__(self, path):
        p = Path(path).resolve()
        if p.is_file() and p.suffix.lower() == ".pbip":
            p = p.parent
        if p.name == "definition" and (p / "pages").exists():
            self.definition = p
        elif p.suffix == ".Report" or p.name.endswith(".Report"):
            self.definition = p / "definition"
        else:
            reports = sorted(p.glob("*.Report"))
            if not reports:
                raise PbirError(f"Nenhuma pasta *.Report encontrada em {p}. Salve o relatorio "
                                "como .pbip (Arquivo > Salvar como) com o formato PBIR ativo.")
            if len(reports) > 1:
                raise PbirError("Mais de um *.Report em " + str(p) + ": "
                                + ", ".join(r.name for r in reports) + ". Passe a pasta exata.")
            self.definition = reports[0] / "definition"
        if not (self.definition / "pages").exists():
            if (self.definition.parent / "report.json").exists():
                raise PbirError("Relatorio em formato PBIR-Legacy (report.json unico). No Desktop, "
                                "ative Opcoes > Recursos de visualizacao previa > 'Armazenar relatorios "
                                "usando formato PBIR' e salve de novo.")
            raise PbirError(f"Pasta definition/pages nao encontrada em {self.definition}")
        self.report_dir = self.definition.parent
        self.root = self.report_dir.parent
        self.model_dir = self._find_model()

    def _find_model(self):
        pbir = self.report_dir / "definition.pbir"
        if pbir.exists():
            ref = load_json(pbir).get("datasetReference", {})
            by_path = (ref.get("byPath") or {}).get("path")
            if by_path:
                d = (self.report_dir / by_path).resolve()
                if d.exists():
                    return d
            if ref.get("byConnection"):
                return None  # modelo remoto (servico); campos so via MCP
        models = sorted(self.root.glob("*.SemanticModel"))
        return models[0] if models else None

    # --- paginas ---------------------------------------------------------
    @property
    def pages_dir(self):
        return self.definition / "pages"

    def pages_meta(self):
        f = self.pages_dir / "pages.json"
        return load_json(f) if f.exists() else {"pageOrder": []}

    def page_dirs(self):
        meta = self.pages_meta()
        order = meta.get("pageOrder", [])
        dirs = {d.name: d for d in self.pages_dir.iterdir() if (d / "page.json").exists()}
        ordered = [dirs[n] for n in order if n in dirs]
        ordered += [d for n, d in sorted(dirs.items()) if n not in order]
        return ordered

    def find_page(self, key):
        key_l = key.lower()
        for d in self.page_dirs():
            pj = load_json(d / "page.json")
            if d.name.lower() == key_l or pj.get("displayName", "").lower() == key_l:
                return d
        for i, d in enumerate(self.page_dirs(), 1):
            if key == str(i):
                return d
        raise PbirError(f"Pagina '{key}' nao encontrada. Paginas: "
                        + ", ".join(f"{d.name} ({load_json(d / 'page.json').get('displayName')})"
                                    for d in self.page_dirs()))

    # --- visuais ---------------------------------------------------------
    def visual_dirs(self, page_dir):
        vd = page_dir / "visuals"
        return sorted(d for d in vd.iterdir() if (d / "visual.json").exists()) if vd.exists() else []

    def find_visual(self, key, page=None):
        pages = [self.find_page(page)] if page else self.page_dirs()
        hits = []
        key_l = key.lower()
        for pd in pages:
            for vd in self.visual_dirs(pd):
                v = load_json(vd / "visual.json")
                title = (visual_title(v) or "").lower()
                if vd.name.lower() == key_l or v.get("name", "").lower() == key_l or title == key_l:
                    hits.append((pd, vd))
        if not hits:
            raise PbirError(f"Visual '{key}' nao encontrado (procure pelo nome da pasta ou titulo; "
                            "use `info` para listar).")
        if len(hits) > 1:
            raise PbirError(f"'{key}' e ambiguo: " + ", ".join(f"{p.name}/{v.name}" for p, v in hits)
                            + ". Use --page ou o nome da pasta.")
        return hits[0]

    def schema_version(self, kind):
        """Usa a versao de schema que o proprio Desktop ja gravou no projeto."""
        pattern = {"visualContainer": "pages/*/visuals/*/visual.json", "page": "pages/*/page.json",
                   "pagesMetadata": "pages/pages.json"}[kind]
        versions = []
        for f in self.definition.glob(pattern):
            m = re.search(kind + r"/(\d+\.\d+\.\d+)/", load_json(f).get("$schema", ""))
            if m:
                versions.append(tuple(int(x) for x in m.group(1).split(".")))
        if versions:
            return ".".join(map(str, max(versions)))
        return DEFAULT_VERSIONS[kind]


# ---------------------------------------------------------------------------
# Modelo semantico (TMDL)
# ---------------------------------------------------------------------------
NAME_RE = r"('(?:[^']|'')+'|[^\s=:]+)"


def unquote(n):
    n = n.strip()
    if n.startswith("'") and n.endswith("'"):
        n = n[1:-1].replace("''", "'")
    return n


def read_model(project):
    """Retorna {tabela: {"columns": set, "measures": set}} ou None se nao houver TMDL."""
    if not project.model_dir:
        return None
    tables_dir = project.model_dir / "definition" / "tables"
    if not tables_dir.exists():
        return None
    model = {}
    for f in sorted(tables_dir.glob("*.tmdl")):
        table = last = None
        for line in f.read_text(encoding="utf-8-sig").splitlines():
            m = re.match(r"^table\s+" + NAME_RE, line)
            if m:
                table = unquote(m.group(1))
                model.setdefault(table, {"columns": set(), "measures": set(), "file": f})
                continue
            m = re.match(r"^\t(column|measure)\s+" + NAME_RE, line)
            if m and table:
                last = unquote(m.group(2))
                model[table]["columns" if m.group(1) == "column" else "measures"].add(last)
                if m.group(1) != "column":
                    last = None
                continue
            m = re.match(r"^\t\tdataType:\s*(\w+)", line)
            if m and table and last:
                model[table].setdefault("types", {})[last] = m.group(1)
    return model


# ---------------------------------------------------------------------------
# Campos e literais
# ---------------------------------------------------------------------------
FIELD_RE = re.compile(r"^\s*(?:(?P<kind>[mc]):)?(?:(?P<agg>[a-z]+)\()?\s*(?P<table>'(?:[^']|'')+'|[^\[\(]+?)"
                      r"\s*\[(?P<field>[^\]]+)\]\s*\)?\s*$", re.I)


def parse_field(spec, model):
    """'Tabela[Campo]', 'sum(Tabela[Coluna])', 'm:Tabela[Medida]' -> projection dict."""
    m = FIELD_RE.match(spec)
    if not m:
        raise PbirError(f"Campo invalido '{spec}'. Use Tabela[Campo] ou sum(Tabela[Coluna]).")
    table, field = unquote(m.group("table")), m.group("field").strip()
    agg = m.group("agg")
    kind = (m.group("kind") or "").lower()
    if model is not None:
        t = next((t for t in model if t.lower() == table.lower()), None)
        if t is None:
            raise PbirError(f"Tabela '{table}' nao existe no modelo. Tabelas: {', '.join(sorted(model))}")
        table = t
        cols, meas = model[t]["columns"], model[t]["measures"]
        fm = next((x for x in meas if x.lower() == field.lower()), None)
        fc = next((x for x in cols if x.lower() == field.lower()), None)
        if not kind:
            kind = "m" if fm else "c" if fc else ""
        field = fm if kind == "m" and fm else fc if kind == "c" and fc else field
        if not (fm or fc):
            raise PbirError(f"Campo '{field}' nao existe em '{table}'. Colunas: {', '.join(sorted(cols))}; "
                            f"medidas: {', '.join(sorted(meas)) or '-'}")
    if not kind:
        kind = "c" if agg else "m"  # sem modelo local: sem agregacao assume medida
    src = {"Expression": {"SourceRef": {"Entity": table}}, "Property": field}
    if agg:
        if kind == "m":
            raise PbirError(f"Medidas nao recebem agregacao: {spec}")
        code = AGGREGATIONS.get(agg.lower())
        if code is None:
            raise PbirError(f"Agregacao '{agg}' invalida. Opcoes: {', '.join(AGGREGATIONS)}")
        qname, label = AGG_LABEL[code]
        return {"field": {"Aggregation": {"Expression": {"Column": src}, "Function": code}},
                "queryRef": f"{qname}({table}.{field})", "nativeQueryRef": f"{label} {field}"}
    key = "Measure" if kind == "m" else "Column"
    return {"field": {key: src}, "queryRef": f"{table}.{field}", "nativeQueryRef": field}


def lit(value):
    if isinstance(value, bool):
        s = "true" if value else "false"
    elif isinstance(value, int):
        s = f"{value}L"
    elif isinstance(value, float):
        s = f"{value}D"
    else:
        s = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": s}}}


def parse_value(raw):
    """Converte texto da CLI/spec para o formato de propriedade PBIR."""
    if not isinstance(raw, str):
        v = raw
    elif raw.lower() in ("true", "false"):
        v = raw.lower() == "true"
    elif re.fullmatch(r"-?\d+", raw):
        v = int(raw)
    elif re.fullmatch(r"-?\d*\.\d+", raw):
        v = float(raw)
    else:
        v = raw
    if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", v):
        return {"solid": {"color": lit(v)}}
    if isinstance(v, str) and v.startswith("measure:"):  # formatacao condicional por medida
        t, f = re.match(r"measure:\s*'?(.+?)'?\[(.+)\]$", v).groups()
        return {"solid": {"color": {"expr": {"Measure": {"Expression": {"SourceRef": {"Entity": t}},
                                                         "Property": f}}}}}
    return lit(v)


def literal_text(prop):
    try:
        s = prop["expr"]["Literal"]["Value"]
    except (KeyError, TypeError):
        return None
    return s[1:-1].replace("''", "'") if s.startswith("'") else s


def visual_title(v):
    vis = v.get("visual", {})
    for entry in vis.get("visualContainerObjects", {}).get("title", []):
        t = literal_text(entry.get("properties", {}).get("text", {}))
        if t:
            return t
    if vis.get("visualType") == "textbox":
        for entry in vis.get("objects", {}).get("general", []):
            for p in entry.get("properties", {}).get("paragraphs", []):
                return "".join(r.get("value", "") for r in p.get("textRuns", []))[:40]
    return None


# ---------------------------------------------------------------------------
# Edicao de visuais
# ---------------------------------------------------------------------------
def set_prop(v, path, raw):
    """path = 'objeto.propriedade' (ex.: legend.show, title.text, dataPoint.defaultColor)."""
    if "." not in path:
        raise PbirError(f"Propriedade '{path}' deve ser objeto.propriedade (ex.: legend.show)")
    obj, prop = path.split(".", 1)
    warn = check_prop(obj, prop)
    if warn:
        print("AVISO:", warn, file=sys.stderr)
    vis = v["visual"]
    in_container = obj in CONTAINER_OBJECTS and not (obj == "general" and vis.get("visualType") in VISUAL_GENERAL_TYPES)
    bucket = vis.setdefault("visualContainerObjects" if in_container else "objects", {})
    entries = bucket.setdefault(obj, [])
    entry = next((e for e in entries if "selector" not in e), None)
    if entry is None:
        entry = {"properties": {}}
        entries.insert(0, entry)
    if raw is None:
        entry["properties"].pop(prop, None)
    else:
        entry.setdefault("properties", {})[prop] = parse_value(raw)


def set_title(v, text):
    if text is None:
        return
    if text == "":
        set_prop(v, "title.show", False)
    else:
        set_prop(v, "title.show", True)
        set_prop(v, "title.text", text)


def bind_roles(v, roles, model, mode="replace"):
    qs = v["visual"].setdefault("query", {}).setdefault("queryState", {})
    for role, fields in roles.items():
        projs = [parse_field(f, model) for f in fields]
        if mode == "remove" or not projs:
            qs.pop(role, None)
            continue
        if mode == "append" and role in qs:
            existing = {p["queryRef"] for p in qs[role]["projections"]}
            qs[role]["projections"] += [p for p in projs if p["queryRef"] not in existing]
        else:
            qs[role] = {"projections": projs}
    if not qs:
        v["visual"].pop("query", None)


def parse_roles(items):
    roles = {}
    for item in items or []:
        if "=" not in item:
            raise PbirError(f"--role deve ser Papel=Tabela[Campo] (recebido '{item}')")
        role, fields = item.split("=", 1)
        roles.setdefault(role.strip(), []).extend(split_fields(fields))
    return roles


def split_fields(text):
    """Separa 'A[x], B[y]' respeitando virgulas dentro de colchetes/aspas."""
    out, cur, depth = [], "", 0
    for ch in text:
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def slug(text, maxlen=30):
    import unicodedata
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    t = re.sub(r"[^A-Za-z0-9]+", " ", t).title().replace(" ", "")
    return t[:maxlen]


def new_visual_name(project, page_dir, vtype, title):
    existing = {d.name for d in project.visual_dirs(page_dir)}
    base = slug(title) or vtype[:20]
    i = len(existing) + 1
    while True:
        name = f"v{i:02d}{base}"[:50]
        if name not in existing:
            return name
        i += 1


def page_size(page_dir):
    pj = load_json(page_dir / "page.json")
    return pj.get("width", 1280), pj.get("height", 720)


def rects(project, page_dir, exclude=None):
    out = []
    for vd in project.visual_dirs(page_dir):
        if vd.name == exclude:
            continue
        v = load_json(vd / "visual.json")
        if v.get("parentGroupName"):
            continue
        p = v.get("position", {})
        out.append((vd.name, p.get("x", 0), p.get("y", 0), p.get("width", 0), p.get("height", 0)))
    return out


def overlaps(a, b, gap=0):
    _, ax, ay, aw, ah = a
    _, bx, by, bw, bh = b
    return not (ax + aw + gap <= bx or bx + bw + gap <= ax or ay + ah + gap <= by or by + bh + gap <= ay)


def find_free_slot(project, page_dir, w, h, exclude=None):
    pw, ph = page_size(page_dir)
    taken = rects(project, page_dir, exclude)
    w, h = min(w, pw - 2 * MARGIN), h
    for y in range(MARGIN, max(MARGIN + 1, int(ph - h - MARGIN) + 1), GAP):
        for x in range(MARGIN, max(MARGIN + 1, int(pw - w - MARGIN) + 1), GAP):
            cand = ("new", x, y, w, h)
            if not any(overlaps(cand, t, GAP) for t in taken):
                return x, y, w
    # sem espaco: coloca abaixo de tudo (a pagina pode ser aumentada com set-page --height)
    bottom = max((t[2] + t[4] for t in taken), default=MARGIN - GAP)
    return MARGIN, bottom + GAP, w


DEFAULT_SIZES = {"cardVisual": (280, 140), "card": (220, 120), "multiRowCard": (300, 160),
                 "kpi": (260, 160), "gauge": (300, 220), "slicer": (240, 120),
                 "advancedSlicerVisual": (240, 120), "textbox": (400, 60), "shape": (300, 200),
                 "image": (200, 120), "actionButton": (140, 40), "tableEx": (600, 360),
                 "pivotTable": (600, 360), "pieChart": (380, 320), "donutChart": (380, 320),
                 "map": (600, 400), "filledMap": (600, 400), "azureMap": (600, 400)}


def build_visual(project, page_dir, vtype, roles, model, title=None, pos=None, props=None,
                 name=None, text=None):
    pos = dict(pos or {})
    w, h = pos.get("width"), pos.get("height")
    dw, dh = DEFAULT_SIZES.get(vtype, (600, 360))
    w, h = w or dw, h or dh
    if pos.get("x") is None or pos.get("y") is None:
        x, y, w = find_free_slot(project, page_dir, w, h)
    else:
        x, y = pos["x"], pos["y"]
    x, y, w, h = (int(n) if float(n).is_integer() else n for n in (x, y, w, h))
    existing = [load_json(d / "visual.json") for d in project.visual_dirs(page_dir)]
    z = max((e.get("position", {}).get("z", 0) for e in existing), default=0) + 1000
    tab = max((e.get("position", {}).get("tabOrder", 0) for e in existing), default=-1) + 1
    ver = project.schema_version("visualContainer")
    v = {"$schema": f"{SCHEMA_BASE}visualContainer/{ver}/schema.json",
         "name": name or new_visual_name(project, page_dir, vtype, title or text),
         "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": tab},
         "visual": {"visualType": vtype}}
    if roles:
        bind_roles(v, roles, model)
    if vtype == "textbox" and text is not None:
        v["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [
            {"textRuns": [{"value": line}]} for line in text.split("\n")]}}]}
    if roles and vtype not in ("slicer", "advancedSlicerVisual", "textbox"):
        v["visual"]["drillFilterOtherVisuals"] = True
    set_title(v, title)
    apply_style_defaults(v, model)
    for k, val in (props or {}).items():
        set_prop(v, k, val)
    return v


# Graficos com eixos: titulos de eixo X/Y poluem o visual, entao saem desligados por padrao.
# Para religar: --prop categoryAxis.showAxisTitle=true / valueAxis.showAxisTitle=true
AXIS_TYPES = {"clusteredBarChart", "clusteredColumnChart", "barChart", "columnChart",
              "hundredPercentStackedBarChart", "hundredPercentStackedColumnChart", "lineChart",
              "areaChart", "stackedAreaChart", "hundredPercentStackedAreaChart", "ribbonChart",
              "waterfallChart", "lineStackedColumnComboChart", "lineClusteredColumnComboChart",
              "scatterChart"}
COMBO_TYPES = {"lineStackedColumnComboChart", "lineClusteredColumnComboChart"}


# Graficos categoricos saem ranqueados pelo volume (maior -> menor). Eixo de tempo fica cronologico.
SORT_TYPES = {"clusteredBarChart", "clusteredColumnChart", "barChart", "columnChart",
              "hundredPercentStackedBarChart", "hundredPercentStackedColumnChart", "pieChart",
              "donutChart", "funnel", "treemap", "lineStackedColumnComboChart",
              "lineClusteredColumnComboChart", "tableEx"}
CATEGORY_ROLE = {"treemap": "Group", "tableEx": "Values"}
VALUE_ROLES = ("Y", "ColumnY", "Values", "LineY")
TIME_NAME_RE = re.compile(r"(?i)^(data|date|dia|day|m[eê]s|month|ano|year|trimestre|quarter|semana|week|hora|hour|per[ií]odo)\b")


def is_time_field(proj, model):
    col = proj.get("field", {}).get("Column")
    if not col:
        return False
    table = col.get("Expression", {}).get("SourceRef", {}).get("Entity", "")
    name = col.get("Property", "")
    dtype = ((model or {}).get(table, {}).get("types") or {}).get(name, "")
    return dtype.lower() in ("datetime", "date") or bool(TIME_NAME_RE.match(name))


def rank_by_volume(v, model=None):
    """Ordena pela primeira medida, decrescente, quando fizer sentido. Retorna motivo ou None."""
    vis = v.get("visual") or {}
    vtype = vis.get("visualType")
    if vtype not in SORT_TYPES:
        return None
    qs = (vis.get("query") or {}).get("queryState") or {}
    cats = (qs.get(CATEGORY_ROLE.get(vtype, "Category")) or {}).get("projections", [])
    cats = [p for p in cats if "Column" in p.get("field", {})]
    if not cats or is_time_field(cats[0], model):
        return None  # sem categoria, ou eixo de tempo: mantem ordem cronologica
    value = None
    for role in VALUE_ROLES:
        for p in (qs.get(role) or {}).get("projections", []):
            if "Measure" in p.get("field", {}) or "Aggregation" in p.get("field", {}):
                value = p
                break
        if value:
            break
    if not value:
        return None
    sd = vis["query"].get("sortDefinition") or {}
    if sd.get("sort") and not sd.get("isDefaultSort", False):
        current = sd["sort"][0]
        if current.get("field") != value["field"] or current.get("direction") != "Descending":
            return None  # ordenacao escolhida pelo usuario: respeitar
    vis["query"]["sortDefinition"] = {"sort": [{"field": copy.deepcopy(value["field"]),
                                                "direction": "Descending"}], "isDefaultSort": False}
    return value["queryRef"]


def apply_style_defaults(v, model=None):
    """Padroes visuais da skill. Retorna lista do que alterou."""
    vtype = (v.get("visual") or {}).get("visualType")
    done = []
    if vtype in AXIS_TYPES:
        props = ["categoryAxis.showAxisTitle", "valueAxis.showAxisTitle"]
        if vtype in COMBO_TYPES:
            props.append("valueAxis.secShowAxisTitle")
        for p in props:
            set_prop(v, p, False)
        done.append("sem titulo de eixo")
    ranked = rank_by_volume(v, model)
    if ranked:
        done.append(f"ordenado por {ranked} (maior->menor)")
    return done


# ---------------------------------------------------------------------------
# Paginas
# ---------------------------------------------------------------------------
def create_page(project, display_name, width=1280, height=720, name=None, ptype=None, hidden=False):
    existing = {d.name for d in project.page_dirs()}
    if not name:
        i = len(existing) + 1
        while True:
            name = f"pg{i:02d}{slug(display_name)}"[:50]
            if name not in existing:
                break
            i += 1
    d = project.pages_dir / name
    if d.exists():
        raise PbirError(f"Pagina {name} ja existe")
    page = {"$schema": f"{SCHEMA_BASE}page/{project.schema_version('page')}/schema.json",
            "name": name, "displayName": display_name, "displayOption": "FitToPage",
            "height": height, "width": width}
    if ptype == "tooltip":
        page.update({"type": "Tooltip", "displayOption": "ActualSize"})
    elif ptype == "drillthrough":
        page["type"] = "Drillthrough"
    if hidden:
        page["visibility"] = "HiddenInViewMode"
    write_json(d / "page.json", page)
    meta = project.pages_meta()
    meta.setdefault("$schema", f"{SCHEMA_BASE}pagesMetadata/{project.schema_version('pagesMetadata')}/schema.json")
    meta.setdefault("pageOrder", []).append(name)
    meta.setdefault("activePageName", name)
    write_json(project.pages_dir / "pages.json", meta)
    return d


# ---------------------------------------------------------------------------
# Validacao
# ---------------------------------------------------------------------------
def make_validator_factory():
    try:
        import jsonschema
        from referencing import Registry, Resource
    except ImportError:
        return None
    cache = {}

    def retrieve(uri):
        if not uri.startswith(SCHEMA_BASE):
            raise PbirError(f"schema externo nao suportado: {uri}")
        path = SCHEMA_DIR / uri[len(SCHEMA_BASE):].split("#")[0]
        return Resource.from_contents(json.loads(path.read_text(encoding="utf-8")))

    registry = Registry(retrieve=retrieve)

    def get(uri):
        if uri not in cache:
            path = SCHEMA_DIR / uri[len(SCHEMA_BASE):]
            if not path.exists():
                cache[uri] = None
            else:
                schema = json.loads(path.read_text(encoding="utf-8"))
                cache[uri] = jsonschema.Draft7Validator(schema, registry=registry)
        return cache[uri]
    return get


def validate_project(project, quiet=False):
    errors, warnings = [], []
    get_validator = make_validator_factory()
    if get_validator is None:
        warnings.append("pacote 'jsonschema' ausente: so a sintaxe JSON foi checada (pip install jsonschema)")
    for f in sorted(project.definition.rglob("*.json")):
        rel = f.relative_to(project.definition)
        try:
            data = json.loads(f.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as e:
            errors.append(f"{rel}: JSON invalido ({e})")
            continue
        uri = data.get("$schema", "") if isinstance(data, dict) else ""
        if get_validator and uri.startswith(SCHEMA_BASE):
            val = get_validator(uri)
            if val is None:
                warnings.append(f"{rel}: schema {uri[len(SCHEMA_BASE):]} mais novo que a copia local; "
                                "atualize schemas/ (ver references/manutencao.md)")
            else:
                for err in sorted(val.iter_errors(data), key=lambda e: list(e.absolute_path))[:5]:
                    loc = "/".join(str(p) for p in err.absolute_path) or "(raiz)"
                    errors.append(f"{rel}: {loc}: {err.message[:300]}")
    model = read_model(project)
    if model is None:
        warnings.append("modelo sem TMDL local (conexao ativa/servico): campos nao conferidos. "
                        "Confira pelo powerbi-modeling-mcp.")
    # o catalogo e incompleto (o Desktop grava propriedades que nao aparecem no padrao extraido),
    # entao aqui so resumimos; o aviso detalhado sai na hora de gravar com --prop
    unknown_props = {}
    meta = project.pages_meta()
    for pname in meta.get("pageOrder", []):
        if not (project.pages_dir / pname / "page.json").exists():
            errors.append(f"pages.json: pageOrder cita '{pname}', que nao existe")
    for pd in project.page_dirs():
        pw, ph = page_size(pd)
        rs = rects(project, pd)
        for i, a in enumerate(rs):
            if a[1] < 0 or a[2] < 0 or a[1] + a[3] > pw + 1 or a[2] + a[4] > ph + 1:
                warnings.append(f"{pd.name}/{a[0]}: fora da area da pagina ({pw}x{ph})")
            for b in rs[i + 1:]:
                if overlaps(a, b):
                    warnings.append(f"{pd.name}: {a[0]} sobrepoe {b[0]}")
        for vd in project.visual_dirs(pd):
            v = load_json(vd / "visual.json")
            for bucket in ("objects", "visualContainerObjects"):
                for obj, entries in ((v.get("visual") or {}).get(bucket) or {}).items():
                    for entry in entries:
                        for prop in (entry.get("properties") or {}):
                            if check_prop(obj, prop):
                                unknown_props.setdefault(f"{obj}.{prop}", []).append(f"{pd.name}/{vd.name}")
            if v.get("name") != vd.name:
                errors.append(f"{pd.name}/{vd.name}: 'name' ({v.get('name')}) difere da pasta")
            if model is None:
                continue
            for ent, prop, kind in iter_field_refs(v):
                t = model.get(ent)
                if t is None:
                    errors.append(f"{pd.name}/{vd.name}: tabela '{ent}' nao existe no modelo")
                elif prop not in t["columns"] and prop not in t["measures"]:
                    errors.append(f"{pd.name}/{vd.name}: campo '{ent}[{prop}]' nao existe no modelo")
    if unknown_props:
        warnings.append(f"{len(unknown_props)} propriedade(s) fora do catalogo (pode ser falso positivo se o "
                        f"Desktop as gravou): " + ", ".join(sorted(unknown_props))[:600])
    if not quiet:
        for w in warnings:
            print("AVISO:", w)
        for e in errors:
            print("ERRO: ", e)
        print(f"Validacao: {len(errors)} erro(s), {len(warnings)} aviso(s).")
    return errors, warnings


def iter_field_refs(obj):
    """Encontra todas as referencias {Column|Measure: {Expression:{SourceRef:{Entity}}, Property}}."""
    if isinstance(obj, dict):
        for key in ("Column", "Measure", "Hierarchy"):
            node = obj.get(key)
            if isinstance(node, dict) and "Property" in node:
                ent = node.get("Expression", {}).get("SourceRef", {}).get("Entity")
                if ent:
                    yield ent, node["Property"], key
        for val in obj.values():
            yield from iter_field_refs(val)
    elif isinstance(obj, list):
        for val in obj:
            yield from iter_field_refs(val)


# ---------------------------------------------------------------------------
# Backup / IO
# ---------------------------------------------------------------------------
def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def backup_root(project):
    return project.root / ".pbir-backups"


def snapshot(project, label):
    """Zip unico (evita o limite de 260 caracteres de caminho do Windows)."""
    import zipfile
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    root = backup_root(project)
    root.mkdir(exist_ok=True)
    dest = root / f"{ts}_{label}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for prefix, base in (("definition", project.definition),
                             ("model", project.model_dir / "definition" if project.model_dir else None)):
            if base and base.exists():
                for f in base.rglob("*"):
                    if f.is_file():
                        z.write(f, f"{prefix}/{f.relative_to(base).as_posix()}")
    return dest


def desktop_windows():
    """Titulos das janelas do Power BI Desktop abertas ("<arquivo> - Power BI Desktop")."""
    if sys.platform != "win32":
        return []
    ps = ("[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-CimInstance Win32_Process -Filter \"Name='PBIDesktop.exe'\" | ForEach-Object { "
          "$t = (Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue).MainWindowTitle; "
          "\"$t`t$($_.CommandLine)\" }")
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, encoding="utf-8", errors="replace", timeout=30).stdout
    except Exception:
        return []
    return [line for line in (out or "").splitlines() if line.strip()]


def desktop_running(project=None):
    """Cada item = 'titulo<TAB>linha de comando' de um processo PBIDesktop."""
    procs = desktop_windows()
    if project is None:
        return bool(procs)
    stem = project.report_dir.name[:-len(".Report")].lower()
    for p in procs:
        title, _, cmdline = p.partition("\t")
        if stem in title.lower() or stem in cmdline.lower():
            return True
        # sem titulo (minimizado/dialogo) e sem arquivo na linha de comando: nao da para saber
        if not title.strip() and ".pbi" not in cmdline.lower():
            return True
    return False


def writing(project, label, args, model_change=False):
    """Checagens antes de gravar + snapshot. Retorna o caminho do backup."""
    if desktop_running(project):
        msg = ("Power BI Desktop esta aberto. Ele nao recarrega arquivos alterados por fora e, "
               "ao salvar, sobrescreve estas mudancas. Feche o Desktop (salvando antes) e reabra o .pbip depois.")
        if model_change and not args.force:
            raise PbirError(msg + " Para medidas com o Desktop aberto, use o powerbi-modeling-mcp. "
                            "(--force ignora este bloqueio)")
        if not args.force:
            raise PbirError(msg + " (--force grava mesmo assim)")
        print("AVISO:", msg, file=sys.stderr)
    return snapshot(project, label)


def finish(project, args):
    errors, warnings = validate_project(project, quiet=True)
    for w in warnings:
        print("  AVISO:", w)
    if errors:
        print("A validacao encontrou erros apos a gravacao:")
        for e in errors:
            print("  ERRO:", e)
        print("Corrija ou rode `undo` para voltar ao estado anterior.")
        return 1
    print("OK - arquivos validos. Abra o .pbip no Power BI Desktop para ver o resultado.")
    return 0


# ---------------------------------------------------------------------------
# Comandos
# ---------------------------------------------------------------------------
def describe_visual(vd):
    v = load_json(vd / "visual.json")
    vis = v.get("visual") or {}
    p = v.get("position", {})
    roles = {r: [x.get("queryRef") for x in d.get("projections", [])]
             for r, d in (vis.get("query", {}).get("queryState", {}) or {}).items()}
    return {"name": vd.name, "type": vis.get("visualType") or ("group" if "visualGroup" in v else "?"),
            "title": visual_title(v), "x": p.get("x"), "y": p.get("y"), "width": p.get("width"),
            "height": p.get("height"), "z": p.get("z"), "group": v.get("parentGroupName"),
            "hidden": v.get("isHidden", False), "roles": roles,
            "filters": len((v.get("filterConfig") or {}).get("filters", []))}


def cmd_info(args):
    pr = Project(args.project)
    out = {"report": str(pr.report_dir), "model": str(pr.model_dir) if pr.model_dir else None,
           "desktopRunning": desktop_running(pr), "pages": []}
    active = pr.pages_meta().get("activePageName")
    for pd in pr.page_dirs():
        if args.page and pd != pr.find_page(args.page):
            continue
        pj = load_json(pd / "page.json")
        out["pages"].append({"name": pd.name, "displayName": pj.get("displayName"),
                             "size": f"{pj.get('width')}x{pj.get('height')}", "type": pj.get("type"),
                             "hidden": pj.get("visibility") == "HiddenInViewMode",
                             "active": pd.name == active,
                             "visuals": [describe_visual(vd) for vd in pr.visual_dirs(pd)]})
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    print(f"Relatorio: {out['report']}\nModelo:    {out['model'] or '(remoto / sem TMDL)'}")
    if out["desktopRunning"]:
        print("!! Power BI Desktop aberto - feche antes de editar arquivos.")
    for pg in out["pages"]:
        flags = " [ativa]" if pg["active"] else ""
        flags += f" [{pg['type']}]" if pg["type"] else ""
        flags += " [oculta]" if pg["hidden"] else ""
        print(f"\nPagina {pg['name']} - \"{pg['displayName']}\" {pg['size']}{flags}")
        for v in pg["visuals"]:
            title = f" \"{v['title']}\"" if v["title"] else ""
            print(f"  - {v['name']}: {v['type']}{title} @({v['x']},{v['y']}) {v['width']}x{v['height']}"
                  + (f" grupo={v['group']}" if v["group"] else "") + (" oculto" if v["hidden"] else ""))
            for role, refs in v["roles"].items():
                print(f"      {role}: {', '.join(refs)}")
    return 0


def cmd_model(args):
    pr = Project(args.project)
    model = read_model(pr)
    if model is None:
        print("Sem TMDL local (modelo remoto ou formato .bim). Use o powerbi-modeling-mcp para listar o modelo.")
        return 1
    if args.json:
        print(json.dumps({t: {"columns": sorted(d["columns"]), "measures": sorted(d["measures"])}
                          for t, d in model.items()}, indent=2, ensure_ascii=False))
        return 0
    for t, d in sorted(model.items()):
        print(f"{t}")
        if d["columns"]:
            print("   colunas: " + ", ".join(sorted(d["columns"])))
        if d["measures"]:
            print("   medidas: " + ", ".join(sorted(d["measures"])))
    return 0


def cmd_layout(args):
    pr = Project(args.project)
    pd = pr.find_page(args.page)
    pw, ph = page_size(pd)
    cols, rows = 80, max(10, int(80 * ph / pw / 2))
    grid = [["." for _ in range(cols)] for _ in range(rows)]
    legend = []
    for i, (name, x, y, w, h) in enumerate(rects(pr, pd)):
        ch = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"[i % 36]
        legend.append(f"{ch} = {name} ({x},{y} {w}x{h})")
        for r in range(int(y / ph * rows), min(rows, int((y + h) / ph * rows + 0.999))):
            for c in range(int(x / pw * cols), min(cols, int((x + w) / pw * cols + 0.999))):
                if 0 <= r < rows and 0 <= c < cols:
                    grid[r][c] = ch if grid[r][c] == "." else "#"
    print(f"Pagina {pd.name} {pw}x{ph}  (# = sobreposicao)")
    print("\n".join("".join(r) for r in grid))
    print("\n".join(legend))
    if args.free:
        w, h = (int(n) for n in args.free.lower().split("x"))
        x, y, w = find_free_slot(pr, pd, w, h)
        print(f"Espaco livre para {w}x{h}: x={x} y={y}")
    return 0


def cmd_add_page(args):
    pr = Project(args.project)
    writing(pr, "add-page", args)
    d = create_page(pr, args.display_name, args.width, args.height, args.name, args.type, args.hidden)
    print(f"Pagina criada: {d.name}")
    return finish(pr, args)


def cmd_set_page(args):
    pr = Project(args.project)
    pd = pr.find_page(args.page)
    writing(pr, "set-page", args)
    pj = load_json(pd / "page.json")
    for key in ("width", "height"):
        if getattr(args, key):
            pj[key] = getattr(args, key)
    if args.display_name:
        pj["displayName"] = args.display_name
    if args.display_option:
        pj["displayOption"] = args.display_option
    if args.hidden is not None:
        if args.hidden:
            pj["visibility"] = "HiddenInViewMode"
        else:
            pj.pop("visibility", None)
    if args.background:
        pj.setdefault("objects", {})["background"] = [{"properties": {
            "color": parse_value(args.background), "transparency": lit(0.0)}}]
    write_json(pd / "page.json", pj)
    if args.active:
        meta = pr.pages_meta()
        meta["activePageName"] = pd.name
        write_json(pr.pages_dir / "pages.json", meta)
    if args.move_to:
        meta = pr.pages_meta()
        order = [n for n in meta.get("pageOrder", []) if n != pd.name]
        order.insert(max(0, args.move_to - 1), pd.name)
        meta["pageOrder"] = order
        write_json(pr.pages_dir / "pages.json", meta)
    return finish(pr, args)


def cmd_delete_page(args):
    pr = Project(args.project)
    pd = pr.find_page(args.page)
    writing(pr, "delete-page", args)
    shutil.rmtree(pd)
    meta = pr.pages_meta()
    meta["pageOrder"] = [n for n in meta.get("pageOrder", []) if n != pd.name]
    if meta.get("activePageName") == pd.name:
        meta["activePageName"] = meta["pageOrder"][0] if meta["pageOrder"] else None
        if not meta["activePageName"]:
            meta.pop("activePageName")
    write_json(pr.pages_dir / "pages.json", meta)
    print(f"Pagina removida: {pd.name} (backup em .pbir-backups)")
    return finish(pr, args)


def parse_props(items):
    out = {}
    for item in items or []:
        if "=" not in item:
            raise PbirError(f"--prop deve ser objeto.propriedade=valor (recebido '{item}')")
        k, val = item.split("=", 1)
        out[k.strip()] = None if val == "" else val
    return out


def cmd_add_visual(args):
    pr = Project(args.project)
    pd = pr.find_page(args.page)
    model = read_model(pr)
    roles = parse_roles(args.role)
    pos = {"x": args.x, "y": args.y, "width": args.width, "height": args.height}
    v = build_visual(pr, pd, args.type, roles, model, args.title, pos, parse_props(args.prop),
                     args.name, args.text)
    writing(pr, "add-visual", args)
    write_json(pd / "visuals" / v["name"] / "visual.json", v)
    p = v["position"]
    print(f"Visual criado: {pd.name}/{v['name']} ({args.type}) em ({p['x']},{p['y']}) {p['width']}x{p['height']}")
    return finish(pr, args)


def cmd_edit_visual(args):
    pr = Project(args.project)
    pd, vd = pr.find_visual(args.visual, args.page)
    model = read_model(pr)
    f = vd / "visual.json"
    v = load_json(f)
    if "visual" not in v:
        raise PbirError("Este item e um grupo de visuais; edite os filhos ou use set-pos.")
    if args.type:
        v["visual"]["visualType"] = args.type
    if args.role:
        bind_roles(v, parse_roles(args.role), model, "replace")
    if args.add_role:
        bind_roles(v, parse_roles(args.add_role), model, "append")
    for role in args.remove_role or []:
        v["visual"].get("query", {}).get("queryState", {}).pop(role, None)
    set_title(v, args.title)
    for k, val in parse_props(args.prop).items():
        set_prop(v, k, val)
    pos = v.setdefault("position", {})
    for key, attr in (("x", "x"), ("y", "y"), ("width", "width"), ("height", "height"), ("z", "z")):
        val = getattr(args, attr)
        if val is not None:
            pos[key] = int(val) if float(val).is_integer() else val
    if args.auto_place:
        pos["x"], pos["y"], pos["width"] = find_free_slot(pr, pd, pos.get("width", 400),
                                                          pos.get("height", 300), exclude=vd.name)
    if args.hide is not None:
        if args.hide:
            v["isHidden"] = True
        else:
            v.pop("isHidden", None)
    if args.text is not None and v["visual"].get("visualType") == "textbox":
        v["visual"].setdefault("objects", {})["general"] = [{"properties": {"paragraphs": [
            {"textRuns": [{"value": line}]} for line in args.text.split("\n")]}}]
    writing(pr, "edit-visual", args)
    write_json(f, v)
    print(f"Visual atualizado: {pd.name}/{vd.name}")
    return finish(pr, args)


def cmd_copy_visual(args):
    pr = Project(args.project)
    pd, vd = pr.find_visual(args.visual, args.page)
    target = pr.find_page(args.to_page) if args.to_page else pd
    v = load_json(vd / "visual.json")
    if "visual" not in v:
        raise PbirError("Copia de grupos nao suportada; copie os visuais filhos.")
    v = copy.deepcopy(v)
    v.pop("parentGroupName", None)
    v["name"] = new_visual_name(pr, target, v["visual"].get("visualType", "visual"), visual_title(v))
    p = v["position"]
    if args.x is not None and args.y is not None:
        p["x"], p["y"] = args.x, args.y
    else:
        p["x"], p["y"], p["width"] = find_free_slot(pr, target, p["width"], p["height"])
    if args.title is not None:
        set_title(v, args.title)
    writing(pr, "copy-visual", args)
    write_json(target / "visuals" / v["name"] / "visual.json", v)
    print(f"Copiado para {target.name}/{v['name']}")
    return finish(pr, args)


def cmd_delete_visual(args):
    pr = Project(args.project)
    pd, vd = pr.find_visual(args.visual, args.page)
    writing(pr, "delete-visual", args)
    shutil.rmtree(vd)
    print(f"Visual removido: {pd.name}/{vd.name} (backup em .pbir-backups)")
    return finish(pr, args)


def cmd_align(args):
    """Organiza os visuais de uma pagina em grade (linhas na ordem atual de leitura)."""
    pr = Project(args.project)
    pd = pr.find_page(args.page)
    pw, _ = page_size(pd)
    items = []
    for vd in pr.visual_dirs(pd):
        v = load_json(vd / "visual.json")
        if v.get("parentGroupName"):
            continue
        items.append((vd, v))
    items.sort(key=lambda it: (round(it[1]["position"].get("y", 0) / 40), it[1]["position"].get("x", 0)))
    writing(pr, "align", args)
    x, y, row_h = MARGIN, MARGIN, 0
    for vd, v in items:
        p = v["position"]
        w = min(p.get("width", 300), pw - 2 * MARGIN)
        if x + w > pw - MARGIN and x > MARGIN:
            x, y, row_h = MARGIN, y + row_h + args.gap, 0
        p["x"], p["y"], p["width"] = x, y, w
        x += w + args.gap
        row_h = max(row_h, p.get("height", 0))
        write_json(vd / "visual.json", v)
    print(f"{len(items)} visuais reorganizados em {pd.name}")
    return finish(pr, args)


def cmd_style(args):
    """Aplica os padroes visuais da skill (ex.: sem titulo de eixo) a visuais ja existentes."""
    pr = Project(args.project)
    pages = [pr.find_page(args.page)] if args.page else pr.page_dirs()
    model = read_model(pr)
    writing(pr, "style", args)
    changed = 0
    for pd in pages:
        for vd in pr.visual_dirs(pd):
            if args.visual and vd.name != args.visual:
                continue
            v = load_json(vd / "visual.json")
            done = apply_style_defaults(v, model) if "visual" in v else []
            if done:
                write_json(vd / "visual.json", v)
                changed += 1
                print(f"  {pd.name}/{vd.name}: {', '.join(done)}")
    print(f"{changed} visual(is) ajustado(s).")
    return finish(pr, args)


def cmd_apply(args):
    """Aplica uma especificacao declarativa (ver references/spec.md)."""
    pr = Project(args.project)
    spec = load_json(args.spec)
    model = read_model(pr)
    writing(pr, "apply", args)
    created = 0
    for pspec in spec.get("pages", []):
        key = pspec.get("name") or pspec.get("displayName")
        try:
            pd = pr.find_page(key)
        except PbirError:
            pd = create_page(pr, pspec.get("displayName", key), pspec.get("width", 1280),
                             pspec.get("height", 720), pspec.get("name"), pspec.get("type"),
                             pspec.get("hidden", False))
            print(f"Pagina criada: {pd.name}")
        for vspec in pspec.get("visuals", []):
            target = vspec.get("target")
            if target:  # editar visual existente
                _, vd = pr.find_visual(target, pd.name)
                v = load_json(vd / "visual.json")
                if vspec.get("delete"):
                    shutil.rmtree(vd)
                    print(f"  removido {vd.name}")
                    continue
                if vspec.get("type"):
                    v["visual"]["visualType"] = vspec["type"]
                if vspec.get("roles"):
                    bind_roles(v, norm_roles(vspec["roles"]), model, vspec.get("rolesMode", "replace"))
                set_title(v, vspec.get("title"))
                for k, val in (vspec.get("props") or {}).items():
                    set_prop(v, k, val)
                v["position"].update({k: val for k, val in (vspec.get("position") or {}).items()})
                write_json(vd / "visual.json", v)
                print(f"  atualizado {vd.name}")
            else:
                v = build_visual(pr, pd, vspec["type"], norm_roles(vspec.get("roles", {})), model,
                                 vspec.get("title"), vspec.get("position"), vspec.get("props"),
                                 vspec.get("name"), vspec.get("text"))
                write_json(pd / "visuals" / v["name"] / "visual.json", v)
                created += 1
                print(f"  criado {v['name']} ({vspec['type']})")
    print(f"{created} visual(is) criado(s).")
    return finish(pr, args)


def norm_roles(roles):
    return {r: ([f] if isinstance(f, str) else list(f)) for r, f in roles.items()}


def cmd_add_measure(args):
    pr = Project(args.project)
    model = read_model(pr)
    if model is None:
        raise PbirError("Sem TMDL local. Crie a medida pelo powerbi-modeling-mcp.")
    t = next((t for t in model if t.lower() == args.table.lower()), None)
    if t is None:
        raise PbirError(f"Tabela '{args.table}' nao existe. Tabelas: {', '.join(sorted(model))}")
    if any(args.name.lower() == m.lower() for d in model.values() for m in d["measures"]):
        raise PbirError(f"Ja existe uma medida chamada '{args.name}' no modelo.")
    writing(pr, "add-measure", args, model_change=True)
    f = model[t]["file"]
    name = args.name if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.name) else "'" + args.name.replace("'", "''") + "'"
    expr = args.expression.strip()
    lines = [""]
    if "\n" in expr:
        lines.append(f"\tmeasure {name} = ```")
        lines += ["\t\t\t" + ln for ln in expr.splitlines()]
        lines.append("\t\t\t```")
    else:
        lines.append(f"\tmeasure {name} = {expr}")
    if args.format:
        lines.append(f"\t\tformatString: {args.format}")
    if args.folder:
        lines.append(f"\t\tdisplayFolder: {args.folder}")
    lines.append(f"\t\tlineageTag: {uuid.uuid4()}")
    text = f.read_text(encoding="utf-8-sig")
    # insere antes do primeiro bloco de particao/anotacao de nivel de tabela, ou no fim
    m = re.search(r"^\t(partition|annotation|column|hierarchy)\b", text, re.M)
    block = "\n".join(lines) + "\n"
    if m:
        text = text[:m.start()] + block.lstrip("\n") + "\n" + text[m.start():]
    else:
        text = text.rstrip("\n") + "\n" + block
    f.write_text(text, encoding="utf-8")
    print(f"Medida '{args.name}' adicionada em {f.name}. O DAX nao foi testado: valide com "
          "o powerbi-modeling-mcp (dax_query_operations) ao abrir o Desktop.")
    return finish(pr, args)


def cmd_validate(args):
    pr = Project(args.project)
    errors, _ = validate_project(pr)
    return 1 if errors else 0


def cmd_undo(args):
    pr = Project(args.project)
    root = backup_root(pr)
    snaps = sorted(root.glob("*.zip")) if root.exists() else []
    if args.list:
        for s in snaps:
            print(s.name)
        return 0
    if not snaps:
        raise PbirError("Nenhum backup encontrado.")
    snap = root / (args.to if args.to.endswith(".zip") else args.to + ".zip") if args.to else snaps[-1]
    if not snap.exists():
        raise PbirError(f"Backup {args.to} nao existe (use undo --list)")
    if desktop_running(pr) and not args.force:
        raise PbirError("Feche o Power BI Desktop antes de restaurar (--force ignora).")
    import zipfile
    with zipfile.ZipFile(snap) as z:
        names = z.namelist()
        targets = [("definition/", pr.definition)]
        if pr.model_dir and any(n.startswith("model/") for n in names):
            targets.append(("model/", pr.model_dir / "definition"))
        for prefix, base in targets:
            shutil.rmtree(base)
            for n in names:
                if n.startswith(prefix):
                    out = base / n[len(prefix):]
                    out.parent.mkdir(parents=True, exist_ok=True)
                    out.write_bytes(z.read(n))
    snap.unlink()
    print(f"Restaurado o estado anterior a '{snap.name}'.")
    return 0


def cmd_schema(args):
    """Mostra objetos/propriedades de formatacao validos e as versoes de schema locais."""
    if args.what == "versions":
        for d in sorted(p for p in SCHEMA_DIR.iterdir() if p.is_dir()):
            print(d.name + ": " + ", ".join(sorted((x.name for x in d.iterdir() if x.is_dir()),
                                                   key=lambda s: tuple(map(int, s.split("."))))))
        return 0
    cat = catalog()
    if not cat:
        print("Catalogo ausente: rode scripts/extract_catalog.py")
        return 1
    if args.what == "list":
        print("\n".join(f"{o} ({len(p)})" for o, p in cat.items()))
        return 0
    term = args.what.lower()
    hits = {o: p for o, p in cat.items() if term in o.lower()}
    if not hits:  # procura por nome de propriedade
        hits = {o: [x for x in p if term in x.lower()] for o, p in cat.items()}
        hits = {o: p for o, p in hits.items() if p}
    for o, p in hits.items():
        print(f"{o}: {', '.join(p)}")
    if not hits:
        print("Nada encontrado. Use `schema list`.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--version", action="version", version=f"pbir {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        p = sub.add_parser(name, help=help_)
        p.add_argument("project", help="pasta do projeto, arquivo .pbip ou pasta *.Report")
        p.add_argument("--force", action="store_true", help="grava mesmo com o Desktop aberto")
        p.set_defaults(fn=fn)
        return p

    p = add("info", cmd_info, "lista paginas, visuais e campos")
    p.add_argument("--page")
    p.add_argument("--json", action="store_true")
    p = add("model", cmd_model, "lista tabelas, colunas e medidas do TMDL")
    p.add_argument("--json", action="store_true")
    p = add("layout", cmd_layout, "desenha o mapa da pagina e acha espaco livre")
    p.add_argument("--page", required=True)
    p.add_argument("--free", help="tamanho LxA para procurar espaco, ex.: 600x360")
    p = add("validate", cmd_validate, "valida JSON, schemas, campos e sobreposicoes")

    p = add("add-page", cmd_add_page, "cria pagina")
    p.add_argument("display_name")
    p.add_argument("--name")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=720)
    p.add_argument("--type", choices=["tooltip", "drillthrough"])
    p.add_argument("--hidden", action="store_true")
    p = add("set-page", cmd_set_page, "altera pagina (tamanho, nome, fundo, ordem)")
    p.add_argument("page")
    p.add_argument("--display-name")
    p.add_argument("--width", type=int)
    p.add_argument("--height", type=int)
    p.add_argument("--display-option", choices=["FitToPage", "FitToWidth", "ActualSize"])
    p.add_argument("--background", help="cor #RRGGBB")
    p.add_argument("--hidden", type=lambda s: s.lower() == "true")
    p.add_argument("--active", action="store_true")
    p.add_argument("--move-to", type=int, help="nova posicao (1 = primeira)")
    p = add("delete-page", cmd_delete_page, "remove pagina")
    p.add_argument("page")

    p = add("add-visual", cmd_add_visual, "cria visual")
    p.add_argument("--page", required=True)
    p.add_argument("--type", required=True, help="visualType, ex.: clusteredColumnChart")
    p.add_argument("--role", action="append", help="Papel=Tabela[Campo][, Tabela[Campo2]]")
    p.add_argument("--title")
    p.add_argument("--text", help="conteudo de textbox")
    p.add_argument("--prop", action="append", help="objeto.propriedade=valor")
    p.add_argument("--name")
    for k in ("x", "y", "width", "height"):
        p.add_argument("--" + k, type=float)

    p = add("edit-visual", cmd_edit_visual, "altera visual existente")
    p.add_argument("visual", help="nome da pasta do visual ou titulo")
    p.add_argument("--page")
    p.add_argument("--type")
    p.add_argument("--role", action="append", help="substitui os campos do papel")
    p.add_argument("--add-role", action="append", help="acrescenta campos ao papel")
    p.add_argument("--remove-role", action="append")
    p.add_argument("--title", help="'' oculta o titulo")
    p.add_argument("--text")
    p.add_argument("--prop", action="append", help="objeto.propriedade=valor (valor vazio remove)")
    for k in ("x", "y", "width", "height", "z"):
        p.add_argument("--" + k, type=float)
    p.add_argument("--auto-place", action="store_true", help="move para o primeiro espaco livre")
    p.add_argument("--hide", type=lambda s: s.lower() == "true")
    p = add("copy-visual", cmd_copy_visual, "duplica visual (mesma pagina ou outra)")
    p.add_argument("visual")
    p.add_argument("--page")
    p.add_argument("--to-page")
    p.add_argument("--title")
    p.add_argument("--x", type=float)
    p.add_argument("--y", type=float)
    p = add("delete-visual", cmd_delete_visual, "remove visual")
    p.add_argument("visual")
    p.add_argument("--page")
    p = add("align", cmd_align, "reorganiza visuais da pagina em grade")
    p.add_argument("--page", required=True)
    p.add_argument("--gap", type=int, default=GAP)

    p = add("style", cmd_style, "aplica padroes visuais (sem titulo de eixo) a visuais existentes")
    p.add_argument("--page")
    p.add_argument("--visual")
    p = add("apply", cmd_apply, "aplica especificacao JSON (varias paginas/visuais)")
    p.add_argument("spec")
    p = add("add-measure", cmd_add_measure, "acrescenta medida DAX no TMDL (Desktop fechado)")
    p.add_argument("--table", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--expression", required=True)
    p.add_argument("--format")
    p.add_argument("--folder")
    p = add("undo", cmd_undo, "restaura o ultimo backup")
    p.add_argument("--list", action="store_true")
    p.add_argument("--to", help="nome do backup (ver --list)")

    p = sub.add_parser("schema", help="versions | list | <objeto ou propriedade> (catalogo do Desktop)")
    p.add_argument("what")
    p.set_defaults(fn=cmd_schema)

    args = ap.parse_args(argv)
    try:
        return args.fn(args) or 0
    except PbirError as e:
        print("ERRO:", e, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
