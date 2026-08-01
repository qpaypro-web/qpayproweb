"""
Regenera public/_redirects con las URLs del WordPress de qpaypro.com.

    python3 scripts/redirects-blog.py

Conserva las reglas de las páginas y los .html del despliegue intermedio, y recalcula las del
blog a partir de src/data/blog-articles.json, para que el mapa nunca quede desincronizado del
contenido publicado. Ver docs/BLOG.md.
"""
import json
import re
from pathlib import Path

AQUI = Path(__file__).parent
REPO = AQUI.parent
REDIRECTS = REPO / 'public' / '_redirects'

# Páginas del WordPress, mapeadas una por una según su contenido real (no según su title: dos
# de ellas tienen el title de otra página).
PAGINAS = {
    '/planes-y-precios-de-pasarela-de-pagos-en-el-salvador/': '/sv/precios',
    '/planes-y-precios-de-pasarela-de-pagos-en-guatemala/': '/gt/precios',
    '/posplanfree/': '/sv/precios',
    '/pos-plan-premium-sv/': '/sv/precios',
    '/contacto-ventas-qpaypro/': '/gt/contacto',
    '/programa-de-partners-de-pagos/': '/gt/partners',
    '/seguridad-en-pagos-digitales/': '/gt/seguridad',
    '/sobre-qpaypro/': '/gt/sobre-qpaypro',
    '/sv-anterior/': '/sv',
    '/pasarela-de-pagos-en-el-salvador/': '/sv',
    '/bbbblog-de-pasarela-pagos-digitales/': '/gt/blog',
    '/blog-de-pasarela-pagos-digitales/': '/gt/blog',
    '/politicas-de-privacidad/': '/gt/politicas-de-privacidad',
    '/terminos-condiciones/': '/gt/terminos-condiciones',
    '/tu-tienda-en-linea-con-pagos-integrados/': '/gt/tiendas-en-linea',
    '/automatiza-tus-cobros-por-suscripcion/': '/gt',
    '/payments/': '/gt/pasarela-de-pagos',
}

# Atajos que hoy resuelve el propio WordPress con un 301 interno y que desaparecen cuando el
# dominio deje de apuntarle. Los tres últimos van a El Salvador porque es a donde los manda el
# sitio actual.
ATAJOS = {
    '/blog/': '/gt/blog',
    '/contacto/': '/gt/contacto',
    '/partners/': '/gt/partners',
    '/seguridad/': '/gt/seguridad',
    '/terminos/': '/gt/terminos-condiciones',
    '/planes/': '/sv/precios',
    '/pasarela-de-pagos/': '/sv',
    '/pos/': '/sv/precios',
}

# Las 25 categorías del WordPress hacia las 6 del sitio nuevo. Las que no tienen equivalente
# —las de la plantilla y las de un solo artículo sin tema propio— van al índice del blog.
CATEGORIAS_VIEJAS = {
    'pagos-en-linea': 'pagos',
    'tarjetas-de-credito': 'pagos',
    'simplificacion-del-pago': 'pagos',
    'qpaybilling': 'pagos',
    'criptomonedas': 'pagos',
    'ecommerce': 'ecommerce',
    'turismo': 'ecommerce',
    'servicios-profesionales': 'ecommerce',
    'fundaciones': 'ecommerce',
    'organizaciones-sociales': 'ecommerce',
    'seguridad': 'seguridad',
    'marketing': 'marketing',
    'redes-sociales': 'marketing',
    'estrategias-de-venta-digital': 'marketing',
    'qpaypro': 'producto',
    'lanzamientos': 'producto',
    'qpayfel': 'producto',
    'qpayboost': 'producto',
    'atencion-al-cliente': 'producto',
    'transformacion-de-negocios': 'guias',
    'tecnologia-y-automatizacion': 'guias',
    'velocidad-y-rendimiento': 'guias',
    'articles': None,
    'post-types': None,
    'otros': None,
}


def main():
    articulos = json.load(open(REPO / 'src' / 'data' / 'blog-articles.json'))
    publicados = {a['slugWp']: a['slug'] for a in articulos}

    # Todos los slugs de post que existen en el WordPress, publicados o no.
    posts = json.load(open(AQUI / '.wp-posts.json'))
    todos_wp = [p['slug'] for p in posts]

    # Se conservan tal cual las reglas de los .html del despliegue intermedio.
    html = {}
    if REDIRECTS.exists():
        for linea in REDIRECTS.read_text(encoding='utf-8').split('\n'):
            if linea.strip():
                o, d, _ = linea.split()
                if o.endswith('.html'):
                    html[o] = d

    reglas, vistos = [], set()

    def agregar(origen, destino):
        if origen not in vistos:
            vistos.add(origen)
            reglas.append((origen, destino))

    for o, d in html.items():
        agregar(o, d)
    for o, d in PAGINAS.items():
        agregar(o, d)
    for o, d in ATAJOS.items():
        agregar(o, d)

    migrados, al_indice = 0, 0
    for slug in todos_wp:
        origen = f'/{slug}/'
        if origen in vistos:
            continue
        nuevo = publicados.get(slug)
        if nuevo:
            agregar(origen, f'/gt/blog/{nuevo}')
            migrados += 1
        else:
            # Anteriores a 2022 y demos de la plantilla: no se publican.
            agregar(origen, '/gt/blog')
            al_indice += 1

    cats = 0
    for viejo, nuevo in CATEGORIAS_VIEJAS.items():
        destino = f'/gt/blog/categoria/{nuevo}' if nuevo else '/gt/blog'
        agregar(f'/category/{viejo}/', destino)
        cats += 1

    # Las dos variantes de barra final, porque los enlaces entrantes traen las dos formas.
    lineas = []
    for o, d in reglas:
        lineas.append(f'{o} {d} 301')
        if o.endswith('/') and o != '/':
            lineas.append(f'{o.rstrip("/")} {d} 301')

    REDIRECTS.write_text('\n'.join(lineas) + '\n', encoding='utf-8')

    corregidos = [(a['slugWp'], a['slug']) for a in articulos if a['slugWp'] != a['slug']]
    print(f'{len(reglas)} reglas -> {len(lineas)} líneas')
    print(f'  .html heredados: {len(html)}   páginas: {len(PAGINAS)}   atajos: {len(ATAJOS)}')
    print(f'  artículos publicados: {migrados}   al índice del blog: {al_indice}   categorías: {cats}')
    print(f'  slugs corregidos: {len(corregidos)}')
    for viejo, nuevo in corregidos:
        print(f'     /{viejo}/  ->  /gt/blog/{nuevo}')


if __name__ == '__main__':
    main()
