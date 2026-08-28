# -*- coding: utf-8 -*-
"""Arma data.json de la v2 a partir del volcado de Monday (src/crudo.tsv)
   + las causas textuales que ya se habian extraido de los updates de GLOW 3."""
import json, pathlib, datetime, itertools

BASE = pathlib.Path(__file__).parent.parent
CORTE = datetime.date(2026, 8, 28)

NOMBRE = {"glow3": "GLOW 3", "glow5": "GLOW 5", "glow6": "GLOW 6+", "glow7": "GLOW 7"}
BOARD  = {"glow3": 18398874016, "glow5": 18402983112, "glow6": 18398672766, "glow7": 18402983267}
TOTAL  = {"glow3": 778, "glow5": 540, "glow6": 726, "glow7": 619}
ACTIVAS= {"glow3": 81,  "glow5": 103, "glow6": 3,   "glow7": 37}

FRENADA = {"Bloqueada", "Retrasada", "Pendiente", "Restringido por Mano de Obra"}
CORTO   = {"Bloqueada": "Bloqueada", "Retrasada": "Retrasada", "Pendiente": "Pendiente",
           "Restringido por Mano de Obra": "Sin mano de obra", "Iniciada": "En curso"}

def pct(s):
    s = (s or "").strip()
    if not s: return None
    try: return int(float(s.lstrip("0") or "0"))
    except ValueError: return None

def rango(s):
    s = (s or "").strip()
    if " - " not in s: return None, None
    a, b = s.split(" - ", 1)
    return a.strip(), b.strip()

def dias(f):
    if not f: return None
    y, m, d = (int(x) for x in f.split("-"))
    return (CORTE - datetime.date(y, m, d)).days

# ── causas textuales ya extraidas de los updates (se conservan) ──
prev = json.loads((BASE / "data.json").read_text(encoding="utf-8"))
causas = {(c["oid"], c["tarea"]): {k: c[k] for k in
          ("causa", "familia", "autor", "fechaCausa", "alcance", "parcial")}
          for c in json.loads((BASE / "src" / "causas.json").read_text(encoding="utf-8"))}

# ── volcado ──
filas = []
for ln in (BASE / "src" / "crudo.tsv").read_text(encoding="utf-8").splitlines():
    if not ln.strip(): continue
    c = (ln.split("\t") + [""] * 7)[:7]
    oid, sector, tarea, p, estado, cron, resp = [x.strip() for x in c]
    ini, fin = rango(cron)
    atraso = dias(fin)
    filas.append({
        "oid": oid, "obra": NOMBRE[oid], "sector": sector, "tarea": tarea,
        "avance": pct(p), "estado": estado, "corto": CORTO.get(estado, estado),
        "ini": ini, "fin": fin,
        "vencidaDias": atraso if (atraso is not None and atraso > 0) else None,
        "sinFecha": fin is None,
        "resp": resp or None,
        **(causas.get((oid, tarea)) or {"causa": None, "familia": None, "autor": None,
                                        "fechaCausa": None, "alcance": None, "parcial": False}),
    })

def problema(f):
    """Un frente lo abre lo que esta frenado o vencido Y tiene fecha o causa.
       Lo que no tiene ni fecha ni causa es carga incompleta, no un frente."""
    if f["sinFecha"] and not f["causa"]:
        return False
    return f["estado"] in FRENADA or f["vencidaDias"] is not None

def enCurso(f):
    return (f["estado"] == "Iniciada" and f["ini"] and f["fin"]
            and f["ini"] <= CORTE.isoformat() <= f["fin"])

# ── frentes por obra + sector ──
frentes = []
for (oid, sector), items in itertools.groupby(
        sorted(filas, key=lambda f: (f["oid"], f["sector"])), key=lambda f: (f["oid"], f["sector"])):
    items = list(items)
    malos = [i for i in items if problema(i)]
    if not malos: continue
    conFecha = [i["fin"] for i in malos if i["fin"]]
    malos.sort(key=lambda i: (i["fin"] or "9999", i["tarea"]))
    frentes.append({
        "obra": NOMBRE[oid], "oid": oid, "sector": sector,
        "vence": min(conFecha) if conFecha else None,
        "atrasoMax": max([i["vencidaDias"] or 0 for i in malos]) or None,
        "frenadas": sum(1 for i in malos if i["estado"] in FRENADA),
        "vencidas": sum(1 for i in malos if i["vencidaDias"]),
        "sinFecha": sum(1 for i in malos if i["sinFecha"]),
        "enCurso": len(items) - len(malos),
        "items": [{k: i[k] for k in ("tarea", "estado", "corto", "avance", "ini", "fin",
                                     "vencidaDias", "sinFecha", "resp", "causa", "familia",
                                     "autor", "fechaCausa", "alcance", "parcial")} for i in malos],
    })
frentes.sort(key=lambda f: (-(f["atrasoMax"] or -9999), f["vence"] or "9999", f["obra"]))

# ── lo que hoy se esta ejecutando (util donde no hay frentes cargados) ──
curso = [f for f in filas if enCurso(f) and not problema(f)]
curso.sort(key=lambda f: (f["oid"], f["fin"]))
curso = [{k: f[k] for k in ("oid", "obra", "sector", "tarea", "avance", "ini", "fin", "resp")}
         for f in curso]

# ── tareas activas sin fecha en el plan ──
sinplan = {}
for f in filas:
    if f["sinFecha"] and not f["causa"]:
        sinplan.setdefault(f["oid"], []).append({"sector": f["sector"], "tarea": f["tarea"],
                                                 "estado": f["estado"], "corto": f["corto"],
                                                 "resp": f["resp"]})
sinPlan = [{"oid": k, "obra": NOMBRE[k], "n": len(v),
            "sectores": len({x["sector"] for x in v}), "items": v}
           for k, v in sorted(sinplan.items())]

# ── resumen por obra ──
obrasM = []
for oid in ("glow3", "glow5", "glow6", "glow7"):
    de = [f for f in filas if f["oid"] == oid]
    fr = [f for f in frentes if f["oid"] == oid]
    obrasM.append({
        "oid": oid, "obra": NOMBRE[oid], "board": BOARD[oid],
        "tareas": TOTAL[oid], "activas": ACTIVAS[oid],
        "frentes": len(fr),
        "tareasProblema": sum(len(f["items"]) for f in fr),
        "frenadas": sum(1 for f in de if f["estado"] in FRENADA),
        "vencidas": sum(1 for f in de if f["vencidaDias"]),
        "sinFecha": sum(1 for f in de if f["sinFecha"]),
        "conCausa": sum(1 for f in de if f["causa"]),
        "conResp": sum(1 for f in de if f["resp"]),
    })

d = dict(prev)
d["corte"] = CORTE.isoformat()
d["mauricio"] = {
    "obras": obrasM,
    "frentes": frentes,
    "enCurso": curso,
    "sinPlan": sinPlan,
    "seLibera": prev["mauricio"]["seLibera"],
    "faltan": prev["mauricio"]["faltan"],
}
(BASE / "data.json").write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")

for o in obrasM:
    print("{obra:8} frentes {frentes:3}  tareas-problema {tareasProblema:3}  frenadas {frenadas:3}"
          "  vencidas {vencidas:3}  sin fecha {sinFecha:3}  con causa {conCausa:3}"
          "  con resp {conResp:3}".format(**o))
print("\ntotal frentes:", len(frentes), "| en curso:", len(curso),
      "| sin plan:", sum(x["n"] for x in sinPlan))
for x in sinPlan:
    print("  sin plan  {obra:8} {n:3} tareas en {sectores} sectores".format(**x))
for oid in ("glow3","glow5","glow6","glow7"):
    n = len([c for c in curso if c["oid"] == oid])
    print("  en curso  {:8} {:3}".format(NOMBRE[oid], n))
for f in frentes[:12]:
    print("  {obra:8} {sector:32} vence {v:10} atraso {a}  ({n} tareas)".format(
        obra=f["obra"], sector=f["sector"][:32], v=f["vence"] or "—",
        a=f["atrasoMax"] or 0, n=len(f["items"])))
