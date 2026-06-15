const fs = require('fs');
const path = require('path');

const NM = 'C:/Users/40747/AppData/Local/npm-cache/_npx/55158e48eb5c59f7/node_modules';
const CHROME = 'C:/Users/40747/.cache/puppeteer/chrome/win64-149.0.7827.22/chrome-win64/chrome.exe';
const BUILD = __dirname;
const DOCS = path.resolve(BUILD, '..');

const markedMod = require(NM + '/marked');
const marked = markedMod.marked || markedMod;
const puppeteer = require(NM + '/puppeteer');

function prepare(mdFile, svgFile) {
  let md = fs.readFileSync(path.join(DOCS, mdFile), 'utf8').replace(/^﻿/, '');
  // drop the ASCII-diagram section (heading until next "## ")
  md = md.replace(/\n##\s+Diagram[ăa] ASCII[^\n]*\n[\s\S]*?(?=\n##\s)/, '\n');
  // replace the mermaid fence with the pre-rendered SVG
  const svg = fs.readFileSync(path.join(BUILD, svgFile), 'utf8').replace(/^﻿/, '');
  md = md.replace(/```mermaid[\s\S]*?```/, '\n<div class="diagram">' + svg + '</div>\n');
  return md;
}

function main() {
  const archMd = prepare('architecture-diagram.md', 'combined.rendered-1.svg');
  const flowMd = prepare('flow-diagram.md', 'combined.rendered-2.svg');

  const archHtml = marked.parse(archMd);
  const flowHtml = marked.parse(flowMd);
  const html = archHtml + '\n<div class="page-break"></div>\n' + flowHtml;

  const css = `
    body { font-family: Segoe UI, Helvetica, Arial, sans-serif; font-size: 13px; color: #1a1a1a; margin: 0; }
    h1 { font-size: 23px; border-bottom: 2px solid #333; padding-bottom: 5px; }
    h2 { font-size: 17px; margin-top: 20px; }
    .diagram { text-align: center; margin: 18px 0; }
    .diagram svg { max-width: 100%; height: auto; }
    .page-break { page-break-before: always; }
    ul { line-height: 1.6; }
    strong { color: #111; }
  `;

  const doc = `<!doctype html><html><head><meta charset="utf-8"><style>${css}</style></head><body>${html}</body></html>`;
  fs.writeFileSync(path.join(BUILD, 'combined.final.html'), doc, 'utf8');

  (async () => {
    const browser = await puppeteer.launch({
      executablePath: CHROME,
      headless: 'new',
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });
    const page = await browser.newPage();
    await page.setContent(doc, { waitUntil: 'load', timeout: 60000 });
    await page.pdf({
      path: path.join(BUILD, 'diagrams.pdf'),
      format: 'A4',
      printBackground: true,
      margin: { top: '14mm', bottom: '14mm', left: '14mm', right: '14mm' },
    });
    await browser.close();
    console.log('PDF_DONE');
  })().catch((e) => { console.error('ERR', e); process.exit(1); });
}

main();
