const fs = require('fs');
const path = require('path');
const BUILD = __dirname;
const DOCS = path.resolve(BUILD, '..');

function extract(mdFile, outFile) {
  const md = fs.readFileSync(path.join(DOCS, mdFile), 'utf8').replace(/^﻿/, '');
  const m = md.match(/```mermaid\r?\n([\s\S]*?)```/);
  if (!m) throw new Error('no mermaid block in ' + mdFile);
  // write as UTF-8 without BOM
  fs.writeFileSync(path.join(BUILD, outFile), m[1].trimEnd() + '\n', { encoding: 'utf8' });
  console.log('wrote', outFile, m[1].length, 'chars');
}

extract('architecture-diagram.md', 'arch.mmd');
extract('flow-diagram.md', 'flow.mmd');
