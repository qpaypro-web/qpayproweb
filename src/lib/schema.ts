import { COUNTRY_HREFLANG, COUNTRY_LABELS, COUNTRY_CODES, normalizePath, type CountryCode } from './country';

/**
 * Datos estructurados (schema.org, JSON-LD).
 *
 * Los buscadores y los motores generativos —ChatGPT con búsqueda, Perplexity,
 * los AI Overviews— leen el mismo marcado: no hay un formato aparte "para
 * LLMs". Lo que sí cambia es qué tan caro les sale entender la página. Con
 * JSON-LD, "Qpaypro opera en Guatemala y El Salvador" o "el plan Premium
 * cuesta Q195 al mes" son datos, no una frase que haya que interpretar.
 *
 * Todo cuelga de dos nodos con @id estable —la organización y el sitio— para
 * que las entidades de cada página los referencien en vez de repetirlos. Sin
 * @id, cada página declara una empresa distinta que se llama igual.
 */

export const SITIO = 'https://www.qpaypro.com';

export const ID_ORGANIZACION = `${SITIO}/#organizacion`;
export const ID_SITIO = `${SITIO}/#sitio`;

const REDES = [
  'https://www.linkedin.com/company/qpaypro',
  'https://www.youtube.com/@qpaypro',
  'https://www.instagram.com/qpaypro',
  'https://www.facebook.com/qpaypro',
];

/** Teléfono de ventas y soporte por país, igual que en el pie de página. */
const TELEFONOS: Record<CountryCode, string> = {
  gt: '+502-2355-6000',
  sv: '+503-2208-2300',
};

export function urlAbsoluta(ruta: string): string {
  return new URL(ruta, SITIO).href;
}

/**
 * Nombre legible de cada segmento de ruta, para las migas de pan. Un slug
 * como "pasarela-de-pagos" es adivinable, pero "sistema-pos" no dice "Punto
 * de venta" y "clinicas" no lleva tilde: conviene escribirlos.
 */
const NOMBRE_DE_RUTA: Record<string, string> = {
  'pasarela-de-pagos': 'Pasarela de pagos',
  'sistema-pos': 'Punto de venta',
  'terminal-pos': 'Terminal de cobro POS',
  'tiendas-en-linea': 'Tiendas en línea',
  integraciones: 'Integraciones',
  precios: 'Precios y planes',
  contacto: 'Contacto',
  seguridad: 'Seguridad',
  'sobre-qpaypro': 'Sobre Qpaypro',
  partners: 'Partners',
  blog: 'Blog',
  categoria: 'Categorías',
  'politicas-de-privacidad': 'Políticas de privacidad',
  'terminos-condiciones': 'Términos y condiciones',
  retail: 'Retail',
  ecommerce: 'E-commerce',
  servicios: 'Servicios',
  belleza: 'Belleza',
  clinicas: 'Clínicas',
};

/** Quita el sufijo de marca del <title> para reusarlo como texto corto. */
export function tituloCorto(titulo: string): string {
  return titulo.split('|')[0].trim();
}

/** La ficha de la empresa. Es el nodo del que cuelga todo lo demás. */
export function organizacion() {
  return {
    '@context': 'https://schema.org',
    '@type': 'Organization',
    '@id': ID_ORGANIZACION,
    name: 'Qpaypro',
    legalName: 'Qpaypro',
    url: SITIO,
    logo: {
      '@type': 'ImageObject',
      url: urlAbsoluta('/logo.svg'),
      contentUrl: urlAbsoluta('/logo.svg'),
    },
    description:
      'Qpaypro es una plataforma de pagos para Guatemala y El Salvador: pasarela de pagos con tarjeta, links de pago, suscripciones, tienda en línea y punto de venta, con certificación PCI-DSS.',
    // areaServed es lo que responde "¿funciona en mi país?", la pregunta que
    // más se le hace a un modelo sobre una pasarela regional.
    areaServed: COUNTRY_CODES.map((code) => ({ '@type': 'Country', name: COUNTRY_LABELS[code] })),
    knowsLanguage: ['es'],
    sameAs: REDES,
    contactPoint: [
      ...COUNTRY_CODES.map((code) => ({
        '@type': 'ContactPoint',
        contactType: 'ventas',
        telephone: TELEFONOS[code],
        areaServed: COUNTRY_LABELS[code],
        availableLanguage: 'es',
      })),
      {
        '@type': 'ContactPoint',
        contactType: 'soporte técnico',
        email: 'soporte@qpaypro.com',
        availableLanguage: 'es',
      },
    ],
  };
}

/** El sitio como entidad, para separar "la web" de "la empresa". */
export function sitioWeb(country: CountryCode) {
  return {
    '@context': 'https://schema.org',
    '@type': 'WebSite',
    '@id': ID_SITIO,
    name: 'Qpaypro',
    url: SITIO,
    inLanguage: COUNTRY_HREFLANG[country],
    publisher: { '@id': ID_ORGANIZACION },
  };
}

/**
 * Migas de pan derivadas de la propia ruta. El primer nivel es el home del
 * país, no la raíz del sitio: `/` solo redirige y no tiene contenido propio.
 */
export function migaDePan(pathname: string, tituloDePagina: string) {
  const ruta = normalizePath(pathname);
  const segmentos = ruta.split('/').filter(Boolean);
  const [pais, ...resto] = segmentos;
  const codigo = (COUNTRY_CODES as string[]).includes(pais) ? (pais as CountryCode) : null;
  if (!codigo || resto.length === 0) return null;

  const items = [{ name: `Qpaypro ${COUNTRY_LABELS[codigo]}`, item: urlAbsoluta(`/${codigo}`) }];
  resto.forEach((segmento, i) => {
    const esUltimo = i === resto.length - 1;
    // El último nivel puede ser un slug de artículo que no está en el mapa;
    // ahí el título de la página es la mejor etiqueta disponible.
    const nombre = NOMBRE_DE_RUTA[segmento] ?? (esUltimo ? tituloCorto(tituloDePagina) : segmento);
    items.push({ name: nombre, item: urlAbsoluta(`/${codigo}/${resto.slice(0, i + 1).join('/')}`) });
  });

  return {
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((entrada, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: entrada.name,
      item: entrada.item,
    })),
  };
}

interface ServicioOpciones {
  nombre: string;
  tipo: string;
  descripcion: string;
  url: string;
  country: CountryCode;
  /** Prestaciones concretas: es lo que un modelo cita al comparar productos. */
  incluye?: string[];
}

export function servicio({ nombre, tipo, descripcion, url, country, incluye }: ServicioOpciones) {
  const nodo: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'Service',
    name: nombre,
    serviceType: tipo,
    description: descripcion,
    url: urlAbsoluta(url),
    provider: { '@id': ID_ORGANIZACION },
    areaServed: { '@type': 'Country', name: COUNTRY_LABELS[country] },
    inLanguage: COUNTRY_HREFLANG[country],
  };
  if (incluye?.length) {
    nodo.hasOfferCatalog = {
      '@type': 'OfferCatalog',
      name: `${nombre} — qué incluye`,
      itemListElement: incluye.map((item) => ({
        '@type': 'Offer',
        itemOffered: { '@type': 'Service', name: item },
      })),
    };
  }
  return nodo;
}

export function preguntasFrecuentes(faq: { q: string; a: string }[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: faq.map((item) => ({
      '@type': 'Question',
      name: item.q,
      acceptedAnswer: { '@type': 'Answer', text: item.a },
    })),
  };
}

/**
 * Convierte "Q1,950" o "$25" en 1950 / 25. Los precios se guardan ya
 * formateados para pintarlos tal cual; schema.org exige el número solo, con
 * la moneda en un campo aparte.
 */
export function precioNumerico(formateado: string): number | null {
  const n = Number(formateado.replace(/[^\d.]/g, ''));
  return Number.isFinite(n) ? n : null;
}

interface Plan {
  name: string;
  tagline: string;
  priceMonth: string;
  commission: string;
  url: string;
}

/**
 * Los planes como catálogo de ofertas. Es la página con más valor de cita del
 * sitio: "¿cuánto cuesta Qpaypro en Guatemala?" se responde con estos datos.
 */
export function catalogoDePlanes(country: CountryCode, moneda: string, planes: Plan[]) {
  return {
    '@context': 'https://schema.org',
    '@type': 'Product',
    name: `Qpaypro ${COUNTRY_LABELS[country]}`,
    description: `Planes de la plataforma de pagos Qpaypro en ${COUNTRY_LABELS[country]}: pagos con tarjeta, links de pago, suscripciones, tienda en línea y punto de venta.`,
    brand: { '@id': ID_ORGANIZACION },
    url: urlAbsoluta(`/${country}/precios`),
    offers: planes
      .map((plan) => {
        const precio = precioNumerico(plan.priceMonth);
        if (precio === null) return null;
        return {
          '@type': 'Offer',
          name: `Plan ${plan.name}`,
          description: `${plan.tagline} Comisión: ${plan.commission} por transacción.`,
          price: precio,
          priceCurrency: moneda,
          // El precio es la mensualidad: sin esto el número queda ambiguo
          // entre pago único y recurrente.
          priceSpecification: {
            '@type': 'UnitPriceSpecification',
            price: precio,
            priceCurrency: moneda,
            billingDuration: 1,
            billingIncrement: 1,
            unitCode: 'MON',
          },
          availability: 'https://schema.org/InStock',
          url: plan.url.startsWith('http') ? plan.url : urlAbsoluta(`/${country}${plan.url}`),
          eligibleRegion: { '@type': 'Country', name: COUNTRY_LABELS[country] },
        };
      })
      .filter(Boolean),
  };
}
