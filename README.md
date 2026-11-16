# Web personal · Fernando Cornet-Gómez

https://fcornetgomez.github.io/ · versión en inglés en `en/`

Web estática (HTML y CSS generados con Python), con el mismo sistema que la web
del grupo [FQM-429 (ACP)](https://www.uco.es/investiga/grupos/acp/).

- **¿Cambiar el contenido?** Lee [`contenido/LEEME.md`](contenido/LEEME.md).
- **¿Cómo se publica?** Sola, con GitHub Actions al guardar en `main` y cada lunes
  (`.github/workflows/publicar.yml`), en GitHub Pages.
- **Publicaciones y citas**: se descargan de INSPIRE-HEP (`scripts/publicaciones.py`).
- **Inglés**: se genera a la vez con las traducciones de `datos/traducciones.json`.
  `python scripts/construir.py --estricto` falla si falta alguna.

## Trabajar en local

```bash
pip install -r requirements.txt
python scripts/publicaciones.py      # descarga publicaciones y citas
python scripts/construir.py          # genera _site/
python -m http.server -d _site 8000  # vista previa: http://localhost:8000
```
