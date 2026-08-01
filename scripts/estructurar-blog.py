#!/usr/bin/env python3
"""
Repara la estructura de los artículos migrados del WordPress.

La migración trajo el texto pero perdió la jerarquía: los títulos de sección
quedaron como párrafos en negrita, las citas quedaron partidas en tres bloques y
varios encabezados quedaron con el número y sin el nombre. El resultado es que la
mayoría de artículos no tenía ni un solo `h2`, y el índice lateral del artículo
—que se arma con los h2— no aparecía en ninguno.

Este script no escribe contenido: solo reinterpreta bloques que ya existen,
usando las marcas que el propio texto dejó. Es idempotente; volver a correrlo
sobre un archivo ya reparado no lo cambia.

    python3 scripts/estructurar-blog.py            # aplica y reescribe el JSON
    python3 scripts/estructurar-blog.py --dry-run  # solo informa

Las imágenes se agregan aparte, con scripts/imagenes-blog.py.
"""

from __future__ import annotations  # el python del sistema es 3.9

import argparse
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARTICULOS = RAIZ / 'src' / 'data' / 'blog-articles.json'

# "Indicó hugo garcía", "Concluyó Hugo García", "Dijo hugo garcia"…
VERBOS = r'(?:indic[oó]|concluy[oó]|dijo|afirm[oó]|se[ñn]al[oó]|agreg[oó]|coment[oó]|expres[oó])'
ATRIBUCION = re.compile(rf'^\s*{VERBOS}\s+hugo\s+garc[ií]a\s*$', re.I)
CARGO = re.compile(r'^\s*CEO\s*[–-]\s*Qpaypro\s*$', re.I)

# Un párrafo que es únicamente un título en negrita: "<strong>Acerca de Qpaypro:</strong>"
SOLO_NEGRITA = re.compile(r'^\s*<strong>\s*(.+?)\s*</strong>\s*$', re.S)

# "<strong>1. Mejora tu presencia en línea:</strong> El resto del párrafo…"
TITULO_NUMERADO = re.compile(
    r'^\s*<strong>\s*(\d+)\s*\.\s*</strong>\s*<strong>\s*(.+?)\s*:?\s*</strong>\s*(.*)$'
    r'|^\s*<strong>\s*(\d+)\s*\.\s*(.+?)\s*:\s*</strong>\s*(.*)$',
    re.S,
)

# Encabezado que quedó solo con el número: "1." / "2."
SOLO_NUMERO = re.compile(r'^\s*(\d+)\s*\.?\s*$')

VINETA = re.compile(r'^\s*[•·▪]\s*(.+)$', re.S)


def sin_html(s: str) -> str:
    return re.sub(r'<[^>]+>', '', s or '').strip()


def primer_negrita(texto: str) -> str | None:
    """El primer <strong> del párrafo: el nombre de la herramienta o del apartado."""
    m = re.search(r'<strong>\s*(.+?)\s*</strong>', texto or '', re.S)
    return sin_html(m.group(1)) if m else None


def regla_citas(body: list[dict]) -> tuple[list[dict], int]:
    """
    Une la cita partida en tres bloques —párrafo entrecomillado, encabezado con la
    atribución y una línea con el cargo— en un solo bloque `quote`.
    """
    salida, cambios, i = [], 0, 0
    while i < len(body):
        b = body[i]
        es_encabezado = b['type'] in ('h2', 'h3') and ATRIBUCION.match(sin_html(b.get('text', '')))
        if es_encabezado and salida and salida[-1]['type'] == 'p':
            cita = salida[-1].get('text', '').strip()
            # El WordPress las guardó en minúsculas ("indicó hugo garcía"): el
            # verbo va en minúscula porque continúa la frase, pero el nombre no.
            atribucion = re.sub(
                r'hugo\s+garc[ií]a', 'Hugo García', sin_html(b['text']).lower(), flags=re.I
            )

            salto = 1
            cargo = ''
            if i + 1 < len(body) and body[i + 1]['type'] == 'p' and CARGO.match(sin_html(body[i + 1].get('text', ''))):
                cargo = ', CEO de Qpaypro'
                salto = 2

            cita = cita.rstrip()
            if cita.endswith(('.', '”', '"')):
                cita = cita.rstrip('.')
            salida[-1] = {'type': 'quote', 'text': f'{cita}, {atribucion}{cargo}.'}
            cambios += 1
            i += salto
            continue
        salida.append(b)
        i += 1
    return salida, cambios


def regla_encabezados_numerados(body: list[dict]) -> tuple[list[dict], int]:
    """Un h3 que dice solo «1.» toma el nombre del párrafo que le sigue."""
    salida, cambios = list(body), 0
    for i, b in enumerate(salida):
        if b['type'] not in ('h2', 'h3'):
            continue
        m = SOLO_NUMERO.match(sin_html(b.get('text', '')))
        if not m or i + 1 >= len(salida) or salida[i + 1]['type'] != 'p':
            continue
        nombre = primer_negrita(salida[i + 1].get('text', ''))
        if nombre and len(nombre) < 60:
            salida[i] = {**b, 'text': f'{m.group(1)}. {nombre}'}
            cambios += 1
    return salida, cambios


def nivel_para(body: list[dict]) -> str:
    """
    Un artículo que ya tiene secciones no necesita más: lo que se promueve dentro
    de ellas son subsecciones. Sin esto, un artículo con diez apartados terminaba
    con veintiún encabezados y un índice lateral inservible.
    """
    return 'h3' if any(b['type'] == 'h2' for b in body) else 'h2'


def regla_titulos_en_negrita(body: list[dict], nivel: str) -> tuple[list[dict], int]:
    """
    Párrafos que en realidad eran títulos de sección. Dos formas:
      «<strong>Acerca de Qpaypro:</strong>»            -> encabezado
      «<strong>1. Mejora tu presencia:</strong> texto» -> encabezado + párrafo
    """
    salida, cambios = [], 0
    for b in body:
        if b['type'] != 'p':
            salida.append(b)
            continue
        texto = (b.get('text') or '').strip()

        m = TITULO_NUMERADO.match(texto)
        if m:
            titulo = (m.group(2) or m.group(5) or '').strip().rstrip(':')
            resto = (m.group(3) or m.group(6) or '').strip()
            if titulo and len(sin_html(titulo)) < 80:
                salida.append({'type': nivel, 'text': sin_html(titulo)})
                if resto:
                    salida.append({'type': 'p', 'text': resto})
                cambios += 1
                continue

        m = SOLO_NEGRITA.match(texto)
        if m:
            titulo = sin_html(m.group(1)).rstrip(':')
            # Un título es corto y no termina en punto: si no, es un párrafo que
            # el editor puso todo en negrita y debe seguir siendo párrafo.
            if titulo and len(titulo) < 70 and not titulo.endswith('.') and ' ' in titulo:
                salida.append({'type': nivel, 'text': titulo})
                cambios += 1
                continue

        salida.append(b)
    return salida, cambios


def regla_listas_de_un_titulo(body: list[dict], nivel: str) -> tuple[list[dict], int]:
    """Una lista de un solo elemento que es solo un título en negrita era un encabezado."""
    salida, cambios = [], 0
    for b in body:
        if b['type'] in ('ul', 'ol') and len(b.get('items') or []) == 1:
            m = SOLO_NEGRITA.match(b['items'][0].strip())
            if m:
                titulo = sin_html(m.group(1)).rstrip(':')
                if titulo and len(titulo) < 70:
                    salida.append({'type': nivel, 'text': titulo})
                    cambios += 1
                    continue
        salida.append(b)
    return salida, cambios


def regla_vinetas_sueltas(body: list[dict]) -> tuple[list[dict], int]:
    """Párrafos consecutivos que empiezan con «•» son una lista."""
    salida, cambios, i = [], 0, 0
    while i < len(body):
        b = body[i]
        if b['type'] == 'p' and VINETA.match(b.get('text', '')):
            items, j = [], i
            while j < len(body) and body[j]['type'] == 'p' and VINETA.match(body[j].get('text', '')):
                items.append(VINETA.match(body[j]['text']).group(1).strip())
                j += 1
            if len(items) >= 2:
                salida.append({'type': 'ul', 'items': items})
                cambios += 1
                i = j
                continue
        salida.append(b)
        i += 1
    return salida, cambios


NOMBRES = [
    'citas partidas',
    'encabezados sin nombre',
    'títulos en negrita',
    'listas de un título',
    'viñetas sueltas',
]


def reparar(body: list[dict]) -> tuple[list[dict], list[int]]:
    """
    El orden importa. Las citas van primero porque quitan encabezados falsos, y
    el nivel de los encabezados que se promueven se decide una sola vez después
    de eso: si se recalculara entre reglas, los apartados de un mismo artículo
    quedarían repartidos entre h2 y h3 según el orden en que se procesaran.
    """
    cuenta = []
    body, n = regla_citas(body); cuenta.append(n)
    body, n = regla_encabezados_numerados(body); cuenta.append(n)
    nivel = nivel_para(body)
    body, n = regla_titulos_en_negrita(body, nivel); cuenta.append(n)
    body, n = regla_listas_de_un_titulo(body, nivel); cuenta.append(n)
    body, n = regla_vinetas_sueltas(body); cuenta.append(n)
    return body, cuenta


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true', help='informa sin escribir')
    args = ap.parse_args()

    articulos = json.loads(ARTICULOS.read_text(encoding='utf-8'))
    total = {nombre: 0 for nombre in NOMBRES}
    tocados = 0

    for art in articulos:
        body = art['body']
        antes_h2 = sum(1 for b in body if b['type'] == 'h2')
        body, cuenta = reparar(body)
        for nombre, n in zip(NOMBRES, cuenta):
            total[nombre] += n
        cambio_articulo = sum(cuenta)
        if cambio_articulo:
            tocados += 1
            despues_h2 = sum(1 for b in body if b['type'] == 'h2')
            print(f'  {art["slug"][:58]:<58} h2 {antes_h2} -> {despues_h2}  ({cambio_articulo} cambios)')
        art['body'] = body

    print(f'\nartículos tocados: {tocados}/{len(articulos)}')
    for nombre, n in total.items():
        print(f'  {nombre:<24} {n}')

    con_indice = sum(1 for a in articulos if sum(1 for b in a['body'] if b['type'] == 'h2') >= 3)
    print(f'\ncon índice lateral (3+ h2): {con_indice}/{len(articulos)}')

    if not args.dry_run:
        ARTICULOS.write_text(
            json.dumps(articulos, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'
        )
        print(f'\nescrito {ARTICULOS.relative_to(RAIZ)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
