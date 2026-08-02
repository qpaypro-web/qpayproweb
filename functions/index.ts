/**
 * Reparte la raíz del sitio entre Guatemala y El Salvador.
 *
 * Solo actúa sobre `/`. Cualquier ruta con país explícito —/gt/precios,
 * /sv/contacto— se sirve tal cual: si alguien pidió una versión concreta, no
 * hay nada que decidir.
 *
 * Reglas, en orden:
 *   1. Bots: se les deja el index estático de siempre, con su meta refresh a
 *      /gt, su canonical y su noindex. Redirigir por IP a un rastreador hace
 *      que solo se indexe una versión del sitio: Googlebot rastrea casi
 *      siempre desde EE.UU., así que nunca vería las páginas de El Salvador.
 *   2. Elección manual: si el visitante ya usó el selector de país, esa
 *      decisión manda sobre la geolocalización. Sin esto, alguien en El
 *      Salvador que quiera ver los precios de Guatemala pelearía con el sitio
 *      en cada visita.
 *   3. Geolocalización: El Salvador va a /sv; todo lo demás —y también lo
 *      desconocido— va a /gt.
 */

interface EventContext {
  request: Request;
  next: () => Promise<Response>;
}

const PAISES = ['gt', 'sv'] as const;
const POR_DEFECTO = 'gt';
const COOKIE_PAIS = 'qp-pais';

// Rastreadores de buscadores, redes y modelos de lenguaje. La lista no puede
// ser exhaustiva, y no hace falta: quien no coincida recibe una redirección
// normal, que es el peor caso aceptable.
const BOTS =
  /bot|crawl|spider|slurp|baidu|yandex|duckduck|facebookexternalhit|whatsapp|telegram|twitter|linkedin|embedly|quora|pinterest|slack|discord|applebot|petal|bytespider|ahrefs|semrush|mj12|dotbot|screaming|lighthouse|chrome-lighthouse|gptbot|claude|perplexity|ccbot|google-inspectiontool/i;

function esBot(userAgent: string): boolean {
  return BOTS.test(userAgent);
}

/** Lee la elección manual guardada por el selector de país del navbar. */
function paisElegido(cookies: string): string | null {
  const m = cookies.match(new RegExp(`(?:^|;\\s*)${COOKIE_PAIS}=([^;]+)`));
  const valor = m ? decodeURIComponent(m[1]).toLowerCase() : '';
  return (PAISES as readonly string[]).includes(valor) ? valor : null;
}

export async function onRequestGet(context: EventContext): Promise<Response> {
  const { request, next } = context;

  const userAgent = request.headers.get('User-Agent') ?? '';
  if (esBot(userAgent)) return next();

  const elegido = paisElegido(request.headers.get('Cookie') ?? '');
  const geo = (request.headers.get('CF-IPCountry') ?? '').toUpperCase();
  const destino = elegido ?? (geo === 'SV' ? 'sv' : POR_DEFECTO);

  const url = new URL(request.url);
  // La querystring se conserva: si no, se perderían las UTM y el gclid/fbclid
  // de quien llega desde una campaña, y la atribución se rompería justo en la
  // primera visita.
  const query = url.search;

  return new Response(null, {
    status: 302,
    headers: {
      Location: `/${destino}${query}`,
      // Temporal y sin cachear a propósito: el destino depende de quién pide.
      // Un 301, o una respuesta cacheada, le serviría a todo el mundo el país
      // del primero que haya entrado.
      'Cache-Control': 'no-store',
      Vary: 'Cookie, User-Agent',
    },
  });
}
