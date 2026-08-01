/**
 * Proxy entre el formulario de contacto y Zoho CRM.
 *
 * El sitio es estático, así que el navegador no puede hablar con Zoho: las
 * credenciales quedarían dentro del bundle público y la API de CRM tampoco
 * responde con cabeceras CORS. Esta Function es el único lugar donde viven el
 * client secret y el refresh token.
 *
 * Variables de entorno (Cloudflare Pages → Settings → Variables and Secrets):
 *   ZOHO_CLIENT_ID          secreto
 *   ZOHO_CLIENT_SECRET      secreto
 *   ZOHO_REFRESH_TOKEN      secreto
 *   TURNSTILE_SECRET_KEY    secreto
 *   ZOHO_ACCOUNTS_HOST      texto, opcional (default accounts.zoho.com)
 *   ZOHO_API_HOST           texto, opcional (normalmente lo dice el propio Zoho)
 *   LEAD_RATE_LIMIT         KV binding, opcional
 */

interface Env {
  ZOHO_CLIENT_ID: string;
  ZOHO_CLIENT_SECRET: string;
  ZOHO_REFRESH_TOKEN: string;
  TURNSTILE_SECRET_KEY: string;
  ZOHO_ACCOUNTS_HOST?: string;
  ZOHO_API_HOST?: string;
  LEAD_RATE_LIMIT?: KVLike;
}

/** Lo que se usa de KV, para no depender de @cloudflare/workers-types. */
interface KVLike {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
}

interface EventContext {
  request: Request;
  env: Env;
}

// Las assignment rules de Zoho NO corren en un insert normal de la API: hay que
// pedir una por id con `lar_id`. Sin esto el lead queda a nombre de la cuenta
// que firma la petición —no del asesor del país— y nadie lo atiende.
//
// Las claves son además la lista de países válidos. Están duplicadas a propósito
// respecto de src/pages/[country]/contacto.astro: la Function se empaqueta
// aparte y no debe depender del árbol de Astro. Si cambian allá, cambian aquí.
const ASSIGNMENT_RULE_BY_COUNTRY: Record<string, string> = {
  Guatemala: '2592238000003550078', // GT ASIGNACION AUTOMATICA QPAYPRO
  'El Salvador': '2592238000208748011', // SV ASIGNACION AUTOMATICA QPAYPRO
};

// Lo que el visitante elige en el formulario, traducido al nombre comercial que
// espera Zoho. Las claves son las opciones del <select>; los valores, las del
// picklist Interesado_en. La tabla es además la lista de servicios válidos: lo
// que no esté aquí se rechaza antes de llegar al CRM.
const SERVICE_TO_PRODUCT: Record<string, string> = {
  'Pagos con tarjeta': 'QPayPro',
  'Tienda en línea': 'QPayShop',
  'Punto de venta': 'QPayPOS',
  'Terminal POS': 'mPOS',
};

// Lead_Source es un picklist y este es el valor exacto que existe en el CRM.
// Cualquier variante —tilde, mayúscula, sinónimo— hace que Zoho rechace el
// registro completo con INVALID_DATA.
const LEAD_SOURCE = 'Página web';

// Longitudes máximas del módulo Leads. Pasarse también invalida el registro
// entero, así que el recorte se hace aquí y no se delega en Zoho.
const ZOHO_MAX = {
  firstName: 40,
  lastName: 80,
  company: 200,
  email: 100,
  phone: 30,
  product: 255,
  description: 32000,
};

const MESSAGE_MAX = 200;
const FIELD_MAX = 200;
const RATE_LIMIT_MAX = 5;
const RATE_LIMIT_WINDOW = 600; // segundos

const GENERIC_ERROR = 'No pudimos enviar tu mensaje. Inténtalo de nuevo o escríbenos por WhatsApp.';

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  });
}

function fail(message: string, status: number) {
  return json({ ok: false, error: message }, status);
}

function text(value: unknown, max = FIELD_MAX) {
  return typeof value === 'string' ? value.trim().slice(0, max) : '';
}

/** Validación mínima: descarta lo evidente sin rechazar correos legítimos. */
function looksLikeEmail(value: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value);
}

async function verifyTurnstile(token: string, secret: string, ip: string | null) {
  const body = new FormData();
  body.append('secret', secret);
  body.append('response', token);
  if (ip) body.append('remoteip', ip);

  const response = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify', {
    method: 'POST',
    body,
  });
  const result = (await response.json()) as {
    success?: boolean;
    hostname?: string;
    'error-codes'?: string[];
  };

  // Sin esto, un captcha rechazado no deja rastro: el widget dice "¡Operación
  // exitosa!" en pantalla y el servidor responde que no, sin decir por qué.
  //   invalid-input-secret   → el secreto no es el del widget que emitió el token
  //   invalid-input-response → token inválido, malformado o vencido
  //   timeout-or-duplicate   → token ya usado, o de hace más de 5 minutos
  const codes = result['error-codes'] ?? [];
  if (result.success !== true) {
    console.error(`[lead] Turnstile rechazó el token: ${JSON.stringify(codes)} (hostname: ${result.hostname ?? 'n/d'})`);
  }

  return { ok: result.success === true, codes, hostname: result.hostname };
}

/**
 * El access_token de Zoho dura una hora. Con el volumen de este formulario sale
 * más barato pedir uno por envío que mantener cache compartida; si algún día
 * sube el tráfico, aquí es donde entraría KV.
 */
async function getAccessToken(env: Env) {
  const host = env.ZOHO_ACCOUNTS_HOST || 'accounts.zoho.com';
  const params = new URLSearchParams({
    refresh_token: env.ZOHO_REFRESH_TOKEN,
    client_id: env.ZOHO_CLIENT_ID,
    client_secret: env.ZOHO_CLIENT_SECRET,
    grant_type: 'refresh_token',
  });

  const response = await fetch(`https://${host}/oauth/v2/token?${params}`, { method: 'POST' });
  const result = (await response.json()) as { access_token?: string; api_domain?: string; error?: string };

  if (!result.access_token) {
    throw new Error(`Zoho no devolvió access_token: ${result.error ?? 'respuesta inesperada'}`);
  }
  // Zoho informa en la respuesta el dominio de API que corresponde a la cuenta,
  // así que el datacenter no hay que adivinarlo.
  return { accessToken: result.access_token, apiDomain: result.api_domain };
}

async function rateLimited(env: Env, ip: string | null) {
  if (!env.LEAD_RATE_LIMIT || !ip) return false;
  const key = `lead:${ip}`;
  const count = Number((await env.LEAD_RATE_LIMIT.get(key)) ?? '0');
  if (count >= RATE_LIMIT_MAX) return true;
  await env.LEAD_RATE_LIMIT.put(key, String(count + 1), { expirationTtl: RATE_LIMIT_WINDOW });
  return false;
}

/** Zoho devuelve el registro que ya existía dentro de los `details` del error. */
function duplicateLeadId(details: unknown): string | null {
  if (!details || typeof details !== 'object') return null;
  const entry = details as { id?: unknown; duplicate_record?: { id?: unknown } };
  const id = entry.duplicate_record?.id ?? entry.id;
  return typeof id === 'string' ? id : null;
}

/**
 * Cuelga el mensaje como Nota del lead que ya existía. Nunca lanza: si falla,
 * el envío igual se da por bueno, porque para quien escribió su mensaje sí
 * llegó a una persona. La Nota trae su propia fecha, así que no se escribe.
 */
async function attachNote(host: string, accessToken: string, leadId: string, content: string) {
  try {
    const response = await fetch(`${host}/crm/v8/Notes`, {
      method: 'POST',
      headers: {
        Authorization: `Zoho-oauthtoken ${accessToken}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        data: [
          {
            Parent_Id: { module: { api_name: 'Leads' }, id: leadId },
            Note_Title: 'Nuevo mensaje desde el formulario web',
            Note_Content: content,
          },
        ],
      }),
    });

    if (!response.ok) {
      console.error(`[lead] Nota rechazada para ${leadId}: ${response.status} ${await response.text()}`);
    }
  } catch (error) {
    console.error(`[lead] No se pudo adjuntar la nota a ${leadId}: ${error instanceof Error ? error.message : String(error)}`);
  }
}

export async function onRequestPost(context: EventContext): Promise<Response> {
  const { request, env } = context;
  const ip = request.headers.get('CF-Connecting-IP');

  if (!request.headers.get('Content-Type')?.includes('application/json')) {
    return fail('Formato no soportado.', 415);
  }

  let payload: Record<string, unknown>;
  try {
    payload = (await request.json()) as Record<string, unknown>;
  } catch {
    return fail('Petición inválida.', 400);
  }

  // Honeypot: se responde ok para no darle al bot ninguna señal de que falló.
  if (text(payload.website)) return json({ ok: true });

  const missingConfig = (['ZOHO_CLIENT_ID', 'ZOHO_CLIENT_SECRET', 'ZOHO_REFRESH_TOKEN'] as const)
    .filter((key) => !env[key]);
  if (missingConfig.length) {
    console.error(`[lead] Faltan variables de entorno: ${missingConfig.join(', ')}`);
    return fail(GENERIC_ERROR, 500);
  }

  // El captcha se exige solo si hay secreto configurado. Sin él el endpoint
  // sigue usable —lo cubren el honeypot, la validación de abajo y el límite por
  // IP— y la verificación se activa sola en cuanto la variable exista.
  if (env.TURNSTILE_SECRET_KEY) {
    const turnstileToken = text(payload.turnstileToken, 2048);
    if (!turnstileToken) {
      return fail('No se pudo verificar que no eres un robot. [diag: el navegador no mandó token]', 400);
    }
    const verdict = await verifyTurnstile(turnstileToken, env.TURNSTILE_SECRET_KEY, ip);
    if (!verdict.ok) {
      // TEMPORAL — diagnóstico en pantalla mientras se depura por qué Turnstile
      // rechaza tokens que el widget da por buenos. Quitar en cuanto se resuelva
      // y volver al mensaje genérico: los códigos no son secretos, pero tampoco
      // le dicen nada útil a quien está llenando el formulario.
      const diag = `${verdict.codes.join(', ') || 'sin código'} · host: ${verdict.hostname ?? 'n/d'} · ip: ${ip ? 'sí' : 'no'}`;
      return fail(`No se pudo verificar que no eres un robot. [diag: ${diag}]`, 400);
    }
  } else {
    console.warn('[lead] Sin TURNSTILE_SECRET_KEY: se acepta el envío sin verificar el captcha.');
  }

  const firstName = text(payload.first_name, ZOHO_MAX.firstName);
  const lastName = text(payload.last_name, ZOHO_MAX.lastName);
  const company = text(payload.company, ZOHO_MAX.company);
  // El correo y el teléfono no se recortan: uno truncado deja un lead con el que
  // nadie puede comunicarse. Se leen con un tope defensivo y se rechazan abajo.
  const email = text(payload.email, 320);
  const phone = text(payload.phone, 60);
  const country = text(payload.country);
  const product = text(payload.product, ZOHO_MAX.product);
  const service = text(payload.service);
  const message = text(payload.message, MESSAGE_MAX);

  // Se revalida en el servidor: lo que llega del navegador no es confiable, y
  // Zoho rechaza el registro completo si un valor de lista no existe.
  if (!firstName || !lastName || !company || !product) return fail('Faltan campos obligatorios.', 400);
  if (email.length > ZOHO_MAX.email) return fail(`El correo no puede tener más de ${ZOHO_MAX.email} caracteres.`, 400);
  if (!looksLikeEmail(email)) return fail('El correo no parece válido.', 400);
  if (phone.length > ZOHO_MAX.phone) return fail(`El teléfono no puede tener más de ${ZOHO_MAX.phone} caracteres.`, 400);
  if (phone.length < 6) return fail('El teléfono no parece válido.', 400);
  if (!(country in ASSIGNMENT_RULE_BY_COUNTRY)) return fail('País no válido.', 400);
  if (!(service in SERVICE_TO_PRODUCT)) return fail('Servicio no válido.', 400);

  // El contador va después de validar: cinco intentos con un correo mal escrito
  // no deben dejar fuera diez minutos a alguien que sí quiere escribirnos.
  if (await rateLimited(env, ip)) {
    return fail('Recibimos varios mensajes desde aquí. Espera unos minutos antes de volver a enviar.', 429);
  }

  const interest = SERVICE_TO_PRODUCT[service];

  const lead: Record<string, unknown> = {
    First_Name: firstName,
    Last_Name: lastName,
    Company: company,
    Email: email,
    Phone: phone,
    Lead_Source: LEAD_SOURCE,
    // Pa_s, no el Country estándar: en este CRM el estándar viene vacío y es
    // este el que usan las assignment rules y los reportes por país.
    Pa_s: country,
    // Interesado_en es un picklist de selección múltiple: espera un arreglo
    // aunque solo se mande un valor.
    Interesado_en: [interest],
    Qu_vendes: product,
  };

  // El mensaje es opcional: si no lo escribieron, no se manda el campo vacío.
  if (message) lead.Description = message.slice(0, ZOHO_MAX.description);

  try {
    const { accessToken, apiDomain } = await getAccessToken(env);
    const host = apiDomain ?? `https://${env.ZOHO_API_HOST || 'www.zohoapis.com'}`;

    const response = await fetch(`${host}/crm/v8/Leads`, {
      method: 'POST',
      headers: {
        Authorization: `Zoho-oauthtoken ${accessToken}`,
        'Content-Type': 'application/json',
      },
      // Sin duplicate_check_fields: ese parámetro es del endpoint de upsert. En
      // el insert, Zoho ya detecta el repetido por Email y responde
      // DUPLICATE_DATA, que es lo que se maneja abajo.
      //
      // `lar_id` es lo que hace correr la assignment rule del país; sin él el
      // lead nace a nombre de la cuenta que firma la API. Las assignment rules
      // son independientes de `trigger`, que solo cubre workflows —aprobaciones,
      // blueprints, pathfinder y orchestration no corren con este parámetro.
      body: JSON.stringify({
        data: [lead],
        trigger: ['workflow'],
        lar_id: ASSIGNMENT_RULE_BY_COUNTRY[country],
      }),
    });

    const result = (await response.json()) as {
      data?: Array<{ code?: string; status?: string; message?: string; details?: unknown }>;
    };
    const entry = result.data?.[0];

    // Un lead repetido no es un error para quien escribe: ya está en el CRM. Lo
    // que no puede pasar es que su mensaje nuevo se pierda sin que nadie en
    // ventas se entere, así que se cuelga como Nota del lead existente.
    if (entry?.code === 'DUPLICATE_DATA') {
      const leadId = duplicateLeadId(entry.details);
      if (leadId) {
        const note = [
          `Servicio de interés: ${interest}`,
          `Qué vende: ${product}`,
          message ? `Mensaje:\n${message}` : '',
        ]
          .filter(Boolean)
          .join('\n\n');
        await attachNote(host, accessToken, leadId, note);
      } else {
        console.error(`[lead] Duplicado sin id en la respuesta: ${JSON.stringify(entry.details)}`);
      }
      console.log(`[lead] Duplicado para ${email}`);
      return json({ ok: true });
    }

    if (!response.ok || entry?.status !== 'success') {
      // El detalle se queda en el log: puede nombrar campos internos del CRM.
      console.error(`[lead] Zoho ${response.status}: ${JSON.stringify(result)}`);
      return fail(GENERIC_ERROR, 502);
    }

    return json({ ok: true });
  } catch (error) {
    console.error(`[lead] ${error instanceof Error ? error.message : String(error)}`);
    return fail(GENERIC_ERROR, 502);
  }
}

// Solo se exporta onRequestPost. Con cualquier otro método Pages no encuentra
// handler y sirve el 404 del sitio, que para un endpoint interno está bien: no
// hace falta anunciar que la ruta existe.
