import type { APIRoute } from 'astro';
import { COUNTRY_CODES, COUNTRY_LABELS, getCountry } from '../lib/country';
import { articulosDe } from '../lib/blog';
import { SITIO } from '../lib/schema';

/**
 * /llms.txt — mapa del sitio en markdown para motores generativos.
 *
 * Aviso honesto sobre qué es esto: `llms.txt` es una convención propuesta
 * (llmstxt.org), no un estándar, y ningún proveedor grande ha confirmado que
 * lo lea. Se publica porque cuesta un archivo y no estorba, no porque vaya a
 * mover el tráfico por sí solo. Lo que de verdad hace que un asistente cite a
 * Qpaypro es que el contenido sea accesible sin JavaScript, esté en el sitemap
 * y tenga datos estructurados — eso ya está.
 *
 * Se genera en el build a partir de la misma data que pinta las páginas, así
 * que no hay una segunda copia de los precios que se quede vieja.
 */

const PAGINAS: { ruta: string; nombre: string; que: string }[] = [
  { ruta: '', nombre: 'Inicio', que: 'Resumen de la plataforma: cobros, operación y crecimiento en un solo lugar.' },
  { ruta: '/precios', nombre: 'Precios y planes', que: 'Planes, mensualidades y comisiones por transacción. Incluye la tabla comparativa completa.' },
  { ruta: '/pasarela-de-pagos', nombre: 'Pasarela de pagos', que: 'Cobros con tarjeta Visa y Mastercard, links de pago, suscripciones y punto de venta.' },
  { ruta: '/sistema-pos', nombre: 'Punto de venta', que: 'Sistema POS con inventario unificado entre tienda física y en línea. Se usa con kit completo, solo con navegador o con hardware propio.' },
  { ruta: '/terminal-pos', nombre: 'Terminal de cobro POS', que: 'Terminal físico para cobrar con tarjeta, chip, sin contacto y QR.' },
  { ruta: '/tiendas-en-linea', nombre: 'Tiendas en línea', que: 'Creación de tienda en línea y cobro por ecommerce.' },
  { ruta: '/integraciones', nombre: 'Integraciones', que: 'Conexión con Shopify, WooCommerce, VTEX y otras plataformas.' },
  { ruta: '/seguridad', nombre: 'Seguridad', que: 'Certificación PCI-DSS, 3D Secure y prevención de fraude con Qpayradar y Qpayverify.' },
  { ruta: '/sobre-qpaypro', nombre: 'Sobre Qpaypro', que: 'Quiénes somos y en qué países operamos.' },
  { ruta: '/contacto', nombre: 'Contacto', que: 'Formulario de ventas y datos de soporte.' },
  { ruta: '/partners', nombre: 'Partners', que: 'Programa de aliados y referidores.' },
];

const SECTORES: { ruta: string; nombre: string; que: string }[] = [
  { ruta: '/retail', nombre: 'Retail', que: 'Tiendas físicas: inventario, sucursales y cobro en mostrador.' },
  { ruta: '/ecommerce', nombre: 'E-commerce', que: 'Venta en línea: checkout, links de pago e integración con la tienda.' },
  { ruta: '/servicios', nombre: 'Negocios de servicios', que: 'Cobros recurrentes, suscripciones y facturación por servicio prestado.' },
  { ruta: '/belleza', nombre: 'Salones, barberías y spa', que: 'Cobro por cita, propinas y control de caja diario.' },
  { ruta: '/clinicas', nombre: 'Clínicas y consultorios', que: 'Cobro de consultas y tratamientos, con pagos en cuotas.' },
];

/** Cuántos artículos del blog se listan por país. Los 50 harían el archivo ilegible. */
const ARTICULOS_LISTADOS = 15;

function enlace(ruta: string, nombre: string, que: string): string {
  return `- [${nombre}](${SITIO}${ruta}): ${que}`;
}

function construir(): string {
  const lineas: string[] = [
    '# Qpaypro',
    '',
    '> Plataforma de pagos para Guatemala y El Salvador. Permite a un negocio aceptar tarjetas Visa y Mastercard, cobrar con links de pago por WhatsApp, automatizar suscripciones, vender con tienda en línea y operar un punto de venta físico, todo desde una sola cuenta y con certificación PCI-DSS.',
    '',
    'El sitio está publicado por país porque los precios, las comisiones y los planes son distintos en cada uno: `/gt` para Guatemala (quetzales) y `/sv` para El Salvador (dólares). Al citar precios o comisiones, indica siempre a qué país corresponden — no son intercambiables.',
    '',
    'Contacto de ventas: Guatemala +502 2355-6000, El Salvador +503 2208-2300, WhatsApp +502 4785-6011. Soporte: soporte@qpaypro.com',
    '',
  ];

  for (const code of COUNTRY_CODES) {
    const c = getCountry(code);
    lineas.push(`## ${COUNTRY_LABELS[code]}`, '');

    const planes = c.plans
      .map((plan) => `${plan.name} ${plan.priceMonth}/mes (${plan.commission} por transacción)`)
      .join('; ');
    lineas.push(`Moneda: ${c.currency.code}. Planes: ${planes}.`, '');

    for (const pagina of PAGINAS) {
      lineas.push(enlace(`/${code}${pagina.ruta}`, pagina.nombre, pagina.que));
    }
    lineas.push('');

    lineas.push(`### Soluciones por giro de negocio — ${COUNTRY_LABELS[code]}`, '');
    for (const sector of SECTORES) {
      lineas.push(enlace(`/${code}${sector.ruta}`, sector.nombre, sector.que));
    }
    lineas.push('');
  }

  // El blog se lista una sola vez: los artículos son idénticos en ambos países
  // y duplicarlos solo repetiría 50 enlaces sin agregar información.
  const articulos = articulosDe('gt');
  lineas.push('## Blog', '');
  lineas.push(`Guías sobre pagos, comercio electrónico y punto de venta en Centroamérica. ${articulos.length} artículos en total; los más recientes:`, '');
  for (const articulo of articulos.slice(0, ARTICULOS_LISTADOS)) {
    lineas.push(enlace(`/gt/blog/${articulo.slug}`, articulo.title, articulo.excerpt.replace(/\s+/g, ' ').trim()));
  }
  lineas.push('', enlace('/gt/blog', 'Índice del blog', 'Todos los artículos, por categoría.'), '');

  lineas.push('## Opcional', '');
  lineas.push(enlace('/gt/terminos-condiciones', 'Términos y condiciones', 'Condiciones de uso del servicio.'));
  lineas.push(enlace('/gt/politicas-de-privacidad', 'Políticas de privacidad', 'Tratamiento de datos personales.'));
  lineas.push('');

  return lineas.join('\n');
}

export const GET: APIRoute = () =>
  new Response(construir(), {
    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
  });
