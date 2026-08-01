# El blog: cómo funciona y cómo agregar artículos

El contenido del blog vive en `src/data/blog-articles.json`. Las páginas de Astro solo lo leen;
no hay CMS ni base de datos. Para agregar un artículo se edita ese archivo (o se vuelve a correr
la migración si el artículo nuevo se escribió en el WordPress).

## Estructura

| Archivo | Qué es |
|---|---|
| `src/data/blog-articles.json` | Los 50 artículos publicados. Lo genera la migración; se puede editar a mano. |
| `src/data/blog-manual.json` | Artículos escritos a mano, que la migración no puede convertir. Se mezclan con los demás. |
| `src/data/blog-categorias.json` | Las 6 categorías, con su nombre y descripción. |
| `src/lib/blog.ts` | Consultas: filtrado por país, categorías, relacionados, fechas, índice del artículo. |
| `src/components/BlogBlocks.astro` | Renderiza los bloques del cuerpo. |
| `src/pages/[country]/blog/index.astro` | Índice con destacado, filtro y "ver más". |
| `src/pages/[country]/blog/[slug].astro` | El artículo. |
| `src/pages/[country]/blog/categoria/[cat].astro` | La página de cada categoría. |

## Un artículo

```json
{
  "slug": "criptomonedas",
  "slugWp": "criptomonedas",
  "title": "Criptomonedas: datos clave y cómo transforman el comercio en línea",
  "excerpt": "Máximo 185 caracteres. Es lo que sale en la tarjeta y en la meta description.",
  "date": "2024-07-09",
  "cats": ["pagos"],
  "countries": ["gt", "sv"],
  "cover": { "src": "/images/blog/criptomonedas.jpg", "alt": "…", "w": 800, "h": 800 },
  "readingMinutes": 3,
  "body": [{ "type": "h2", "text": "…" }]
}
```

- **`slug`** es la URL: `/gt/blog/<slug>`. Cambiarlo rompe el enlace, así que si hay que cambiarlo
  se agrega un 301 desde el viejo.
- **`slugWp`** es el slug que tenía en el WordPress. Solo sirve para generar los redirects; no se
  muestra. En un artículo nuevo se pone igual que `slug`.
- **`cats`** son slugs de `blog-categorias.json`. El primero es la categoría principal: es la que
  sale en la tarjeta y en "Sigue leyendo". Máximo dos.
- **`countries`** decide en qué países aparece. Hoy los 50 llevan `["gt", "sv"]`. Para esconder
  un artículo de El Salvador se deja `["gt"]` y desaparece de `/sv/` sin tocar nada más: no se
  genera su página ni se lista en el índice ni en las categorías.
- **`readingMinutes`** se calcula a 200 palabras por minuto.
- **`cover.w` y `cover.h`** pueden ir en `null` si no se conocen; la plantilla omite los atributos.
  El recorte lo hace el contenedor, así que no hay salto de maquetación.
- La firma es siempre **"Equipo de medios de QPayPro"** y está en `src/lib/blog.ts` (`FIRMA`).
  No hay autores individuales.

## Tipos de bloque

| Tipo | Campos | Para qué |
|---|---|---|
| `p` | `text` | Párrafo. |
| `h2` | `text` | Encabezado de sección. Alimenta el índice lateral del artículo. |
| `h3` | `text` | Subencabezado. |
| `ul` | `items` | Lista con viñetas. |
| `ol` | `items` | Lista numerada. |
| `quote` | `text` | Cita destacada, con barra azul a la izquierda. |
| `callout` | `text` | Caja azul clara con icono, para un dato o una advertencia. |
| `cta` | `text` | Caja con el texto y dos botones, a precios y a ventas del país de la página. |
| `img` | `src`, `alt`, `w`, `h`, `caption`, `wide` | Imagen dentro del texto: foto, gráfico o infografía. |

En `text` y en `items` se permite **solo** `<strong>`, `<em>` y `<a href="…">`. Cualquier otra
etiqueta se ve como texto: el renderizador usa `set:html` sobre esa lista blanca a propósito,
para que nadie pueda meter estilos del editor viejo.

El índice lateral del artículo aparece desde 1280 px y solo si el artículo tiene 3 o más `h2`.

### Imágenes en el cuerpo

La migración desde WordPress no trajo ninguna imagen del cuerpo: solo la portada. Los artículos
que la necesiten se completan a mano con bloques `img`.

```json
{
  "type": "img",
  "src": "/images/blog/alianzaelsalvador-presentacion.webp",
  "alt": "Tres representantes de Qpaypro muestran la aplicación de cobro",
  "w": 1080,
  "h": 1080,
  "caption": "La aplicación de cobro de Qpaypro, durante la presentación."
}
```

- `alt` describe lo que se ve, para quien no puede verla. Va vacío **solo** si la imagen es
  decorativa y no aporta información que no esté en el texto.
- `w` y `h` son los píxeles reales del archivo. Sin ellos el navegador no reserva el espacio y la
  página salta mientras carga.
- `caption` es opcional. Se ve centrado y en gris bajo la imagen.
- `wide: true` saca la imagen del ancho de la columna de texto en pantallas grandes. Es para
  infografías y gráficos, donde el detalle se pierde a 720 px; en una foto normal estorba.

Las imágenes van en `public/images/blog/` con el slug del artículo como prefijo
(`<slug>-<que-es>.<ext>`), para que se sepa a cuál pertenecen. Conviene bajar las fotos grandes a
1600 px de ancho antes de commitear:

```bash
sips -Z 1600 original.jpg --out public/images/blog/<slug>-<que-es>.jpg
```

Un artículo con imágenes del WordPress viejo tiene una trampa: las fotos que el tema ponía como
**fondo de columna** no aparecen como `<img>` en el HTML ni en el contenido que devuelve la API de
WordPress, que son shortcodes de WPBakery. Hay que buscarlas en el HTML renderizado por
`column-image-bg-wrap` o revisar la biblioteca de medios de la fecha del artículo.

## Agregar un artículo a mano

Se agrega el objeto a `src/data/blog-articles.json` (o a `blog-manual.json` si se quiere que la
migración no lo pise) y se pone la portada en `public/images/blog/<slug>.<ext>`.

Si no hay imagen, se genera una de marca con:

```bash
python3 scripts/finalizar-blog.py
```

Ese script crea un SVG con el degradado del sitio, la categoría y el título cuando un artículo no
tiene portada. También normaliza títulos y encabezados al estilo del sitio.

Al final, agregar el redirect si el artículo existía antes con otra URL:

```bash
python3 scripts/redirects-blog.py
```

## Volver a correr la migración

Si el equipo publica artículos nuevos en el WordPress y hay que traerlos:

```bash
python3 scripts/migrar-blog.py --descargar   # baja la API y revisa qué imágenes siguen vivas
python3 scripts/finalizar-blog.py            # títulos, portadas y src/data/blog-articles.json
python3 scripts/redirects-blog.py            # recalcula public/_redirects
npm run build
```

`--descargar` tarda unos minutos porque revisa una por una las imágenes referenciadas.

## Qué se migró y qué no

De los 90 posts del WordPress:

| | Cuántos | Qué se hizo |
|---|---|---|
| De 2022 en adelante | 50 | Publicados |
| Anteriores a 2022 | 35 | 301 al índice del blog |
| Demos de la plantilla | 5 | 301 al índice del blog |

Los 35 anteriores a 2022 quedaron fuera por decisión del cliente: citan tasas, comisiones y
políticas que hoy contradicen las páginas de precios. Si alguna vez se quieren recuperar, hay que
revisar esas cifras antes de publicarlas, no solo convertirlas.

Los 5 demos son posts de ejemplo de la plantilla Essentials/pixfort que el equipo compró, en
inglés y sin relación con el negocio.

## Defectos del WordPress que la migración corrige

Vale la pena conocerlos porque explican por qué la migración no es una copia:

1. **Las imágenes del cuerpo no existen.** De 385 URLs de imagen que el contenido referencia,
   sobreviven 60, y todas son portadas. Las intercaladas en el texto están caídas en el propio
   WordPress. Se descartan sus etiquetas en lugar de dejar huecos, y el ritmo visual del artículo
   lo dan los encabezados, las citas y los `callout`.
2. **Cinco artículos tienen la URL de otro post.** El slug
   `errores-comunes-en-el-ecommerce-y-como-evitarlos` servía el artículo de Qpayfel, y los tres
   slugs que terminan en `-copy` son artículos distintos, no duplicados. Se les dio un slug
   correcto y la URL vieja redirige a la nueva (ver `SLUG_CORREGIDO` en `migrar-blog.py`).
3. **El campo `excerpt` está cruzado entre artículos.** Ocho grupos de resúmenes repetidos
   afectaban a 17 artículos. La migración lo ignora y saca el extracto del primer párrafo del
   propio artículo.
4. **Un artículo abre con el intro de otro.** "Temporadas altas sin pérdidas" empezaba con dos
   párrafos de "Tendencias que están transformando el ecommerce"; se recortan
   (`INTRO_AJENO` en `migrar-blog.py`).
5. **Los niveles de encabezado no tienen jerarquía.** Hay artículos cuyo encabezado principal es
   `h6`. Se normalizan por artículo: el nivel más superficial pasa a `h2` y el siguiente a `h3`.
   Si el artículo no empieza por su nivel más superficial, todo queda en `h2`, porque un `h3`
   antes del primer `h2` es jerarquía inválida.
6. **Restos del editor.** 148 etiquetas `<strong>` traían atributos `data-start`/`data-end`, y
   había emoji decorativos y comillas angulares delante de los encabezados. Todo eso se quita.
7. **Un artículo arrastraba los widgets del pie de la página** ("Contacto PBX", "email@site.com")
   dentro del contenido. Se corta desde el primero que aparece.
8. **Enlaces a URLs que ya no existen.** Los artículos enlazan a `/payments/` y a
   `/qpayshop-vende24hrs/`; el primero es hoy la pasarela de pagos y el segundo ya estaba caído.
   Se mapean en `ENLACES_VIEJOS`; lo que no esté en ese mapa se reporta al correr el script en
   lugar de romperse en silencio.
9. **`alianzaelsalvador` no es convertible.** Su contenido en el WordPress son shortcodes de
   Visual Composer y su texto real es una sola frase. Está escrito a mano en
   `src/data/blog-manual.json`.

## Categorías

Las 25 categorías del WordPress dejaban el filtro inservible: `Ecommerce` se llevaba 41 de 49
artículos y `Seguridad` y `Guías` tenían uno cada una. Además `Articles` y `Post Types` son
categorías de la plantilla.

Las 6 actuales se asignaron por contenido, artículo por artículo, en `CATEGORIA_FIJA` dentro de
`migrar-blog.py`. Para mover un artículo de categoría basta cambiar su campo `cats` en el JSON;
si además se quiere que la migración lo respete cuando se vuelva a correr, hay que cambiarlo
también en `CATEGORIA_FIJA`.

Los artículos que no estén en ese mapa se clasifican por palabras clave y el script los lista al
final para que alguien los revise.

## Riesgo abierto: contenido de Guatemala en El Salvador

Por decisión del cliente los 50 artículos salen en los dos países. Dos de ellos chocan con lo que
dicen las páginas de El Salvador:

| Artículo | Por qué |
|---|---|
| `qpayfel-facturacion-electronica-guatemala` | Habla de facturación electrónica, producto que no se ofrece en El Salvador |
| `nuevos-cambios-en-politicas-tasas-e-impuestos` | Cita tasas de Guatemala |

Para sacarlos de El Salvador se les cambia `countries` a `["gt"]` y se reconstruye. No hace falta
tocar nada más.
