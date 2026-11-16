#!/usr/bin/env python3
"""Genera la web estática en _site/ a partir de contenido/, plantillas/ y estatico/.

Se generan dos versiones con las mismas páginas: español (en la raíz) e inglés
americano (en en/). Los textos en inglés salen de datos/traducciones.json
(ver scripts/traduccion.py). Con --estricto, la construcción falla si falta
alguna traducción (se usa antes de cada commit para comprobar que las dos
versiones son iguales).

Todos los enlaces internos son relativos, así la web funciona en cualquier
carpeta o dominio (GitHub Pages, servidor de la UCO o vista previa local).

Los dibujos (diagramas de Feynman y la colisión de la portada) se generan aquí
como SVG: ver las funciones onda(), muelle() y evento().
"""
import copy
import datetime as dt
import hashlib
import json
import math
import random
import re
import shutil
import sys
import unicodedata
from pathlib import Path

import markdown
import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup, escape

from traduccion import Traductor

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
SITE = RAIZ / "_site"

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December"]

# Idiomas de la web: carpeta (relativa a _site/) y prefijo para llegar a la raíz
IDIOMAS = {"es": dict(carpeta="", raiz=""), "en": dict(carpeta="en/", raiz="../")}

# Tipos de documento de INSPIRE → apartado de la página de publicaciones
APARTADOS = [
    ("articulos", "Artículos e informes", ("article", "book", "review", "report",
                                           "book chapter")),
    ("congresos", "Contribuciones a congresos", ("conference paper", "proceedings")),
    ("tesis", "Tesis doctoral", ("thesis",)),
]

# Tema de cada publicación (para los filtros), según palabras de su título.
# Se comprueban en orden; el primero que encaja gana.
TEMAS = [
    ("topologia", "Topología cósmica", r"topolog|kullback|compact|cosmic"),
    ("colisionadores", "Colisionadores", r"collider|top[- ]quark|factory|top sector"),
    ("sabor", "2HDM: sabor y g−2", r"higgs doublet|2hdm|flavou?r|fcnc|ckm|cp|g\s*[-−–]\s*2"),
]


def error(archivo, msg):
    sys.exit(f"\n❌ Error en {archivo}:\n   {msg}\n")


def leer_yaml(nombre):
    ruta = CONTENIDO / nombre
    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        marca = getattr(e, "problem_mark", None)
        linea = f" (línea {marca.line + 1})" if marca else ""
        error(nombre, f"el formato no es válido{linea}. Revisa los espacios al "
                      "principio de la línea y que no falten los dos puntos.")


def md(texto):
    return Markup(markdown.markdown(texto or "", extensions=["smarty"]))


def md_linea(texto):
    """Markdown de una sola línea, sin el párrafo <p> alrededor."""
    html = markdown.markdown(str(texto or ""), extensions=["smarty"])
    return Markup(re.sub(r"^<p>(.*)</p>$", r"\1", html.strip(), flags=re.S))


def fecha_larga(f, idioma="es"):
    if isinstance(f, str):
        f = dt.date.fromisoformat(str(f))
    if idioma == "en":
        return f"{MONTHS[f.month - 1]} {f.day}, {f.year}"
    return f"{f.day} de {MESES[f.month - 1]} de {f.year}"


def recurso(ruta):
    """Ruta a un archivo de estatico/ con su huella (?v=...), para que el
    navegador descargue la versión nueva cuando cambia."""
    contenido = (RAIZ / "estatico" / ruta).read_bytes()
    return f"{ruta}?v={hashlib.md5(contenido).hexdigest()[:8]}"


def _normal(t):
    """Minúsculas, sin acentos y con guiones como espacios."""
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if not unicodedata.combining(c)).replace("-", " ")


def es_yo(autor, nombre):
    """¿El autor «Apellidos, Nombre» de una publicación soy yo?
    Basta con que coincida el primer apellido y la inicial del nombre."""
    palabras = _normal(nombre).split()
    apellido, inicial = palabras[1], palabras[0][0]
    apellidos, _, nombre_a = _normal(autor).partition(",")
    return apellido in apellidos.split() and nombre_a.strip()[:1] == inicial


def preparar_publicacion(p, nombre, mostrados=6):
    """Autores que se muestran (marcándome) y tema de la publicación."""
    p["autores_web"] = [(a, es_yo(a, nombre)) for a in p["autores"][:mostrados]]
    p["yo_en_et_al"] = (p["num_autores"] > mostrados
                        and not any(yo for _, yo in p["autores_web"]))
    p["mostrados"] = mostrados
    p["yo"] = nombre
    texto = f"{p['titulo']} {p.get('colaboracion') or ''}".lower()
    p["tema"] = next((clave for clave, _, rx in TEMAS if re.search(rx, texto)), "")
    return p


def saltos(texto):
    return Markup("<br>".join(escape(l) for l in (texto or "").strip().splitlines()))


def latex_ligero(t):
    """Limpia el LaTeX más habitual de los títulos de INSPIRE."""
    t = str(escape(t)).replace("---", "—").replace("--", "–")
    t = re.sub(r"\\(?:rm|mathrm|text|mathcal|bf)\s*\{([^}]*)\}", r"\1", t)
    t = re.sub(r"\\(?:rm|it)\b\s*", "", t)
    reemplazos = {r"\delta": "δ", r"\nu": "ν", r"\mu": "μ", r"\tau": "τ",
                  r"\Lambda": "Λ", r"\gamma": "γ", r"\alpha": "α", r"\beta": "β",
                  r"\sim": "∼", r"\to": "→", r"\rightarrow": "→", r"\pm": "±",
                  r"\times": "×", r"\Omega": "Ω", r"\sigma": "σ", r"\ell": "ℓ",
                  "\\": ""}
    for a, b in reemplazos.items():
        t = t.replace(a, b)
    t = re.sub(r"\^\{?([^}\s$]+)\}?", r"<sup>\1</sup>", t)
    t = re.sub(r"_\{?([^}\s$]+)\}?", r"<sub>\1</sub>", t)
    t = re.sub(r"(?<=\w)\s*-\s*2\b", "−2", t)   # g-2 → g−2
    return Markup(t.replace("$", "").replace("{", "").replace("}", ""))


# ---------------------------------------------------------------------------
# Dibujos: diagramas de Feynman y colisión de la portada
# ---------------------------------------------------------------------------

def _f(x):
    return f"{x:.1f}".rstrip("0").rstrip(".")


def onda(x1, y1, x2, y2, amplitud=3.0, longitud=8.0):
    """Trazo ondulado (fotón, W, Z) entre dos puntos, como 'd' de un <path>."""
    L = math.hypot(x2 - x1, y2 - y1)
    n = max(2, round(L / longitud * 2))       # medias ondas
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    nx, ny = -uy, ux
    d, paso = [f"M{_f(x1)} {_f(y1)}"], L / n
    for i in range(n):
        s = amplitud * (1 if i % 2 == 0 else -1) * 1.33
        cx = x1 + ux * paso * (i + .5) + nx * s
        cy = y1 + uy * paso * (i + .5) + ny * s
        ex, ey = x1 + ux * paso * (i + 1), y1 + uy * paso * (i + 1)
        d.append(f"Q{_f(cx)} {_f(cy)} {_f(ex)} {_f(ey)}")
    return " ".join(d)


def muelle(x1, y1, x2, y2, radio=3.0, vueltas=None):
    """Trazo en espiral (gluón) entre dos puntos."""
    L = math.hypot(x2 - x1, y2 - y1)
    vueltas = vueltas or max(3, round(L / (radio * 2.2)))
    ux, uy = (x2 - x1) / L, (y2 - y1) / L
    nx, ny = -uy, ux
    pts = []
    for k in range(vueltas * 16 + 1):
        t = k / (vueltas * 16)
        a = 2 * math.pi * vueltas * t
        s = t * L + radio * .9 * math.sin(a) * -1
        h = radio * (1 - math.cos(a))
        pts.append((x1 + ux * s + nx * h, y1 + uy * s + ny * h))
    return "M" + " L".join(f"{_f(x)} {_f(y)}" for x, y in pts)


def evento(semilla=7):
    """Colisión e⁺e⁻ → ZH → μ⁺μ⁻ bb̄ vista en un detector (corte transversal).

    Devuelve las trazas (curvadas por el campo magnético), los depósitos en los
    calorímetros y los impactos en las cámaras de muones, con coordenadas en
    torno a (0, 0). Los radios de las capas del detector están en CAPAS."""
    rnd = random.Random(semilla)
    r_traza, r_ecal, r_hcal, r_muon = 92, 104, 128, 158

    def traza(phi, curv, r_max):
        # Hélice proyectada: arco de circunferencia que sale del origen
        puntos, x, y, a = [(0.0, 0.0)], 0.0, 0.0, phi
        while math.hypot(x, y) < r_max:
            x += 2 * math.cos(a)
            y += 2 * math.sin(a)
            a += 2 * curv
            puntos.append((x, y))
            if len(puntos) > 400:
                break
        d = "M" + " L".join(f"{_f(px)} {_f(py)}" for px, py in puntos)
        return d, math.atan2(y, x)

    trazas, depositos = [], []
    # Dos muones casi opuestos (Z → μ⁺μ⁻): atraviesan todo el detector
    for phi, q in ((0.55, 1), (0.55 + math.pi * .93, -1)):
        d, salida = traza(phi, q * 0.0016, r_muon + 8)
        trazas.append(dict(d=d, clase="muon"))
        for r in (r_muon - 6, r_muon + 2):
            depositos.append(dict(clase="muon", **_celda(salida, r, 5, .05)))
    # Dos chorros de partículas (H → bb̄)
    for eje in (2.35, 2.35 + math.pi * 1.05 - 0.5):
        for _ in range(7):
            phi = eje + rnd.gauss(0, .16)
            q = rnd.choice((-1, 1))
            curv = q * rnd.uniform(.002, .009)
            d, salida = traza(phi, curv, r_traza)
            trazas.append(dict(d=d, clase="hadron"))
            depositos.append(dict(clase="ecal", **_celda(salida, r_ecal - 8,
                                                         rnd.uniform(4, 13), .045)))
            depositos.append(dict(clase="hcal", **_celda(salida, r_hcal - 18,
                                                         rnd.uniform(6, 22), .06)))
    # Algunas partículas blandas sueltas, muy curvadas
    for _ in range(5):
        phi = rnd.uniform(0, 2 * math.pi)
        q = rnd.choice((-1, 1))
        d, _ = traza(phi, q * rnd.uniform(.018, .03), 40)
        trazas.append(dict(d=d, clase="blanda"))
    for i, t in enumerate(trazas):
        t["retraso"] = f"{0.15 + 0.06 * i:.2f}s"
    return dict(trazas=trazas, depositos=depositos,
                capas=dict(traza=r_traza, ecal=r_ecal, hcal=r_hcal, muon=r_muon))


def _celda(angulo, r, largo, ancho):
    """Rectángulo (como polígono) en dirección radial: un depósito de energía."""
    a1, a2 = angulo - ancho / 2, angulo + ancho / 2
    pts = [(r * math.cos(a1), r * math.sin(a1)), ((r + largo) * math.cos(a1), (r + largo) * math.sin(a1)),
           ((r + largo) * math.cos(a2), (r + largo) * math.sin(a2)), (r * math.cos(a2), r * math.sin(a2))]
    return dict(puntos=" ".join(f"{_f(x)},{_f(y)}" for x, y in pts))


# ---------------------------------------------------------------------------

def cargar_noticias():
    noticias = []
    for ruta in sorted((CONTENIDO / "noticias").glob("*.md"), reverse=True):
        texto = ruta.read_text(encoding="utf-8")
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", texto, re.S)
        if not m:
            error(f"noticias/{ruta.name}", "debe empezar con un bloque entre "
                  "líneas '---' que contenga 'titulo:' y 'fecha:'.")
        cab = yaml.safe_load(m.group(1)) or {}
        for campo in ("titulo", "fecha"):
            if campo not in cab:
                error(f"noticias/{ruta.name}", f"falta el campo '{campo}:'.")
        noticias.append({**cab, "id": ruta.stem, "cuerpo": m.group(2)})
    noticias.sort(key=lambda n: str(n["fecha"]), reverse=True)
    return noticias


def enlaces(s):
    """Lista de (red, texto, url) con los perfiles rellenos en sitio.yml."""
    def campo(nombre):
        return str(s.get(nombre) or "").strip()
    candidatos = [
        ("correo", "Correo electrónico", "mailto:" + campo("correo") if campo("correo") else ""),
        ("inspire", "INSPIRE-HEP", f"https://inspirehep.net/authors/{campo('inspire')}" if campo("inspire") else ""),
        ("orcid", "ORCID", "https://orcid.org/" + campo("orcid") if campo("orcid") else ""),
        ("scholar", "Google Scholar", f"https://scholar.google.com/citations?user={campo('scholar')}" if campo("scholar") else ""),
        ("arxiv", "arXiv", f"https://arxiv.org/a/{campo('arxiv')}" if campo("arxiv") else ""),
        ("github", "GitHub", "https://github.com/" + campo("github") if campo("github") else ""),
        ("linkedin", "LinkedIn", "https://www.linkedin.com/in/" + campo("linkedin") if campo("linkedin") else ""),
        ("x", "X (Twitter)", "https://x.com/" + campo("x").lstrip("@") if campo("x") else ""),
    ]
    return [(red, texto, url) for red, texto, url in candidatos if url]


def comprobar(sitio, lineas, colaboraciones, trayectoria):
    for campo in ("nombre", "cargo", "correo"):
        if not sitio.get(campo):
            error("sitio.yml", f"falta el campo '{campo}:'.")
    foto = sitio.get("foto")
    if foto and not (RAIZ / "estatico/img/foto" / foto).exists():
        error("sitio.yml", f"no encuentro la foto estatico/img/foto/{foto}")
    diagramas = {"sabor", "g-2", "colisionador", "topologia"}
    for i, l in enumerate(lineas, 1):
        if not l.get("titulo"):
            error("investigacion.yml", f"la línea nº {i} no tiene 'titulo:'.")
        if l.get("diagrama") and l["diagrama"] not in diagramas:
            error("investigacion.yml", f"{l['titulo']}: el diagrama "
                  f"'{l['diagrama']}' no existe. Usa uno de: {', '.join(sorted(diagramas))}.")
    for c in colaboraciones:
        if not c.get("nombre") or not c.get("web"):
            error("colaboraciones.yml", "cada colaboración necesita 'nombre:' y 'web:'.")
        if c.get("logo") and not (RAIZ / "estatico/img/colaboraciones" / c["logo"]).exists():
            error("colaboraciones.yml", f"{c['nombre']}: no encuentro el logo "
                  f"estatico/img/colaboraciones/{c['logo']}")
    if not isinstance(trayectoria, list):
        error("trayectoria.yml", "debe ser una lista de etapas, cada una empezando por '- periodo:'.")
    for e in trayectoria:
        for x in [e] + (e.get("estancias") or []):
            if not x.get("periodo") or not x.get("titulo"):
                error("trayectoria.yml", "cada etapa y estancia necesita 'periodo:' y 'titulo:'.")
            x["periodo"] = str(x["periodo"])
            for campo in ("web", "detalle", "lugar"):
                x.setdefault(campo, None)
        e["estancias"] = e.get("estancias") or []
    for c in colaboraciones:
        c.setdefault("logo", None)
    for l in lineas:
        for campo in ("diagrama", "resumen", "texto", "temas"):
            l.setdefault(campo, None)


def traducir_contenido(d, tr):
    """Copia del contenido con los textos pasados por el traductor tr."""
    d = copy.deepcopy(d)
    for campo in ("cargo", "departamento", "universidad", "grupo", "direccion",
                  "lema", "presentacion"):
        d["sitio"][campo] = tr(d["sitio"].get(campo))
    for l in d["lineas"]:
        for campo in ("titulo", "resumen", "texto"):
            l[campo] = tr(l.get(campo))
        l["temas"] = [tr(x) for x in l.get("temas") or []]
    for e in d["trayectoria"]:
        for x in [e] + e["estancias"]:
            for campo in ("titulo", "lugar", "detalle"):
                x[campo] = tr(x.get(campo))
    for n in d["noticias"]:
        n["titulo"], n["cuerpo"] = tr(n["titulo"]), tr(n["cuerpo"])
    return d


def generar(idioma, tr, datos_es, comun):
    """Genera todas las páginas de un idioma. Devuelve la lista de páginas."""
    d = traducir_contenido(datos_es, tr)
    for n in d["noticias"]:
        n["html"] = md(n["cuerpo"])

    env = Environment(loader=FileSystemLoader(RAIZ / "plantillas"),
                      undefined=StrictUndefined, autoescape=True,
                      trim_blocks=True, lstrip_blocks=True)
    env.globals.update(recurso=recurso, t=tr, idioma=idioma, onda=onda, muelle=muelle)
    env.filters.update(md=md, md_linea=md_linea, fecha=lambda f: fecha_larga(f, idioma),
                       latex=latex_ligero, saltos=saltos)

    hoy = comun["hoy"]
    base = dict(sitio=d["sitio"], redes=comun["redes"], anio=hoy.year,
                actualizado=fecha_larga(hoy, idioma), **IDIOMAS[idioma],
                otro_idioma=("en/" if idioma == "es" else "../"))
    metricas = dict(comun["metricas"])
    if metricas.get("fecha"):
        metricas["fecha"] = fecha_larga(metricas["fecha"], idioma)
    paginas = {
        "index.html": dict(lineas=d["lineas"], noticias=d["noticias"][:3],
                           destacadas=comun["destacadas"], metricas=metricas,
                           evento=comun["evento"]),
        "investigacion.html": dict(lineas=d["lineas"],
                                   colaboraciones=comun["colaboraciones"]),
        "publicaciones.html": dict(apartados=comun["apartados"], metricas=metricas,
                                   temas=comun["temas"]),
        "trayectoria.html": dict(trayectoria=d["trayectoria"]),
        "noticias.html": dict(noticias=d["noticias"]),
        "contacto.html": dict(),
    }
    carpeta = SITE / IDIOMAS[idioma]["carpeta"]
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, datos in paginas.items():
        html = env.get_template(nombre).render(**base, **datos, pagina=nombre)
        (carpeta / nombre).write_text(html, encoding="utf-8")
    return list(paginas)


def main():
    sitio = leer_yaml("sitio.yml") or {}
    lineas = leer_yaml("investigacion.yml") or []
    colaboraciones = leer_yaml("colaboraciones.yml") or []
    trayectoria = leer_yaml("trayectoria.yml") or []
    opciones = leer_yaml("publicaciones.yml") or {}
    comprobar(sitio, lineas, colaboraciones, trayectoria)

    pub_json = RAIZ / "datos/publicaciones.json"
    publicaciones = json.loads(pub_json.read_text()) if pub_json.exists() else []
    excluir = set(opciones.get("excluir") or [])
    publicaciones = [preparar_publicacion(p, sitio["nombre"]) for p in publicaciones
                     if p.get("inspire") not in excluir]
    met_json = RAIZ / "datos/metricas.json"
    metricas = json.loads(met_json.read_text()) if met_json.exists() else {}

    apartados = []
    for clave, titulo, tipos in APARTADOS:
        lista = [p for p in publicaciones if p["tipo"] in tipos]
        if clave == "articulos":   # y todo lo que no encaje en otro apartado
            otros = {t for _, _, ts in APARTADOS for t in ts}
            lista += [p for p in publicaciones if p["tipo"] not in otros]
        por_anio = {}
        for p in sorted(lista, key=lambda p: p["anio"] or 0, reverse=True):
            por_anio.setdefault(p["anio"] or "Sin fecha", []).append(p)
        if lista:
            apartados.append(dict(clave=clave, titulo=titulo, por_anio=por_anio,
                                  total=len(lista)))
    por_id = {p["inspire"]: p for p in publicaciones}
    destacadas = [por_id[i] for i in opciones.get("destacadas") or [] if i in por_id]
    if not destacadas:
        destacadas = sorted(publicaciones, key=lambda p: -(p["citas"] or 0))[:4]
    usados = {p["tema"] for p in publicaciones}
    temas = [(c, n) for c, n, _ in TEMAS if c in usados]

    noticias = cargar_noticias()
    datos_es = dict(sitio=sitio, lineas=lineas, trayectoria=trayectoria,
                    noticias=noticias)

    if SITE.exists():
        shutil.rmtree(SITE)
    shutil.copytree(RAIZ / "estatico", SITE, ignore=shutil.ignore_patterns(".gitkeep"))
    (SITE / ".nojekyll").write_text("")   # GitHub Pages: servir tal cual

    comun = dict(colaboraciones=colaboraciones, apartados=apartados, temas=temas,
                 destacadas=destacadas, metricas=metricas, hoy=dt.date.today(),
                 redes=enlaces(sitio), evento=evento())
    trad = Traductor(RAIZ / "datos/traducciones.json", "en")
    for idioma in IDIOMAS:
        tr = trad if idioma == "en" else Traductor(None, "es")
        paginas = generar(idioma, tr, datos_es, comun)
    sin_traducir = trad.guardar()

    print(f"✅ Web generada en {SITE.relative_to(RAIZ)}/ "
          f"({len(paginas)} páginas en español y {len(paginas)} en inglés)")
    if sin_traducir and "--estricto" in sys.argv:
        sys.exit("❌ Las versiones en español e inglés no coinciden: faltan traducciones.")


if __name__ == "__main__":
    main()
