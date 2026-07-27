// Pixel-diffs two capture.mjs output directories (baseline vs. current) tile
// by tile, plus a plain-text diff of the accessibility-tree snapshots.
//
// Tiles are matched by index, not by absolute scroll position, so pages
// whose total height differs by more than a few pixels will show growing
// misalignment in later tiles even when the content is correct — treat a
// flagged tile as "go look at it", not as proof of a regression. Continuously
// looping CSS animations (e.g. the rotating decorative orbs/cube) will also
// never pixel-match between two independent captures; that's expected noise,
// not a bug. Use `diffPixels`/a visual look at the emitted _diff/ image to
// judge each flagged tile rather than trusting the ratio alone.
//
// Usage: node tools/visual-regression/diff.mjs <baselineDir> <currentDir> [--threshold 0.03]

import fs from 'node:fs';
import path from 'node:path';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';

function loadPng(file) {
  return PNG.sync.read(fs.readFileSync(file));
}

export function diffDirs(baselineDir, currentDir, { threshold = 0.03 } = {}) {
  const viewports = fs
    .readdirSync(baselineDir)
    .filter((f) => fs.statSync(path.join(baselineDir, f)).isDirectory());

  const results = [];

  for (const vp of viewports) {
    const baseVpDir = path.join(baselineDir, vp);
    const curVpDir = path.join(currentDir, vp);
    if (!fs.existsSync(curVpDir)) {
      results.push({ viewport: vp, tile: null, status: 'MISSING_CURRENT_VIEWPORT' });
      continue;
    }

    const baseFiles = fs.readdirSync(baseVpDir).filter((f) => f.endsWith('.png')).sort();
    const curFiles = fs.readdirSync(curVpDir).filter((f) => f.endsWith('.png')).sort();
    const tileCount = Math.max(baseFiles.length, curFiles.length);

    for (let i = 0; i < tileCount; i++) {
      const baseFile = baseFiles[i];
      const curFile = curFiles[i];
      if (!baseFile || !curFile) {
        results.push({ viewport: vp, tile: i, status: baseFile ? 'MISSING_IN_CURRENT' : 'EXTRA_IN_CURRENT', file: baseFile || curFile });
        continue;
      }
      const img1 = loadPng(path.join(baseVpDir, baseFile));
      const img2 = loadPng(path.join(curVpDir, curFile));
      if (img1.width !== img2.width || img1.height !== img2.height) {
        results.push({ viewport: vp, tile: i, status: 'SIZE_MISMATCH', base: `${img1.width}x${img1.height}`, current: `${img2.width}x${img2.height}` });
        continue;
      }
      const diffPng = new PNG({ width: img1.width, height: img1.height });
      const diffPixels = pixelmatch(img1.data, img2.data, diffPng.data, img1.width, img1.height, { threshold: 0.1 });
      const totalPixels = img1.width * img1.height;
      const ratio = diffPixels / totalPixels;
      const status = ratio > threshold ? 'DIFF' : 'OK';
      if (status === 'DIFF') {
        const diffOutDir = path.join(currentDir, '_diff', vp);
        fs.mkdirSync(diffOutDir, { recursive: true });
        fs.writeFileSync(path.join(diffOutDir, `${baseFile}`), PNG.sync.write(diffPng));
      }
      results.push({ viewport: vp, tile: i, status, diffPixels, totalPixels, ratio: +ratio.toFixed(5), file: baseFile });
    }
  }

  return results;
}

export function diffA11y(baselineDir, currentDir) {
  const reports = [];
  const files = fs.readdirSync(baselineDir).filter((f) => f.endsWith('.a11y.yaml'));
  for (const f of files) {
    const baseContent = fs.readFileSync(path.join(baselineDir, f), 'utf-8').trim();
    const curPath = path.join(currentDir, f);
    if (!fs.existsSync(curPath)) {
      reports.push({ file: f, status: 'MISSING_IN_CURRENT' });
      continue;
    }
    const curContent = fs.readFileSync(curPath, 'utf-8').trim();
    reports.push({ file: f, status: baseContent === curContent ? 'OK' : 'DIFF', identical: baseContent === curContent });
  }
  return reports;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const [, , baselineDir, currentDir] = process.argv;
  if (!baselineDir || !currentDir) {
    console.error('Usage: node diff.mjs <baselineDir> <currentDir>');
    process.exit(1);
  }
  const pixelResults = diffDirs(baselineDir, currentDir);
  const a11yResults = diffA11y(baselineDir, currentDir);

  console.log('=== Pixel diff ===');
  const bad = pixelResults.filter((r) => r.status !== 'OK');
  for (const r of pixelResults) {
    const label = r.tile !== null ? `${r.viewport}/tile-${r.tile}` : r.viewport;
    if (r.status === 'OK') {
      console.log(`  OK   ${label} (${(r.ratio * 100).toFixed(3)}% diff)`);
    } else {
      console.log(`  ${r.status}  ${label}`, r.ratio !== undefined ? `(${(r.ratio * 100).toFixed(2)}% diff)` : '');
    }
  }

  console.log('\n=== Accessibility tree diff ===');
  for (const r of a11yResults) {
    console.log(`  ${r.status}  ${r.file}`);
  }

  const failed = bad.length > 0 || a11yResults.some((r) => r.status !== 'OK');
  console.log(`\n${failed ? 'FAILED' : 'PASSED'}: ${bad.length} pixel issue(s), ${a11yResults.filter((r) => r.status !== 'OK').length} a11y issue(s)`);
  process.exit(failed ? 1 : 0);
}
