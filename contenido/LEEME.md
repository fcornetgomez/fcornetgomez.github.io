# Cómo editar la web

Todo el contenido está en esta carpeta `contenido/`. Se puede editar desde la
propia web de GitHub (lápiz ✏️ → **Commit changes**); en un par de minutos la web
se actualiza sola.

| Quiero…                                   | Archivo                         |
|-------------------------------------------|---------------------------------|
| Cambiar cargo, correo, bio, perfiles      | `sitio.yml`                     |
| Cambiar las líneas de investigación       | `investigacion.yml`             |
| Añadir un puesto, título o docencia       | `trayectoria.yml`               |
| Publicar una noticia                      | archivo nuevo en `noticias/`    |
| Añadir una colaboración                   | `colaboraciones.yml`            |
| Elegir las publicaciones destacadas u ocultar alguna | `publicaciones.yml`  |
| Cambiar la foto                           | `estatico/img/foto/` y `sitio.yml` |

## Reglas de oro

1. Respeta los espacios del principio de cada línea: copia un bloque que ya
   exista y cambia solo el texto.
2. Lo que va detrás de `#` es un comentario.
3. Las fechas se escriben `AAAA-MM-DD`.
4. Si algo está mal escrito, la web **no** se rompe: la publicación se detiene y
   GitHub avisa por correo con el error en español.

## Noticias

Crea `noticias/AAAA-MM-DD-titulo-corto.md`:

```
---
titulo: Charla en el CERN
fecha: 2026-12-03
---

Texto de la noticia, con **negritas**, *cursivas* y [enlaces](https://home.cern).
```

## Publicaciones

Se descargan solas de INSPIRE-HEP cada lunes y en cada cambio. Las citas y el
índice h también. En `publicaciones.yml` se eligen las destacadas de la portada
(por su número de INSPIRE).

## Inglés

Solo se edita en español. Los textos nuevos salen en español en la versión
inglesa hasta que se añada su traducción en `datos/traducciones.json`.
