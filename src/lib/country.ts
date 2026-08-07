import gt from '../data/countries/gt.json';
import sv from '../data/countries/sv.json';

/**
 * Multipaís. Cada país es un árbol de rutas completo bajo su prefijo
 * (/gt/precios, /sv/precios): la ruta es la misma en ambos y lo que cambia es
 * el contenido. Las páginas idénticas renderizan lo mismo en los dos y el
 * hreflang del layout indica que son variantes por país, no duplicados.
 */
export const COUNTRIES = { gt, sv } as const;

export type CountryCode = keyof typeof COUNTRIES;

export const COUNTRY_CODES = Object.keys(COUNTRIES) as CountryCode[];

/** País al que apunta la raíz del sitio. */
export const DEFAULT_COUNTRY: CountryCode = 'gt';

export const COUNTRY_LABELS: Record<CountryCode, string> = {
  gt: 'Guatemala',
  sv: 'El Salvador',
};

/** Códigos de idioma-región para las etiquetas hreflang. */
export const COUNTRY_HREFLANG: Record<CountryCode, string> = {
  gt: 'es-GT',
  sv: 'es-SV',
};

/** getStaticPaths para cualquier página que exista en todos los países. */
export function countryPaths() {
  return COUNTRY_CODES.map((country) => ({ params: { country } }));
}

export function getCountry(code: string | undefined) {
  const key = (code || DEFAULT_COUNTRY) as CountryCode;
  return COUNTRIES[key] ?? COUNTRIES[DEFAULT_COUNTRY];
}

/**
 * Prefija una ruta interna con el país. Deja pasar sin tocar las URLs
 * externas, los anclas sueltos y los esquemas tel:/mailto:, porque el
 * navbar y el footer mezclan los tres tipos de enlace.
 */
export function withCountry(country: string, path: string) {
  if (!path || /^(https?:|mailto:|tel:|#)/.test(path)) return path;
  const clean = path.startsWith('/') ? path : `/${path}`;
  return `/${country}${clean}`;
}

/**
 * Normaliza la ruta que entrega Astro. Con `build: { format: 'file' }` el
 * pathname del home de un país llega como `/gt.html`, no como `/gt`, así que
 * cualquier lógica que parta la ruta por `/` tiene que quitar la extensión
 * primero o lee el segmento como "gt.html" y no reconoce el país.
 */
export function normalizePath(pathname: string) {
  const clean = pathname.replace(/\.html$/, '').replace(/\/index$/, '');
  return clean === '' ? '/' : clean;
}

/** Código de país que corresponde a una ruta, o el país por defecto. */
export function countryFromPath(pathname: string) {
  const segment = normalizePath(pathname).split('/')[1];
  return (COUNTRY_CODES as string[]).includes(segment)
    ? (segment as CountryCode)
    : DEFAULT_COUNTRY;
}

/**
 * Aplica a un contenido compartido las diferencias de un país.
 *
 * Los sectores (retail, servicios, clínicas…) son el mismo contenido en los dos
 * países salvo por las funciones que El Salvador no tiene habilitadas —cuotas,
 * suscripciones y tokenización—. En vez de duplicar el sector entero, el JSON
 * guarda la versión general y, bajo la clave del país, solo los pedazos que
 * cambian.
 *
 * Los objetos se fusionan campo por campo y los textos y las listas se
 * reemplazan enteros. Una lista también se puede retocar por posición
 * —`{ "blocks": { "0": { "desc": "…" } } }` cambia solo el primer elemento—
 * para no tener que repetir los demás con tal de corregir uno.
 */
function fusionar(base: unknown, cambios: unknown): unknown {
  const esObjeto = (v: unknown) => !!v && typeof v === 'object' && !Array.isArray(v);
  if (!esObjeto(cambios)) return cambios;
  const entradas = Object.entries(cambios as Record<string, unknown>);

  if (Array.isArray(base)) {
    const copia = [...base];
    for (const [indice, valor] of entradas) copia[Number(indice)] = fusionar(copia[Number(indice)], valor);
    return copia;
  }

  const salida: Record<string, unknown> = esObjeto(base) ? { ...(base as object) } : {};
  for (const [clave, valor] of entradas) salida[clave] = fusionar(salida[clave], valor);
  return salida;
}

/**
 * Quita de las listas los elementos marcados con `omitirEn`. Es lo que permite
 * borrar un bloque, una tarjeta o una pregunta completa sin tener que repetir
 * en la variante toda la lista que la contiene.
 */
function podar(nodo: unknown, country: string): unknown {
  if (Array.isArray(nodo)) {
    return nodo
      .filter((item) => {
        const omitir = (item as { omitirEn?: unknown })?.omitirEn;
        return !(Array.isArray(omitir) && omitir.includes(country));
      })
      .map((item) => podar(item, country));
  }
  if (nodo && typeof nodo === 'object') {
    return Object.fromEntries(
      Object.entries(nodo as Record<string, unknown>)
        .filter(([clave]) => clave !== 'omitirEn')
        .map(([clave, valor]) => [clave, podar(valor, country)]),
    );
  }
  return nodo;
}

export function conVarianteDePais<T>(contenido: T, country: string): T {
  if (!contenido || typeof contenido !== 'object') return contenido;
  const entradas = contenido as Record<string, unknown>;
  const variante = entradas[country];

  // Las claves de país nunca se renderizan: son la variante, no el contenido.
  const base = Object.fromEntries(
    Object.entries(entradas).filter(([clave]) => !(COUNTRY_CODES as string[]).includes(clave)),
  );
  return podar(variante ? fusionar(base, variante) : base, country) as T;
}

/** Misma página en otro país, para el selector del navbar. */
export function swapCountry(pathname: string, to: CountryCode) {
  const rest = normalizePath(pathname).replace(/^\/(gt|sv)(?=\/|$)/, '') || '/';
  return `/${to}${rest === '/' ? '' : rest}`;
}
