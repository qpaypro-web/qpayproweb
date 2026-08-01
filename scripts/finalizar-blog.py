"""
Segundo paso de la migración del blog: normaliza los títulos, baja las portadas, genera las
que faltan, mezcla los artículos escritos a mano y escribe src/data/blog-articles.json.

    python3 scripts/finalizar-blog.py

Requiere haber corrido antes scripts/migrar-blog.py. Ver docs/BLOG.md.
"""
import json
import re
import subprocess
import unicodedata
from pathlib import Path

AQUI = Path(__file__).parent
REPO = AQUI.parent
DESTINO_IMG = REPO / 'public' / 'images' / 'blog'

# Erratas del WordPress que se corrigen al publicar.
ERRATAS = {
    'Mejoras en Qpayradar: El Sistema que Minimiza el Riesgo de Fraude en tu Negocio el Línea':
        'Mejoras en Qpayradar: el sistema que minimiza el riesgo de fraude en tu negocio en línea',
}

# Los títulos del WordPress mezclan dos estilos: los de 2025 vienen en Title Case inglés
# ("Checklist Para Lanzar Tu Tienda") y los anteriores en mayúscula inicial. El sitio nuevo usa
# mayúscula solo inicial en todos sus titulares, así que se normalizan a eso. Estos términos
# conservan su forma porque son nombres propios o marcas.
PROPIOS = [
    'Qpaypro', 'Qpayfel', 'Qpaycash', 'QPayVerify', 'Qpayradar', 'Qpayshop',
    'Qpayboost', 'Qpaybilling', 'Guatemala', 'El Salvador', 'Latinoamérica', 'Shopify',
    'WooCommerce', 'OpenCart', 'PrestaShop', 'VTEX', 'BAC Credomatic', 'Banco Atlántida',
    'SERFINSA', 'Guatevisión', 'San Valentín', 'Día del Cariño', 'Generación Z', 'Bitcoin',
    'Ethereum', 'Apple Pay', 'Google Pay', 'Visa', 'Mastercard',
    'Internet', 'IA', 'QR', 'POS', 'NFC',
]


def normalizar_titulo(t):
    t = ERRATAS.get(t, t)
    # el WordPress alterna "eCommerce" y "Ecommerce" en los títulos; el sitio usa una sola forma
    t = re.sub(r'\be-?commerce\b', 'ecommerce', t, flags=re.I)
    # se protege cada nombre propio con un marcador antes de bajar a minúsculas
    marcas = {}
    for i, p in enumerate(sorted(PROPIOS, key=len, reverse=True)):
        marca = f'\x00{i}\x00'
        patron = re.compile(rf'\b{re.escape(p)}\b', re.I)
        if patron.search(t):
            t = patron.sub(marca, t)
            marcas[marca] = p

    # Cada segmento del título —lo que va entre dos puntos, signos de pregunta o punto— baja a
    # minúsculas y recupera la mayúscula solo en su primera palabra.
    def arreglar(segmento):
        palabras = segmento.split(' ')
        for i, w in enumerate(palabras):
            if '\x00' in w:
                continue  # es un nombre propio protegido
            if re.fullmatch(r'[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+', w):
                palabras[i] = w.lower()
        for w in palabras:
            if not w:
                continue
            if '\x00' in w:
                break  # el segmento arranca con un nombre propio: ya trae su forma
            palabras[palabras.index(w)] = w[:1].upper() + w[1:]
            break
        return ' '.join(palabras)

    t = ''.join(
        parte if re.fullmatch(r'[:¿?!.]\s*', parte) else arreglar(parte)
        for parte in re.split(r'([:¿?!.]\s*)', t)
        if parte
    )

    for marca, p in marcas.items():
        t = t.replace(marca, p)
    return re.sub(r'\s+', ' ', t).strip()


def dimensiones(ruta):
    """Lee el ancho y el alto sin depender de librerías externas."""
    b = ruta.read_bytes()
    try:
        if b[:8] == b'\x89PNG\r\n\x1a\n':
            return int.from_bytes(b[16:20], 'big'), int.from_bytes(b[20:24], 'big')
        if b[:2] == b'\xff\xd8':
            i = 2
            while i < len(b) - 9:
                if b[i] != 0xFF:
                    i += 1
                    continue
                marcador = b[i + 1]
                if marcador in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB):
                    return int.from_bytes(b[i + 7:i + 9], 'big'), int.from_bytes(b[i + 5:i + 7], 'big')
                i += 2 + int.from_bytes(b[i + 2:i + 4], 'big')
        if b[:4] == b'RIFF' and b[8:12] == b'WEBP':
            if b[12:16] == b'VP8X':
                w = int.from_bytes(b[24:27], 'little') + 1
                h = int.from_bytes(b[27:30], 'little') + 1
                return w, h
            if b[12:16] == b'VP8 ':
                return (int.from_bytes(b[26:28], 'little') & 0x3FFF,
                        int.from_bytes(b[28:30], 'little') & 0x3FFF)
            if b[12:16] == b'VP8L':
                n = int.from_bytes(b[21:25], 'little')
                return (n & 0x3FFF) + 1, ((n >> 14) & 0x3FFF) + 1
    except Exception:
        pass
    return None, None


def dividir_lineas(texto, max_chars):
    lineas, actual = [], ''
    for palabra in texto.split():
        if len(actual) + len(palabra) + 1 <= max_chars:
            actual = f'{actual} {palabra}'.strip()
        else:
            lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas[:4]


def portada_generada(slug, titulo, categoria):
    """
    Portada de marca para los artículos cuya imagen ya no existe en el WordPress. Usa el
    degradado de las secciones oscuras del sitio en lugar de una foto de banco.
    """
    lineas = dividir_lineas(titulo, 30)
    alto_linea = 62
    y0 = 400 - (len(lineas) - 1) * alto_linea / 2
    textos = '\n'.join(
        f'    <text x="80" y="{y0 + i * alto_linea:.0f}" fill="#ffffff" font-size="46" '
        f'font-weight="700" font-family="Manrope, system-ui, sans-serif">'
        f'{l.replace("&", "&amp;").replace("<", "&lt;")}</text>'
        for i, l in enumerate(lineas)
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 800" width="1280" height="800" role="img">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f206c"/>
      <stop offset="100%" stop-color="#0097ce"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="800" fill="url(#g)"/>
  <circle cx="1120" cy="140" r="220" fill="#ffffff" opacity="0.06"/>
  <circle cx="1010" cy="700" r="160" fill="#ffffff" opacity="0.05"/>
  <text x="80" y="140" fill="#ffffff" opacity="0.6" font-size="22" font-weight="600"
        letter-spacing="6" font-family="Manrope, system-ui, sans-serif">QPAYPRO</text>
  <text x="80" y="196" fill="#4ad2ff" font-size="24" font-weight="600"
        font-family="Manrope, system-ui, sans-serif">{categoria}</text>
{textos}
</svg>
'''
    destino = DESTINO_IMG / f'{slug}.svg'
    destino.write_text(svg, encoding='utf-8')
    return f'/images/blog/{slug}.svg', 1280, 800


def main():
    DESTINO_IMG.mkdir(parents=True, exist_ok=True)
    articulos = json.load(open(AQUI / '.articulos.json'))

    manual_path = REPO / 'src' / 'data' / 'blog-manual.json'
    manuales = json.load(open(manual_path)) if manual_path.exists() else []

    categorias = json.load(open(REPO / 'src' / 'data' / 'blog-categorias.json'))
    nombre_cat = {c['slug']: c['name'] for c in categorias}

    bajadas, generadas = 0, 0
    for a in articulos + manuales:
        a['title'] = normalizar_titulo(a['title'])
        # Los encabezados del WordPress vienen en Title Case inglés igual que los títulos. El
        # sitio usa mayúscula solo inicial, así que se normalizan con el mismo criterio.
        for b in a['body']:
            if b['type'] in ('h2', 'h3'):
                b['text'] = normalizar_titulo(b['text'])
        url = a.get('cover', {}).get('wp')
        if url and not str(a['cover'].get('src', '')).startswith('/images'):
            ext = url.rsplit('.', 1)[1].lower()
            destino = DESTINO_IMG / f'{a["slug"]}.{ext}'
            if not destino.exists():
                subprocess.run(['curl', '-s', '-m', '40', '-o', str(destino), url], check=True)
                bajadas += 1
            w, h = dimensiones(destino)
            a['cover'] = {'src': f'/images/blog/{a["slug"]}.{ext}', 'alt': a['title'], 'w': w, 'h': h}
        elif not str(a.get('cover', {}).get('src', '')).startswith('/images'):
            src, w, h = portada_generada(a['slug'], a['title'], nombre_cat.get(a['cats'][0], ''))
            a['cover'] = {'src': src, 'alt': a['title'], 'w': w, 'h': h}
            generadas += 1
        else:
            a['cover'].setdefault('alt', a['title'])

    todos = articulos + manuales
    todos.sort(key=lambda a: a['date'], reverse=True)
    json.dump(todos, open(REPO / 'src' / 'data' / 'blog-articles.json', 'w'),
              ensure_ascii=False, indent=2)

    print(f'artículos publicados: {len(todos)}  (convertidos {len(articulos)} + a mano {len(manuales)})')
    print(f'portadas descargadas: {bajadas}   generadas: {generadas}')
    faltan = [a['slug'] for a in todos if not a['cover']['w']]
    if faltan:
        print(f'portadas sin dimensiones legibles: {faltan}')


if __name__ == '__main__':
    main()
