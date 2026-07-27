// Reusable visual-regression capture tool for the Astro migration.
//
// Captures a page as a series of fixed-height viewport tiles (scrolling
// through the whole page at a constant step) plus an accessibility-tree
// snapshot. Works against either scroll model this site uses across pages
// (window-level scrolling on the new Astro pages, or the legacy body-level
// `overflow-y:auto` app-shell scrolling still used by the un-migrated
// React pages) by auto-detecting which element actually scrolls.
//
// Usage:
//   node tools/visual-regression/capture.mjs <url> <outDir> [--interactive <script.mjs>]
//
// Writes <outDir>/<viewport>/seg-NN-yYYYY.png and <outDir>/<viewport>.a11y.yaml
// for viewports 375x800, 768x900, 1440x900.

import { chromium } from 'playwright';
import fs from 'node:fs';
import path from 'node:path';

const VIEWPORTS = [
  { name: '375', width: 375, height: 800 },
  { name: '768', width: 768, height: 900 },
  { name: '1440', width: 1440, height: 900 },
];

async function detectScroller(page) {
  return page.evaluate(() => {
    const bodyScrollable = document.body.scrollHeight > document.body.clientHeight + 5;
    const docScrollable = document.documentElement.scrollHeight > document.documentElement.clientHeight + 5;
    if (docScrollable) return 'window';
    if (bodyScrollable) return 'body';
    return 'window';
  });
}

async function scrollTo(page, scroller, y) {
  if (scroller === 'body') {
    await page.evaluate((yy) => document.body.scrollTo(0, yy), y);
  } else {
    await page.evaluate((yy) => window.scrollTo(0, yy), y);
  }
}

async function getScrollHeight(page, scroller) {
  return page.evaluate((s) => (s === 'body' ? document.body.scrollHeight : document.documentElement.scrollHeight), scroller);
}

export async function capturePage(url, outDir, { settleMs = 700, initialWaitMs = 900 } = {}) {
  const browser = await chromium.launch();
  const summary = {};

  for (const vp of VIEWPORTS) {
    const dir = path.join(outDir, vp.name);
    fs.mkdirSync(dir, { recursive: true });
    // clear stale tiles from a previous run so removed content doesn't leave orphan files
    for (const f of fs.readdirSync(dir)) fs.unlinkSync(path.join(dir, f));

    const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(initialWaitMs);

    const scroller = await detectScroller(page);
    const scrollHeight = await getScrollHeight(page, scroller);
    const step = vp.height;
    const tiles = [];

    for (let y = 0; y < scrollHeight; y += step) {
      await scrollTo(page, scroller, y);
      // real wheel nudge as well: some scroll-linked reveal effects only
      // observe genuine wheel/scroll events, not a programmatic jump.
      await page.mouse.wheel(0, 1);
      await page.waitForTimeout(settleMs);
      const file = path.join(dir, `seg-${String(tiles.length).padStart(2, '0')}-y${y}.png`);
      await page.screenshot({ path: file });
      tiles.push({ y, file });
    }

    const a11y = await page.locator('body').ariaSnapshot();
    fs.writeFileSync(path.join(outDir, `${vp.name}.a11y.yaml`), a11y);

    summary[vp.name] = { scroller, scrollHeight, tileCount: tiles.length };
    await page.close();
  }

  await browser.close();
  return summary;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [, , url, outDir] = process.argv;
  if (!url || !outDir) {
    console.error('Usage: node capture.mjs <url> <outDir>');
    process.exit(1);
  }
  const summary = await capturePage(url, outDir);
  console.log(JSON.stringify(summary, null, 2));
}
