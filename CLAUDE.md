# Qpaypro — sitio web

Sitio de **Qpaypro** (pasarela de pagos, Guatemala y El Salvador), reconstruido desde un
WordPress. **Astro estático + Tailwind 4**, desplegado en **Cloudflare Pages**.

```sh
npm run dev       # servidor de desarrollo
npm run build     # 146 páginas en dist/
npm run preview   # sirve dist/ para verificar el resultado real
```

No hay tests ni `astro check` en los scripts. La verificación es el build más mirar la página.

**El contenido va en español.** Los comentarios del código, los mensajes de commit y los textos
del sitio están todos en español, en infinitivo para los commits ("Retirar las fotos…").

---

## Multipaís: la decisión que explica casi todo

Cada país es un árbol de rutas completo bajo su prefijo: `/gt/precios` y `/sv/precios`. **La ruta
es la misma en los dos y lo que cambia es el contenido.** Por eso casi todas las páginas viven en
`src/pages/[country]/` y se generan dos veces.

- `src/lib/country.ts` es la pieza central: `withCountry`, `swapCountry`, `countryFromPath`,
  `conVarianteDePais`.
- `src/data/countries/{gt,sv}.json` tiene lo que difiere: planes, tabla comparativa, calculadora,
  FAQ, moneda, requisitos.
- El layout deriva el país de la propia ruta (`countryFromPath`), así que las páginas no tienen
  que pasarlo como prop.

**Trampa:** con `build.format: 'file'` el pathname llega como `/gt.html`, no `/gt`. Cualquier
lógica que parta la ruta por `/` tiene que pasar antes por `normalizePath`, o lee el segmento
como `"gt.html"` y no reconoce el país.

### Capacidades por país (`features`)

El pago en cuotas, las suscripciones y la tokenización **existen en Guatemala pero no en
El Salvador**. Como las páginas son las mismas, cada país declara sus capacidades:

```json
"features": { "installments": true, "subscriptions": true, "tokenization": true }
```

Las plantillas consultan la bandera (`c.features.subscriptions`) en vez de dar por hecho que la
función existe. Cuando se quita un elemento de una lista, **la numeración se calcula al final**
(`.map((x, i) => ({ ...x, num: … }))`), nunca a mano, porque al desaparecer uno los demás se corren.

Para el contenido de los sectores, `conVarianteDePais(contenido, country)` fusiona sobre la
versión general solo lo que cambia, declarado bajo la clave del país en `sectors.json`:

- los objetos se fusionan campo por campo;
- las listas se reemplazan enteras, o se retocan por posición: `{ "blocks": { "0": { "desc": "…" } } }`;
- `"omitirEn": ["sv"]` borra un bloque, una tarjeta o una pregunta completa.

**Los testimonios son citas de personas reales y no se les cambia el texto.** Si una cita nombra
algo que no aplica en un país, ahí se oculta la sección (`testimonial: null`), no se reescribe.

### Al agregar o cambiar contenido

Antes de escribir una frase que prometa una función, verificá si existe en los dos países. Si no,
va detrás de la bandera. Lo mismo aplica al JSON-LD (`src/lib/schema.ts`) y a `llms.txt`: el nodo
`Organization` va en **todas** las páginas de ambos países, así que solo puede enumerar lo que
existe en los dos; lo específico va en los nodos por país.

---

## La raíz reparte, y no redirige a los bots

`src/pages/index.astro` es un meta-refresh con `noindex`, y `functions/index.ts` hace geo-IP en el
edge **solo para humanos**. Es deliberado: Googlebot rastrea desde EE.UU., así que redirigir por IP
a un rastreador haría que solo se indexara una versión del sitio. Los bots reciben el índice
estático; la cookie `qp-pais` del selector manda sobre la geolocalización.

---

## Formulario → Zoho CRM (`functions/api/lead.ts`)

El sitio es estático, así que el navegador no puede hablar con Zoho: esta Cloudflare Function es
el único lugar donde viven los secretos. Ver `functions/README.md` para las variables de entorno.

Cosas que ya costaron una depuración y están comentadas en el archivo:

- **`lar_id`** es lo que hace correr la assignment rule del país. Sin él el lead nace a nombre de
  la cuenta que firma la API y nadie lo atiende.
- El campo de país es **`Pa_s`**, no el `Country` estándar, que en este CRM viene vacío.
- Un **lead duplicado no es un error**: el mensaje se cuelga como Nota del lead existente y cuenta
  igual como conversión.
- El evento de Meta va por Conversions API con **`event_id = lead_<id de Zoho>`**, el mismo que usa
  la automatización del CRM, para que no se cuente la conversión dos veces.
- El refresh token queda atado al **usuario de Zoho** que generó el Self Client. Si lo desactivan,
  la API responde `403 INACTIVE_USER` y el formulario deja de crear leads sin señal visible.

---

## Analítica

Solo se carga el contenedor **GTM-T53BQFC**, que ya contiene Meta Pixel, GA4 y Google Ads. **No
cablear el píxel ni gtag por separado**: se cargarían dos veces y duplicarían el PageView. El
consentimiento se maneja con Consent Mode v2 (`ConsentBanner.astro`).

---

## Mapa rápido

| Dónde | Qué |
|---|---|
| `src/lib/country.ts` | Multipaís: rutas, banderas, variantes de contenido |
| `src/lib/schema.ts` | JSON-LD centralizado (`@id` fijo para Organization y WebSite) |
| `src/lib/blog.ts` | Consultas del blog |
| `src/data/countries/*.json` | Todo lo que difiere entre países |
| `src/data/sectors.json` | Los 5 sectores, con sus variantes por país |
| `src/data/blog-articles.json` | Los 50 artículos migrados. Ver `docs/BLOG.md` |
| `public/_redirects` | Los 301 desde el WordPress viejo |
| `tools/visual-regression/` | Comparar una página antes y después. Ver su README |

## Pendiente conocido

`src/data/countries/sv.json` declara bajo `pendiente` dos datos que **el cliente no ha entregado y
que no deben inventarse**: el precio del kit Sistema POS en El Salvador y el contrato de términos
y condiciones de Qpaypro El Salvador, S.A. de CV. Mientras falten, la página de términos muestra
"Próximamente" y el JSON-LD omite el bloque de precio.
