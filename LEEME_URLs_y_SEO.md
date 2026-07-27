# Qpaypro — Sitio web (URLs, SEO y enlaces del navbar)

## URLs limpias (recomendadas)
| Archivo                  | URL                     | Página                       |
|--------------------------|-------------------------|------------------------------|
| index.html               | /                       | Home                         |
| pasarela-de-pagos.html   | /pasarela-de-pagos      | Soluciones de pago           |
| tiendas-en-linea.html    | /tiendas-en-linea       | Tiendas en línea (ecommerce) |
| sistema-pos.html         | /sistema-pos            | Sistema POS / punto de venta |
| pos-cute.html            | /pos-cute               | POS Cute                     |
| precios.html             | /precios                | Precios y planes             |
| integraciones.html       | /integraciones          | Integraciones                |
| seguridad.html           | /seguridad              | Seguridad                    |
| partners.html            | /partners               | Programa de partners         |
| sobre-qpaypro.html       | /sobre-qpaypro          | Sobre Qpaypro                |
| contacto.html            | /contacto               | Contacto                     |
| blog.html                | /blog                   | Blog                         |
| articulo.html            | /blog/{slug}            | Artículo (ruteo por #slug)   |
| retail/servicios/ecommerce/belleza/clinicas .html | /retail, /servicios, ... | Sectores       |

## SEO aplicado
- title + meta description únicos por página, robots index/follow, Open Graph (es_GT), JSON-LD (Organization/servicio + FAQ). El artículo actualiza su title dinámicamente.

## Navbar — enlaces ya vinculados
- Logo → index.html
- Productos: POS Cute → pos-cute.html · Punto de Venta → sistema-pos.html · Integraciones → integraciones.html · Soluciones → pasarela-de-pagos.html
- Precios → precios.html · Contacto → contacto.html
- Empresa y Recursos: Sobre → sobre-qpaypro.html · Seguridad → seguridad.html · Partners → partners.html
- Desarrolladores: Documentación API → https://developers.qpaypro.com/ · Plugins → https://qpaypro.zohodesk.com/portal/es/kb/payments/integraciones
- Soporte: WhatsApp → api.whatsapp.com (50247856011) · Centro de ayuda Qpaypro → qpaypro.zohodesk.com/portal/es/home · Centro de ayuda Qpayshop → help.shopsettings.com/hc/es
- Ingresa: Qpaypro → https://app.qpaypro.com · Qpayshop → https://my.shopsettings.com/p/qpayshop
- (Los enlaces externos abren en pestaña nueva.)

## Pendientes del equipo de desarrollo
1. SSR o pre-render (las páginas son React del lado del cliente) para que Google/IA lean contenido y JSON-LD.
2. Publicar cada artículo en /blog/{slug} con su propio título y meta.
3. Mover la librería de medios del blog (imágenes) al nuevo hosting.
4. Conectar el formulario de contacto al CRM + reCAPTCHA/hCaptcha real.
5. Botones internos restantes (Comenzar, Comprar, Más información, Ver Sistema POS) a sus rutas.
6. sitemap.xml + canonical por ruta.
