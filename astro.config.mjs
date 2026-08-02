// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import tailwindcss from '@tailwindcss/vite';

// https://astro.build/config
export default defineConfig({
  // Sin esto Astro no puede construir URLs absolutas: el sitemap no se genera y
  // los hreflang salen relativos, que Google ignora. Es el dominio canónico,
  // con www, que es al que resuelve el sitio.
  site: 'https://www.qpaypro.com',
  output: 'static',
  trailingSlash: 'never',
  build: {
    format: 'file',
  },
  integrations: [
    // Genera sitemap-index.xml y sitemap-0.xml en cada build, con las 146
    // páginas. Es lo que se le entrega a Search Console después de la
    // migración para que descubra las rutas nuevas sin esperar al rastreo.
    sitemap({
      // La raíz solo redirige y el 404 no debe indexarse.
      filter: (pagina) => !pagina.endsWith('/404') && pagina !== 'https://www.qpaypro.com/',
    }),
  ],
  vite: {
    plugins: [tailwindcss()],
  },
});
