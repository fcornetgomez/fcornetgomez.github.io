#!/usr/bin/env python3
"""Descarga mis publicaciones desde INSPIRE-HEP (con ORCID como complemento
opcional) y las guarda en datos/publicaciones.json, junto con las métricas de
citas (datos/metricas.json).

- El perfil de INSPIRE sale del campo "inspire:" de contenido/sitio.yml o, si
  está vacío, se busca a partir del ORCID.
- Con "completar_con_orcid: true" (contenido/publicaciones.yml) se añaden los
  trabajos de ORCID que no estén en INSPIRE. El mismo trabajo visto en las dos
  fuentes se fusiona si coincide el DOI, el número de arXiv o el título.

Si la red falla, se conservan los archivos anteriores y se sale con aviso (no
error), para que la web se pueda seguir construyendo.
"""
import datetime as dt
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "datos" / "publicaciones.json"
METRICAS = RAIZ / "datos" / "metricas.json"
INSPIRE = "https://inspirehep.net/api"
ORCID = "https://pub.orcid.org/v3.0"
PRIORIDAD = {"inspire": 0, "orcid": 1}
CAMPOS = ",".join([
    "control_number", "titles", "authors.full_name", "author_count",
    "publication_info", "dois", "arxiv_eprints", "preprint_date",
    "earliest_date", "document_type", "citation_count", "collaborations",
    "citeable", "refereed",
])


def pedir(url):
    req = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "personal-academic-website (static site builder)",
    })
    for intento in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception:
            if intento == 2:
                raise
            time.sleep(2 * (intento + 1))


def bai_inspire(orcid="", inspire=""):
    """BAI del autor en INSPIRE (p. ej. Fernando.Cornet.Gomez.1), o None."""
    if inspire:
        hits = [pedir(f"{INSPIRE}/authors/{inspire}?fields=ids")]
    else:
        q = urllib.parse.urlencode({"q": f'ids.value:"{orcid}"', "fields": "ids"})
        hits = pedir(f"{INSPIRE}/authors?{q}")["hits"]["hits"]
    for h in hits:
        for i in h["metadata"].get("ids", []):
            if i["schema"] == "INSPIRE BAI":
                return i["value"]
    return None


def trabajos_inspire(bai):
    res, pagina = [], 1
    while True:
        q = urllib.parse.urlencode({
            "q": f"a {bai}", "size": 250, "page": pagina,
            "sort": "mostrecent", "fields": CAMPOS,
        })
        d = pedir(f"{INSPIRE}/literature?{q}")
        hits = d["hits"]["hits"]
        res += [normalizar_inspire(h["metadata"]) for h in hits]
        if len(res) >= d["hits"]["total"] or not hits:
            return res
        pagina += 1


def normalizar_inspire(m):
    pub = next((p for p in m.get("publication_info") or []
                if p.get("journal_title")), (m.get("publication_info") or [{}])[0])
    revista = None
    if pub.get("journal_title"):
        revista = " ".join(str(x) for x in [
            pub.get("journal_title"), pub.get("journal_volume"),
        ] if x)
        pag = pub.get("page_start") or pub.get("artid")
        if pag:
            revista += f", {pag}"
    fecha = m.get("preprint_date") or m.get("earliest_date") or ""
    anio = pub.get("year") or (int(fecha[:4]) if fecha[:4].isdigit() else None)
    arxiv = (m.get("arxiv_eprints") or [{}])[0].get("value")
    doi = (m.get("dois") or [{}])[0].get("value")
    autores = [a["full_name"] for a in m.get("authors", [])]
    return {
        "id": f"inspire:{m['control_number']}",
        "inspire": m["control_number"],
        "titulo": m["titles"][0]["title"],
        "autores": autores[:10],
        "num_autores": m.get("author_count") or len(autores),
        "colaboracion": ", ".join(c["value"] for c in m.get("collaborations", [])),
        "revista": revista,
        "anio": anio,
        "doi": doi,
        "arxiv": arxiv,
        "tipo": (m.get("document_type") or ["article"])[0],
        "citas": m.get("citation_count", 0),
        "citable": bool(m.get("citeable")),
    }


def trabajos_orcid(orcid):
    d = pedir(f"{ORCID}/{orcid}/works")
    res = []
    for g in d.get("group", []):
        s = g["work-summary"][0]
        ids = {e["external-id-type"]: e["external-id-value"]
               for e in (s.get("external-ids") or {}).get("external-id", [])}
        anio = ((s.get("publication-date") or {}).get("year") or {}).get("value")
        revista = (s.get("journal-title") or {}).get("value")
        res.append({
            "id": f"orcid:{s['put-code']}",
            "inspire": None,
            "titulo": s["title"]["title"]["value"],
            "autores": [],
            "num_autores": 0,
            "colaboracion": "",
            "revista": revista if revista and "arxiv" not in revista.lower() else None,
            "anio": int(anio) if anio else None,
            "doi": ids.get("doi"),
            "arxiv": ids.get("arxiv"),
            "tipo": (s.get("type") or "").replace("-", " ").replace("journal ", ""),
            "citas": None,
            "citable": False,
        })
    return res


def claves(t):
    """Identificadores con los que se reconoce el mismo trabajo en otra fuente."""
    res = []
    if t.get("doi"):
        res.append("doi:" + t["doi"].lower().strip())
    if t.get("arxiv"):
        res.append("arxiv:" + t["arxiv"].lower().removeprefix("arxiv:"))
    titulo = re.sub(r"<[^>]+>|\\[a-zA-Z]+", "", t["titulo"] or "").lower()
    titulo = re.sub(r"[^a-z0-9]+", "", titulo)
    if len(titulo) >= 25:
        res.append("titulo:" + titulo)
    return res


def fusionar(trabajos):
    """Quita duplicados: une las versiones del mismo trabajo campo a campo,
    empezando por la fuente preferida (INSPIRE)."""
    trabajos = sorted(trabajos, key=lambda t: PRIORIDAD[t["id"].split(":")[0]])
    res, indice = [], {}
    for t in trabajos:
        previo = next((indice[k] for k in claves(t) if k in indice), None)
        if previo is None:
            previo = dict(t)
            res.append(previo)
        else:
            for k, v in t.items():
                if previo.get(k) in (None, "", [], 0) and v:
                    previo[k] = v
        for k in claves(t):
            indice[k] = previo
    return res


def indice_h(citas):
    citas = sorted((c or 0 for c in citas), reverse=True)
    return sum(1 for i, c in enumerate(citas, 1) if c >= i)


def main():
    sitio = yaml.safe_load((RAIZ / "contenido/sitio.yml").read_text()) or {}
    opciones = yaml.safe_load((RAIZ / "contenido/publicaciones.yml").read_text()) or {}
    excluir = set(opciones.get("excluir") or [])
    orcid = str(sitio.get("orcid") or "").strip()
    inspire = str(sitio.get("inspire") or "").strip()

    try:
        bai = bai_inspire(orcid, inspire) if (orcid or inspire) else None
        trabajos = trabajos_inspire(bai) if bai else []
        print(f"  INSPIRE ({bai}): {len(trabajos)} trabajos")
        if orcid and (not bai or opciones.get("completar_con_orcid")):
            de_orcid = trabajos_orcid(orcid)
            print(f"  ORCID: {len(de_orcid)} trabajos")
            trabajos += de_orcid
    except Exception as e:
        print(f"AVISO: no se pudieron descargar las publicaciones ({e}). "
              "Se mantiene la lista anterior.", file=sys.stderr)
        return

    lista = [t for t in fusionar(trabajos) if t["inspire"] not in excluir]
    lista.sort(key=lambda t: (t["anio"] or 0, t["id"]), reverse=True)
    citables = [t for t in lista if t["citable"]]
    metricas = {
        "trabajos": len(lista),
        "citas": sum(t["citas"] or 0 for t in lista),
        "indice_h": indice_h(t["citas"] for t in citables),
        "fecha": dt.date.today().isoformat(),
    }
    SALIDA.parent.mkdir(exist_ok=True)
    SALIDA.write_text(json.dumps(lista, ensure_ascii=False, indent=1))
    METRICAS.write_text(json.dumps(metricas, ensure_ascii=False, indent=1))
    print(f"{len(lista)} publicaciones guardadas en {SALIDA.relative_to(RAIZ)} "
          f"({metricas['citas']} citas, índice h = {metricas['indice_h']})")


if __name__ == "__main__":
    main()
