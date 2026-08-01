import articles from '../data/blog-articles.json';
import categorias from '../data/blog-categorias.json';

/**
 * Capa de consulta del blog. Todo lo que las páginas necesitan saber sobre los artículos pasa
 * por aquí, para que el filtrado por país y el orden por fecha no queden repetidos en cada
 * plantilla.
 */
export interface Bloque {
  type: 'p' | 'h2' | 'h3' | 'ul' | 'ol' | 'quote' | 'callout' | 'cta';
  text?: string;
  items?: string[];
}

export interface Articulo {
  slug: string;
  slugWp: string;
  title: string;
  excerpt: string;
  date: string;
  cats: string[];
  countries: string[];
  cover: { src: string; alt: string; w: number | null; h: number | null };
  readingMinutes: number;
  body: Bloque[];
}

export interface Categoria {
  slug: string;
  name: string;
  description: string;
}

export const CATEGORIAS = categorias as Categoria[];

/** La firma es la misma en todos los artículos: no hay autores individuales. */
export const FIRMA = 'Equipo de medios de QPayPro';

const TODOS = (articles as Articulo[]).slice().sort((a, b) => (a.date < b.date ? 1 : -1));

/**
 * Artículos visibles en un país. Hoy los 50 salen en los dos, pero el campo se respeta para
 * que excluir uno sea editar su `countries` y nada más.
 */
export function articulosDe(country: string): Articulo[] {
  return TODOS.filter((a) => a.countries.includes(country));
}

export function articulo(slug: string): Articulo | undefined {
  return TODOS.find((a) => a.slug === slug);
}

export function categoria(slug: string): Categoria | undefined {
  return CATEGORIAS.find((c) => c.slug === slug);
}

export function nombreCategoria(slug: string): string {
  return categoria(slug)?.name ?? slug;
}

/** Categorías que tienen al menos un artículo en ese país, en el orden de blog-categorias.json. */
export function categoriasDe(country: string): Categoria[] {
  const usadas = new Set(articulosDe(country).flatMap((a) => a.cats));
  return CATEGORIAS.filter((c) => usadas.has(c.slug));
}

export function articulosDeCategoria(country: string, cat: string): Articulo[] {
  return articulosDe(country).filter((a) => a.cats.includes(cat));
}

/**
 * Relacionados por categoría compartida, completando con los más recientes si no alcanzan.
 * Antes se tomaban tres por posición en el arreglo, lo que emparejaba artículos sin relación.
 */
export function relacionados(country: string, slug: string, cuantos = 3): Articulo[] {
  const actual = articulo(slug);
  if (!actual) return [];
  const otros = articulosDe(country).filter((a) => a.slug !== slug);
  const mismos = otros.filter((a) => a.cats.some((c) => actual.cats.includes(c)));
  const resto = otros.filter((a) => !mismos.includes(a));
  return [...mismos, ...resto].slice(0, cuantos);
}

const MESES = [
  'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
];

/** "2024-07-09" -> "9 de julio de 2024". Sin Date para que no dependa de la zona horaria. */
export function fechaLarga(iso: string): string {
  const [a, m, d] = iso.split('-').map(Number);
  return `${d} de ${MESES[m - 1]} de ${a}`;
}

/** Los encabezados de nivel 2, que alimentan el índice del artículo. */
export function indiceDe(body: Bloque[]): { id: string; text: string }[] {
  return body
    .filter((b) => b.type === 'h2' && b.text)
    .map((b) => ({ id: idDeEncabezado(b.text!), text: quitarHtml(b.text!) }));
}

export function idDeEncabezado(texto: string): string {
  return quitarHtml(texto)
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
}

export function quitarHtml(s: string): string {
  return s.replace(/<[^>]+>/g, '').trim();
}
