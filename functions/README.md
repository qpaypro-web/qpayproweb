# Cloudflare Pages Functions

## `/api/lead`

Recibe el formulario de contacto (`src/pages/[country]/contacto.astro`) y crea un
Lead en Zoho CRM.

El navegador no puede hablar con Zoho directamente por dos razones: el sitio es
estático, así que cualquier credencial que se compile en él queda pública, y la
API de CRM no responde con cabeceras CORS. Esta Function es el único punto donde
viven los secretos.

### Configuración en Cloudflare Pages

**Settings → Variables and Secrets.** Cargar en *Production* y en *Preview*: si
solo se cargan en producción, los deploys de preview fallan al enviar.
Después de agregarlas hay que volver a desplegar; los deploys existentes no las
recogen.

| Variable | Tipo | Obligatoria |
|---|---|---|
| `ZOHO_CLIENT_ID` | Secret | sí |
| `ZOHO_CLIENT_SECRET` | Secret | sí |
| `ZOHO_REFRESH_TOKEN` | Secret | sí |
| `TURNSTILE_SECRET_KEY` | Secret | no — ver "Captcha" |
| `PUBLIC_TURNSTILE_SITE_KEY` | Plaintext (build) | no — ver "Captcha" |
| `ZOHO_ACCOUNTS_HOST` | Plaintext | no — default `accounts.zoho.com` |
| `ZOHO_API_HOST` | Plaintext | no — respaldo; Zoho devuelve el correcto |
| `ZOHO_FIELD_PRODUCT` | Plaintext | no — ver más abajo |
| `ZOHO_FIELD_SERVICE` | Plaintext | no — ver más abajo |
| `LEAD_RATE_LIMIT` | KV binding | no — sin él no hay límite por IP |

`PUBLIC_TURNSTILE_SITE_KEY` es la única que se compila dentro del sitio y es
visible para cualquiera; así está diseñado Turnstile. **A ninguna otra se le
puede poner el prefijo `PUBLIC_`**: quedaría dentro del JS que descarga el
navegador.

### Captcha

Las dos variables de Turnstile son opcionales, pero **el formulario queda
expuesto a bots mientras no estén**. Se comporta así:

| Estado | Qué pasa |
|---|---|
| Las dos configuradas | El widget aparece y el servidor verifica el token. Es el estado deseado. |
| Ninguna configurada | El widget no se dibuja y el formulario funciona. Lo protegen el honeypot, la validación del servidor y el límite por IP. Queda un aviso en la consola del navegador y en el log de la Function. |
| Solo la sitekey | El widget aparece pero el servidor no verifica: protección aparente, no real. |
| Solo el secret | El servidor exige un token que el formulario no puede generar. **Nadie puede enviar nada.** |

Los dos estados a medias son configuraciones rotas: o las dos, o ninguna.

En cuanto se agregan las dos y se redespliega, la verificación se activa sola,
sin tocar código.

### Datacenter de Zoho

`accounts.zoho.com` es el de EE.UU. Si el Self Client se creó en
`api-console.zoho.eu` (o `.in`, `.com.au`, `.jp`), hay que poner el
`ZOHO_ACCOUNTS_HOST` que corresponda o el refresh falla con `invalid_client`.

El dominio de la API no hace falta configurarlo: Zoho devuelve el `api_domain`
correcto junto con el `access_token`.

### Campos personalizados

"¿Qué producto o servicio vendes?" y "¿Qué servicio te interesa?" no tienen campo
estándar en el módulo Leads:

- `Lead_Source` **no** sirve para el servicio de interés: es un picklist de
  valores fijos y Zoho rechaza el registro completo con `INVALID_DATA` si llega
  un valor que no está en la lista. Se manda con el valor fijo `Sitio web`.
- `Comments` **no** es escribible por API en Leads.

Pedirle al administrador de Zoho los API names de los dos campos personalizados
y ponerlos en `ZOHO_FIELD_PRODUCT` y `ZOHO_FIELD_SERVICE`. Mientras estén
vacíos, esos dos datos se anexan al final de `Description` en vez de perderse.

### Desarrollo local

```sh
npm run build
npx wrangler pages dev dist
```

Los secretos se leen de un archivo `.dev.vars` en la raíz (ignorado por git):

```
TURNSTILE_SECRET_KEY=1x0000000000000000000000000000000AA
ZOHO_CLIENT_ID=…
ZOHO_CLIENT_SECRET=…
ZOHO_REFRESH_TOKEN=…
```

Cloudflare publica llaves de prueba para Turnstile: `1x00000000000000000000AA`
(sitekey, siempre aprueba) y `1x0000000000000000000000000000000AA` (secret).
Sirven para probar el camino con captcha sin dar de alta un widget real; para
probar la ruta de error están `2x00000000000000000000AB` y
`2x0000000000000000000000000000000AA`, que siempre fallan.

Los baselines de regresión visual se capturan con `npm run build` a secas, sin
ninguna variable de Turnstile.
