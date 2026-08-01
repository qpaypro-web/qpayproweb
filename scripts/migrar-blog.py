"""
Convierte los posts del WordPress de qpaypro.com al formato de bloques del sitio nuevo.

    python3 scripts/migrar-blog.py --descargar   # vuelve a bajar la API y revisa las imágenes
    python3 scripts/migrar-blog.py               # convierte con lo ya descargado

Escribe scripts/.articulos.json y scripts/.no-migrados.json. Ver docs/BLOG.md.

Decisiones que toma este script y por qué:

- Solo migra los artículos de 2022 en adelante. Los anteriores citan tasas y políticas que hoy
  contradicen las páginas de precios, así que se resuelven con un 301 al índice del blog en
  lugar de publicarse desactualizados.
- Los 5 posts de demostración de la plantilla (Essentials/pixfort) quedan fuera. Los slugs que
  terminan en -copy NO son duplicados: son artículos reales a los que nunca les corrigieron la
  URL, así que se migran con un slug correcto y la URL vieja se redirige.
- Las imágenes intercaladas en el texto están todas caídas en el propio WordPress, así que se
  descartan sus etiquetas en lugar de dejar huecos.
- El HTML en línea se reduce a strong, em y a. Todo lo demás se aplana a texto: los estilos del
  WordPress no tienen nada que ver con la tipografía del sitio nuevo.
- Las categorías se asignan por contenido, no por las etiquetas del WordPress, que dejaban
  "Ecommerce" con el 84% de los artículos.
"""
import html
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

AQUI = Path(__file__).parent
POSTS = AQUI / '.wp-posts.json'
IMGS = AQUI / '.img-estado.txt'
API = 'https://www.qpaypro.com/wp-json/wp/v2/posts?per_page=100&_embed'

DEMOS = {
    'say-salut-to-the-most-advanced-theme',
    'its-time-to-say-hello-to-essentials-theme',
    'create-fast-and-cool-websites-like-a-pro',
    'add-multiple-languages-to-your-site',
    'hello-world-this-is-essentials-theme',
}

# Artículos que quedaron con la URL de otro post en el WordPress. Se les da un slug que
# corresponde a su título y la URL vieja se redirige a la nueva.
SLUG_CORREGIDO = {
    'errores-comunes-en-el-ecommerce-y-como-evitarlos': 'qpayfel-facturacion-electronica-guatemala',
    'maximizar-ventas-en-temporadas-de-festividades-copy-copy': 'errores-comunes-en-ecommerce-y-como-evitarlos',
    'san-valentin-una-fecha-rentable-para-el-comercio-copy': 'economia-y-ecommerce-dia-del-carino-entrevista-guatevision',
    'san-valentin-una-fecha-rentable-para-el-comercio-copy-copy': 'comercio-electronico-sostenible',
}

# Artículos de 2022 o posteriores que igual no se publican, porque afirman precios, tasas o
# planes que hoy contradicen las páginas de precios del sitio. Es el mismo criterio con el que
# se dejaron fuera los anteriores a 2022: un artículo que anuncia una tarifa vieja como si fuera
# la vigente desinforma al cliente. Se resuelven con un 301 al índice del blog.
EXCLUIDOS = {
    'nuevos-cambios-en-politicas-tasas-e-impuestos':
        'anuncia la tasa de 4.02% + Q2.43, superada por la de 5% / 4.50% + Q2.95',
    'qpaypro-impulsa-el-emprendimiento-en-el-pais-con-su-modelo-de-negocio-innovador':
        'promociona el Plan Starter de Q50.00 al mes, que ya no existe',
    'mejoras-qpayradar':
        'anuncia un costo de Q2.43 por validación; en la tabla de precios QpayRadar va incluido',
}

CATEGORIAS = {
    'pagos': 'Pagos y cobros',
    'ecommerce': 'Ecommerce y tienda en línea',
    'seguridad': 'Seguridad y fraude',
    'marketing': 'Marketing y ventas',
    'producto': 'Producto Qpaypro',
    'guias': 'Guías y cómo empezar',
}

# Señales por categoría, para los artículos que no estén en CATEGORIA_FIJA. El título pesa el
# triple que el cuerpo porque es lo que declara el tema.
SENALES = {
    'pagos': r'pago|cobr|tarjeta de cr[ée]dito|d[ée]bito|transferencia|efectivo|cuota|'
             r'criptomoneda|bitcoin|c[óo]digo qr|\bqr\b|pasarela|liquidaci[óo]n|donaci[óo]n',
    'ecommerce': r'ecommerce|e-commerce|comercio electr[óo]nico|tienda en l[íi]nea|tienda online|'
                 r'marketplace|carrito|env[íi]o|inventario|cat[áa]logo',
    'seguridad': r'segurid|fraude|estafa|phishing|ciberseguridad|tokeniza|3ds|certificaci[óo]n|'
                 r'pci|privacidad|sitios falsos|riesgo|qpayradar|qpayverify|confianza',
    'marketing': r'marketing|venta|redes sociales|campa[ñn]a|conversi[óo]n|fideliza|'
                 r'retenci[óo]n|lead|personalizaci[óo]n|generaci[óo]n z|consumidor|temporada|'
                 r'san valent[íi]n|festividad',
    'producto': r'qpaypro|qpayfel|qpaycash|qpayboost|qpaybilling|qpayshop|lanzamiento|'
                r'alianza|actualizaci[óo]n|integraci[óo]n con|plug-?in|bac credomatic|'
                r'banco atl[áa]ntida|serfinsa|entrevista',
    'guias': r'gu[íi]a|c[óo]mo empezar|paso a paso|checklist|mitos|tutorial|aprende|'
             r'automatiza|principiantes|c[óo]mo definir|c[óo]mo elegir',
}

# Asignación revisada a mano sobre la tabla completa. La primera categoría es la principal.
CATEGORIA_FIJA = {
    'alianzaelsalvador': ['producto'],
    'qpayfel-facturacion-electronica-guatemala': ['producto'],
    'qpaychas-pagos-en-efectivo': ['producto', 'pagos'],
    'integracion-con-shopify': ['producto', 'ecommerce'],
    'mejoras-qpayradar': ['producto', 'seguridad'],
    'implementacion-qpayverify': ['producto', 'seguridad'],
    'horarios-servicio-cliente-ampliados': ['producto'],
    'qpaypro-busca-modernizarse-estar-a-la-vanguardia-de-la-tecnologia': ['producto'],
    'qpaypro-impulsa-el-emprendimiento-en-el-pais-con-su-modelo-de-negocio-innovador': ['producto'],
    'qpaypro-y-bac-credomatic-aliados-al-servicio-de-los-guatemaltecos': ['producto'],
    'nuevos-cambios-en-politicas-tasas-e-impuestos': ['producto', 'pagos'],
    'conoce-las-nuevas-actualizaciones-y-plantillas-de-pago': ['producto', 'pagos'],
    'soluciones-inteligentes-respaldan-crecimiento-empresarial': ['producto'],
    'qpayboost-un-acelerador-para-tu-emprendimiento': ['producto'],
    'aprende-a-identificar-sitios-falsos-en-internet': ['seguridad'],
    'optimizacion-de-la-seguridad-y-privacidad-de-los-usuarios-mediante-la-tecnologia-de-pagos-en-linea': ['seguridad'],
    'respaldo-y-certificaciones-generan-transacciones-seguras': ['seguridad'],
    'compra-y-paga-en-linea-de-forma-segura': ['seguridad', 'pagos'],
    'relevancia-critica-de-la-ciberseguridad-en-el-comercio-electronico': ['seguridad', 'ecommerce'],
    'importancia-de-los-pagos-electronicos-seguros': ['seguridad', 'pagos'],
    'tokenizacion-y-codigo-qr-tecnologia-de-vanguardia-para-pagos-en-linea': ['seguridad', 'pagos'],
    'checklist-para-lanzar-tu-tienda-online-sin-fallar-en-el-intento': ['guias', 'ecommerce'],
    'automatiza-tu-negocio-sin-perder-el-control-guia-para-principiantes': ['guias'],
    'temporadas-altas-sin-perdidas-la-guia-para-cobrar-sin-errores': ['guias', 'marketing'],
    'mitos-que-estan-frenando-el-crecimiento-de-tu-negocio-digital': ['guias'],
    'mitos-y-realidades-sobre-las-compras-en-linea': ['guias', 'ecommerce'],
    'como-elegir-las-fotografias-de-productos-para-tu-tienda-en-linea': ['guias', 'ecommerce'],
    'como-generar-confianza-en-linea-sin-tener-una-gran-marca': ['guias', 'seguridad'],
    'quieres-vender-tus-productos-o-servicios-en-ecommerce': ['guias', 'ecommerce'],
    'ventajas-de-utilizar-sistemas-de-cobro-automatico': ['pagos'],
    'beneficios-de-hacer-pagos-en-linea': ['pagos'],
    'innovacion-en-recepcion-de-pagos-con-codigo-qr': ['pagos'],
    'criptomonedas': ['pagos'],
    'relacion-entre-las-criptomonedas-y-el-comercio-electronico': ['pagos', 'ecommerce'],
    'tendencias-pagos-digitales': ['pagos'],
    'pagos-digitales-el-aliado-silencioso-para-hacer-crecer-tu-negocio': ['pagos'],
    'estrategias-abandono-de-carrito-en-linea': ['marketing', 'ecommerce'],
    'aumentar-retencion-clientes-en-linea': ['marketing', 'ecommerce'],
    'maximizar-ventas-en-temporadas-de-festividades': ['marketing', 'ecommerce'],
    'san-valentin-una-fecha-rentable-para-el-comercio': ['marketing'],
    'economia-y-ecommerce-dia-del-carino-entrevista-guatevision': ['marketing'],
    'descubre-las-tendencias-de-consumo-de-la-generacion-z': ['marketing'],
    'uso-del-dinero-por-parte-del-consumidor-latinoamericano-moderno': ['marketing'],
    'la-estrategia-de-personalizacion-en-la-experiencia-de-compra-para-impulsar-las-ventas-en-linea': ['marketing', 'ecommerce'],
    'ventajas-de-personalizar-la-experiencia-del-cliente-en-el-comercio-electronico': ['marketing', 'ecommerce'],
    '5-consejos-para-aumentar-las-ventas-en-linea': ['marketing'],
    '5-cosas-que-puedes-hacer-para-cerrar-mas-ventas-en-tu-pagina-web': ['marketing'],
    '8-inteligencias-artificiales-que-te-ayudaran': ['marketing'],
    'tu-sitio-web-esta-vendiendo-menos-estas-senales-podrian-ser-la-razon': ['marketing', 'ecommerce'],
    'errores-comunes-en-ecommerce-y-como-evitarlos': ['ecommerce'],
    'evolucion-ecommerce': ['ecommerce'],
    'experiencia-en-tu-tienda-en-linea': ['ecommerce'],
    'claves-para-lograr-un-comercio-electronico-exitoso': ['ecommerce'],
    'diferencias-entre-ecommerce-y-marketplace': ['ecommerce'],
    'las-metricas-mas-importantes-del-ecommerce-en-guatemala': ['ecommerce'],
    'comercio-electronico-sostenible': ['ecommerce'],
    'maximizar-ventas': ['ecommerce', 'marketing'],
    'tendencias-que-estan-transformando-el-ecommerce-en-latinoamerica': ['ecommerce'],
}


# Los enlaces que los artículos hacen al sitio viejo. Reescribir el prefijo a ciegas dejaba
# rutas inexistentes: /payments/ es hoy la pasarela de pagos y /qpayshop-vende24hrs/ ya estaba
# caído en el propio WordPress. Lo que no esté aquí se reporta al final en lugar de romperse.
ENLACES_VIEJOS = {
    'https://www.qpaypro.com/': '/gt',
    'https://www.qpaypro.com/payments/': '/gt/pasarela-de-pagos',
    'https://www.qpaypro.com/qpayshop-vende24hrs/': '/gt/tiendas-en-linea',
    'https://www.qpaypro.com/planes-y-precios-de-pasarela-de-pagos-en-guatemala/': '/gt/precios',
    'https://www.qpaypro.com/contacto-ventas-qpaypro/': '/gt/contacto',
    'https://www.qpaypro.com/seguridad-en-pagos-digitales/': '/gt/seguridad',
    'https://www.qpaypro.com/sobre-qpaypro/': '/gt/sobre-qpaypro',
    'https://www.qpaypro.com/blog-de-pasarela-pagos-digitales/': '/gt/blog',
}
SIN_MAPEAR = set()

# Bloques iniciales que en el WordPress están copiados de otro artículo. En "Temporadas altas
# sin pérdidas" los dos primeros párrafos son el intro de "Tendencias que están transformando el
# ecommerce en Latinoamérica"; el contenido propio empieza en el primer encabezado.
INTRO_AJENO = {'temporadas-altas-sin-perdidas-la-guia-para-cobrar-sin-errores': 2}


def texto_plano(s):
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()


def limpiar_titulo(s):
    return re.sub(r'\s+', ' ', texto_plano(s).replace('–', '—')).strip()


def slugificar(s):
    s = unicodedata.normalize('NFKD', s.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s).strip('-'))[:70].strip('-')


def limpiar_inline(s):
    """Deja solo el formato en línea que el sitio nuevo sabe renderizar."""
    s = re.sub(r'<br\s*/?>', ' ', s)
    s = re.sub(r'<(?!/?(?:strong|b|em|i|a)\b)[^>]*>', '', s)
    s = re.sub(r'<a\b[^>]*?href="([^"]*)"[^>]*>', lambda m: f'<a href="{m.group(1)}">', s)
    s = re.sub(r'<a\b(?![^>]*href)[^>]*>', '', s)
    s = re.sub(r'<(b|i)\b[^>]*>', lambda m: '<strong>' if m.group(1) == 'b' else '<em>', s)
    s = re.sub(r'</(b|i)>', lambda m: '</strong>' if m.group(1) == 'b' else '</em>', s)
    s = re.sub(r'<(strong|em)\b[^>]*>', r'<\1>', s)
    s = html.unescape(s)

    def enlace(m):
        url = m.group(1).replace('https://qpaypro.com/', 'https://www.qpaypro.com/')
        if url.startswith('https://www.qpaypro.com/'):
            destino = ENLACES_VIEJOS.get(url)
            if destino is None:
                SIN_MAPEAR.add(url)
                destino = '/gt'
            return f'<a href="{destino}">'
        return m.group(0)

    s = re.sub(r'<a href="([^"]+)">', enlace, s)
    s = re.sub(r'<(strong|em)>\s*</\1>', '', s)
    return re.sub(r'\s+', ' ', s).strip()


EMOJI = re.compile(
    '[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF\uFE0F\u200d]'
)


def limpiar_encabezado(s):
    """
    Un encabezado ya viene destacado por estilo, así que no lleva negrita ni cursiva dentro.
    También se quitan los emoji decorativos que usaba el WordPress: el resto del sitio no usa
    ninguno y en un titular de 28px se ven fuera de lugar.
    """
    s = re.sub(r'</?(strong|em)>', '', limpiar_inline(s))
    s = re.sub(r'\s+', ' ', EMOJI.sub('', s)).strip(' –—-:·')
    # el WordPress dejó comillas angulares delante de los encabezados numerados
    return re.sub(r'^[»«▸▶●•]+\s*', '', s).strip()


def a_bloques(contenido):
    c = re.sub(r'<!--.*?-->', '', contenido, flags=re.S)
    c = re.sub(r'<(script|style|noscript)\b.*?</\1>', '', c, flags=re.S | re.I)
    # las imágenes del cuerpo están caídas en el WordPress: se descartan
    c = re.sub(r'<(img|figure|picture|svg)\b.*?(?:</(?:figure|picture|svg)>|/?>)', '', c, flags=re.S | re.I)
    c = re.sub(r'<iframe\b.*?</iframe>', '', c, flags=re.S | re.I)

    bloques = []
    patron = re.compile(
        r'<(h[1-6])\b[^>]*>(.*?)</\1>|<(p)\b[^>]*>(.*?)</\3>|<(ul|ol)\b[^>]*>(.*?)</\5>|'
        r'<(blockquote)\b[^>]*>(.*?)</\7>',
        re.S | re.I,
    )
    for m in patron.finditer(c):
        if m.group(1):
            t = limpiar_encabezado(m.group(2))
            if t:
                bloques.append({'type': f'_h{m.group(1)[1]}', 'text': t})
        elif m.group(3):
            t = limpiar_inline(m.group(4))
            if t:
                bloques.append({'type': 'p', 'text': t})
        elif m.group(5):
            items = [x for x in (limpiar_inline(i) for i in
                                 re.findall(r'<li\b[^>]*>(.*?)</li>', m.group(6), re.S | re.I)) if x]
            if items:
                bloques.append({'type': 'ol' if m.group(5).lower() == 'ol' else 'ul', 'items': items})
        elif m.group(7):
            t = limpiar_inline(m.group(8))
            if t:
                bloques.append({'type': 'quote', 'text': t})

    # Los niveles se resuelven por artículo: el más superficial que use ese artículo pasa a h2
    # y el siguiente a h3, sin importar si en el WordPress eran h2 y h3 o h5 y h6. Así ningún
    # artículo publica un h3 sin su h2.
    encabezados = [int(b['type'][2:]) for b in bloques if b['type'].startswith('_h')]
    niveles = sorted(set(encabezados))
    # Solo se conservan dos niveles si el artículo empieza por el más superficial. Cuando el
    # WordPress alterna niveles sin orden, mantener la distinción produce un h3 antes del primer
    # h2, que es jerarquía inválida: en ese caso todo queda en h2.
    if encabezados and encabezados[0] == niveles[0]:
        mapa = {n: ('h2' if i == 0 else 'h3') for i, n in enumerate(niveles)}
    else:
        mapa = {n: 'h2' for n in niveles}
    for b in bloques:
        if b['type'].startswith('_h'):
            b['type'] = mapa[int(b['type'][2:])]

    # Algunos posts traen dentro del contenido los widgets del pie de la página maquetados con
    # Visual Composer. Se corta desde el primero que aparezca: nada de eso es del artículo.
    PIE = re.compile(r'contacto pbx|env[íi]anos un mail|email@site\.com|'
                     r'escr[íi]benos por whatsapp|2355-6000', re.I)
    for i, b in enumerate(bloques):
        if PIE.search(b.get('text', '') or ' '.join(b.get('items', []))):
            bloques = bloques[:i]
            break

    # Dos encabezados seguidos no se colapsan: un encabezado de sección seguido del primero de
    # sus apartados es estructura legítima, y descartar uno borraba contenido —hacía que una
    # lista numerada del artículo empezara en "2."—.
    while bloques and bloques[-1]['type'].startswith('h'):
        bloques.pop()  # un encabezado al final no encabeza nada
    return bloques


def palabras(bloques):
    n = 0
    for b in bloques:
        n += len(texto_plano(b.get('text', '')).split())
        n += sum(len(texto_plano(i).split()) for i in b.get('items', []))
    return n


def extracto(bloques):
    """
    Sale del primer párrafo del propio artículo. El campo excerpt del WordPress no sirve: los
    resúmenes están cruzados entre posts, con el mismo texto repetido en artículos distintos.
    """
    base = texto_plano(next((b['text'] for b in bloques if b['type'] == 'p'), ''))
    if len(base) > 185:
        base = base[:185].rsplit(' ', 1)[0].rstrip('.,;:') + '…'
    return base


def clasificar(slug, titulo, cuerpo):
    if slug in CATEGORIA_FIJA:
        return CATEGORIA_FIJA[slug]
    puntos = {c: 3 * len(re.findall(s, titulo, re.I)) + len(re.findall(s, cuerpo, re.I))
              for c, s in SENALES.items()}
    orden = sorted(puntos.items(), key=lambda kv: -kv[1])
    cats = [orden[0][0]] if orden[0][1] else ['guias']
    if len(orden) > 1 and orden[1][1] >= max(3, orden[0][1] * 0.5):
        cats.append(orden[1][0])
    return cats


def descargar():
    print('descargando la API del WordPress…')
    subprocess.run(['curl', '-s', '-m', '90', API, '-o', str(POSTS)], check=True)
    posts = json.load(open(POSTS))
    urls = set()
    for p in posts:
        c = html.unescape(p['content']['rendered'])
        for m in re.finditer(r'(?:src|data-src)="(https://www\.qpaypro\.com/wp-content/uploads/[^"]+)"', c):
            urls.add(m.group(1))
        fm = (p.get('_embedded', {}).get('wp:featuredmedia') or [{}])[0]
        if fm.get('source_url'):
            urls.add(fm['source_url'])
    urls = {u for u in urls if re.search(r'\.(jpe?g|png|webp|avif|gif)$', u, re.I)}
    print(f'revisando {len(urls)} imágenes…')
    with open(IMGS, 'w') as f:
        for u in sorted(urls):
            r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-m', '25', '-w', '%{http_code}', u],
                               capture_output=True, text=True)
            f.write(f'{r.stdout.strip()} {u}\n')


def main():
    if '--descargar' in sys.argv or not POSTS.exists():
        descargar()

    posts = json.load(open(POSTS))
    vivas = {l.split(' ', 1)[1].strip() for l in open(IMGS) if l.startswith('200 ')}

    articulos, no_migrados = [], []
    for p in posts:
        slug_wp = p['slug']
        if slug_wp in DEMOS:
            no_migrados.append([slug_wp, 'demo de la plantilla'])
            continue
        if int(p['date'][:4]) < 2022:
            no_migrados.append([slug_wp, 'anterior a 2022'])
            continue
        if slug_wp in EXCLUIDOS:
            no_migrados.append([slug_wp, f'contradice los precios vigentes: {EXCLUIDOS[slug_wp]}'])
            continue

        bloques = a_bloques(p['content']['rendered'])
        slug = SLUG_CORREGIDO.get(slug_wp, slug_wp)
        if not bloques:
            # alianzaelsalvador: el contenido en WordPress son shortcodes de Visual Composer y
            # su texto real es una sola frase. Se redacta a mano en src/data/blog-manual.json.
            no_migrados.append([slug_wp, 'sin contenido convertible: se redacta a mano'])
            continue

        recorte = INTRO_AJENO.get(slug_wp)
        if recorte:
            bloques = bloques[recorte:]

        titulo = limpiar_titulo(p['title']['rendered'])
        cuerpo = ' '.join(texto_plano(b.get('text', '')) + ' ' + ' '.join(map(texto_plano, b.get('items', [])))
                          for b in bloques)
        fm = (p.get('_embedded', {}).get('wp:featuredmedia') or [{}])[0]
        portada = fm.get('source_url') if fm.get('source_url') in vivas else None

        articulos.append({
            'slug': slug,
            'slugWp': slug_wp,
            'title': titulo,
            'excerpt': extracto(bloques),
            'date': p['date'][:10],
            'cats': clasificar(slug, titulo, cuerpo),
            'countries': ['gt', 'sv'],
            'cover': {'wp': portada},
            'readingMinutes': max(1, round(palabras(bloques) / 200)),
            'body': bloques,
        })

    articulos.sort(key=lambda a: a['date'], reverse=True)
    json.dump(articulos, open(AQUI / '.articulos.json', 'w'), ensure_ascii=False, indent=2)
    json.dump(no_migrados, open(AQUI / '.no-migrados.json', 'w'), ensure_ascii=False, indent=2)

    print(f'convertidos: {len(articulos)}   no migrados: {len(no_migrados)}')
    print(f'  sin portada viva: {sum(1 for a in articulos if not a["cover"]["wp"])}')
    conteo = {}
    for a in articulos:
        for c in a['cats']:
            conteo[c] = conteo.get(c, 0) + 1
    print('  categorías:')
    for c, n in sorted(conteo.items(), key=lambda kv: -kv[1]):
        print(f'     {n:3}  {CATEGORIAS[c]}')
    tipos = {}
    for a in articulos:
        for b in a['body']:
            tipos[b['type']] = tipos.get(b['type'], 0) + 1
    print(f'  bloques: {tipos}')
    if SIN_MAPEAR:
        print(f'  ENLACES VIEJOS SIN MAPEAR ({len(SIN_MAPEAR)}), apuntados al home:')
        for u in sorted(SIN_MAPEAR):
            print(f'     {u}')
    sin_fijar = [a['slug'] for a in articulos if a['slug'] not in CATEGORIA_FIJA]
    if sin_fijar:
        print(f'  clasificados automáticamente (revisar): {sin_fijar}')


if __name__ == '__main__':
    main()
