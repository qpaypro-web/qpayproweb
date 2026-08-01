#!/usr/bin/env python3
"""
Recupera las imágenes del cuerpo de los artículos y las inserta como bloques `img`.

La migración desde WordPress solo trajo la portada de cada artículo. Las imágenes
que iban dentro del texto se quedaron atrás, en parte porque el tema viejo las
metía como fondo de columna y no como contenido, así que no aparecen ni en el HTML
renderizado ni en los shortcodes que devuelve la API de contenido. Sí aparecen en
la biblioteca de medios, asociadas al post: de ahí salen.

Qué imagen va en qué artículo, con qué texto alternativo y en qué punto, está en
scripts/blog-imagenes.json. Este script solo ejecuta esa decisión.

    python3 scripts/imagenes-blog.py --descargar   # baja los archivos y los inserta
    python3 scripts/imagenes-blog.py --dry-run     # informa sin escribir

Es idempotente: una imagen ya insertada no se duplica.
"""

from __future__ import annotations  # el python del sistema es 3.9

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARTICULOS = RAIZ / 'src' / 'data' / 'blog-articles.json'
CONFIG = Path(__file__).resolve().parent / 'blog-imagenes.json'
DESTINO = RAIZ / 'public' / 'images' / 'blog'

# Más allá de esto no se gana nitidez en pantalla y sí se paga en peso.
ANCHO_MAX = 1600


def sin_html(s: str) -> str:
    import re
    return re.sub(r'<[^>]+>', '', s or '').strip()


def descargar(url: str, destino: Path) -> None:
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=90) as r:
        destino.write_bytes(r.read())


def encoger(ruta: Path, ancho: int, alto: int) -> tuple[int, int]:
    """sips viene con macOS; si no está, se deja la imagen tal cual."""
    if ancho <= ANCHO_MAX:
        return ancho, alto
    try:
        subprocess.run(
            ['sips', '-Z', str(ANCHO_MAX), str(ruta), '--out', str(ruta)],
            check=True, capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ancho, alto
    return ANCHO_MAX, round(alto * ANCHO_MAX / ancho)


def aligerar(ruta: Path) -> Path:
    """
    El WordPress guardó como PNG fotografías que pesan diez veces lo que deberían.
    Se pasan a JPEG cuando el ahorro es real. El canal alfa de esos PNG no se usa
    —son rectángulos opacos—, así que la conversión no cambia lo que se ve; si un
    PNG sí lo necesitara, el JPEG no comprimiría tanto y se descarta solo.
    """
    if ruta.suffix.lower() != '.png':
        return ruta
    jpg = ruta.with_suffix('.jpg')
    try:
        subprocess.run(
            ['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '80', str(ruta), '--out', str(jpg)],
            check=True, capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return ruta
    if jpg.exists() and jpg.stat().st_size < ruta.stat().st_size * 0.9:
        ruta.unlink()
        return jpg
    jpg.unlink(missing_ok=True)
    return ruta


def punto_de_insercion(body: list[dict], tras: str | None, usados: set) -> int:
    """
    Con `tras`, justo después del encabezado indicado. Sin él, después del primer
    párrafo que quede libre, repartiendo para que no se amontonen al inicio.
    """
    if tras:
        for i, b in enumerate(body):
            if b['type'] in ('h2', 'h3') and sin_html(b.get('text', '')).startswith(tras):
                j = i + 1
                while j < len(body) and body[j]['type'] == 'p':
                    return j + 1
                return i + 1
    parrafos = [i for i, b in enumerate(body) if b['type'] == 'p' and i not in usados]
    if not parrafos:
        return len(body)
    # Se salta el primero: la entradilla debe respirar antes de la primera imagen.
    return (parrafos[1] if len(parrafos) > 1 else parrafos[0]) + 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--descargar', action='store_true', help='baja los archivos que falten')
    ap.add_argument('--dry-run', action='store_true', help='informa sin escribir')
    args = ap.parse_args()

    cfg = json.loads(CONFIG.read_text(encoding='utf-8'))
    articulos = json.loads(ARTICULOS.read_text(encoding='utf-8'))
    por_slug = {a['slug']: a for a in articulos}
    DESTINO.mkdir(parents=True, exist_ok=True)

    insertadas = saltadas = 0
    for slug, imagenes in cfg.items():
        if slug.startswith('_'):
            continue
        art = por_slug.get(slug)
        if not art:
            print(f'  ! {slug}: no existe en el sitio nuevo, se ignora')
            continue

        body = art['body']
        # Se compara sin extensión: aligerar() puede haber convertido un PNG a
        # JPEG después de insertarlo, y volver a correr no debe duplicarlo.
        ya = {Path(b['src']).stem for b in body if b['type'] == 'img'}
        usados: set = set()
        nuevas = 0

        for n, img in enumerate(imagenes, 1):
            base = f'{slug[:60]}-{n}'
            if base in ya:
                saltadas += 1
                continue

            existentes = list(DESTINO.glob(f'{base}.*'))
            if existentes:
                ruta = existentes[0]
            else:
                if not args.descargar:
                    print(f'  ! falta {base} (correr con --descargar)')
                    continue
                ruta = DESTINO / f'{base}{Path(img["archivo"]).suffix.lower()}'
                descargar(img['origen'], ruta)

            w, h = encoger(ruta, img['w'], img['h'])
            ruta = aligerar(ruta)
            src = f'/images/blog/{ruta.name}'
            bloque = {'type': 'img', 'src': src, 'alt': img['alt'], 'w': w, 'h': h}
            if img.get('caption'):
                bloque['caption'] = img['caption']

            pos = punto_de_insercion(body, img.get('tras'), usados)
            body.insert(pos, bloque)
            usados.add(pos)
            usados = {i + 1 if i >= pos else i for i in usados}
            insertadas += 1
            nuevas += 1

        if nuevas:
            print(f'  {slug[:58]:<58} +{nuevas} imágenes')

    print(f'\ninsertadas: {insertadas} | ya estaban: {saltadas}')
    con_img = sum(1 for a in articulos if any(b['type'] == 'img' for b in a['body']))
    print(f'artículos con imágenes en el cuerpo: {con_img}/{len(articulos)}')

    if not args.dry_run:
        ARTICULOS.write_text(
            json.dumps(articulos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
        )
        print(f'escrito {ARTICULOS.relative_to(RAIZ)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
