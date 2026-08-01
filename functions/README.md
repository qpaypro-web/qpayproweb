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

### Campos de Zoho

Los API names están fijos en el código porque están verificados contra el CRM.
Los tres primeros son picklists: si el valor no existe **tal cual**, Zoho no
guarda el campo mal y ya — rechaza el registro completo con `INVALID_DATA`, y el
visitante solo ve el error genérico.

| Campo | Tipo | Qué se manda |
|---|---|---|
| `Lead_Source` | picklist | siempre `Página web` |
| `Pa_s` | picklist | `Guatemala` o `El Salvador` |
| `Interesado_en` | picklist **multi-select** | arreglo de un elemento, ver tabla abajo |
| `Qu_vendes` | texto (255) | "¿Qué producto o servicio vendes?" |
| `Description` | textarea | el mensaje, si lo escribieron |

`Pa_s` es el campo de país que usa este CRM. El `Country` estándar viene vacío en
casi todos los leads, así que no se escribe: cada campo de más es un motivo más
de rechazo del registro completo.

`Interesado_en` es de selección múltiple: el valor va como arreglo (`["QPayPro"]`)
aunque solo sea uno. Mandarlo como texto suelto falla.

| Opción del formulario | Valor en `Interesado_en` |
|---|---|
| Pagos con tarjeta | `QPayPro` |
| Tienda en línea | `QPayShop` |
| Punto de venta | `QPayPOS` |
| Terminal POS | `mPOS` |

Las longitudes máximas de Leads están en `ZOHO_MAX` y también como `maxlength` en
el formulario. Pasarse invalida el registro entero, así que el correo y el
teléfono se rechazan con un 400 en vez de recortarse: uno truncado deja un lead
con el que nadie puede comunicarse.

### Asignación al asesor (`lar_id`)

Las **assignment rules de Zoho no corren en un insert normal de la API**. Hay que
pedir una explícitamente con `lar_id`, parejo a `data`, o el lead nace a nombre
de la cuenta dueña del refresh token y se queda ahí.

`trigger` no sirve para esto: cubre workflows, no assignment rules.

| País | Regla | id |
|---|---|---|
| Guatemala | GT ASIGNACION AUTOMATICA QPAYPRO | `2592238000003550078` |
| El Salvador | SV ASIGNACION AUTOMATICA QPAYPRO | `2592238000208748011` |

Están en `ASSIGNMENT_RULE_BY_COUNTRY`, que es además la lista de países válidos.
Si en Zoho se renombra o reemplaza una regla, el id cambia y hay que actualizarlo
aquí: no hay forma de resolverlo por nombre en tiempo de ejecución.

A quién le toca cada lead lo decide la regla dentro de Zoho, no este código.

### Duplicados

Zoho tiene `Email` como único en Leads. Cuando alguien que ya está en el CRM
vuelve a escribir, la respuesta trae `DUPLICATE_DATA` y la Function **cuelga el
mensaje como Nota** del lead existente en vez de descartarlo. Si la nota falla se
registra en el log pero el envío se da por bueno igual.

### Automatizaciones

El insert manda `trigger: ['workflow']`. Con ese parámetro **no** corren
aprobaciones, blueprints, pathfinder ni orchestration: si se agrega alguno que
deba dispararse desde el formulario, hay que listarlo ahí.

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
