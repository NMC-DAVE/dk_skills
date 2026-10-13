#!/usr/bin/env node
/** Extract the small official IDL discovery index from a vscode-idl checkout. */
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const TYPES = { f: 'Function', p: 'Procedure', fm: 'FunctionMethod', pm: 'ProcedureMethod', s: 'StructureOrClassDefinition', sv: 'SystemVariable' };
export function buildCatalog(upstream) {
  const content = fs.readFileSync(path.join(upstream, 'resources/idl/routines/routines.json'));
  const routines = new Map();
  for (const row of JSON.parse(content.toString('utf8'))) {
    if (!row.name || !['idl', 'internal'].includes(row.source) || !row.link?.startsWith('/idl/') || !TYPES[row.type]) continue;
    const type = TYPES[row.type];
    routines.set(row.name.toLowerCase() + '\0' + type, { name: row.name, type, source: row.source, link: row.link });
  }
  return { upstream: 'https://github.com/interactive-data-language/vscode-idl',
    upstream_version: JSON.parse(fs.readFileSync(path.join(upstream, 'package.json'), 'utf8')).version,
    source_file: 'resources/idl/routines/routines.json', source_sha256: createHash('sha256').update(content).digest('hex'),
    rule: 'Named idl/internal entries with /idl/ links; deduplicate by lowercase name and routine type.',
    routines: [...routines.entries()].sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0).map(([, row]) => row) };
}
if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [upstream, flag, output] = process.argv.slice(2);
  if (!upstream || flag !== '--output' || !output) {
    console.error('Usage: node build_catalog.mjs <upstream> --output <routine-index.json>'); process.exitCode = 1;
  } else {
    const catalog = buildCatalog(upstream);
    fs.mkdirSync(path.dirname(path.resolve(output)), { recursive: true });
    fs.writeFileSync(output, JSON.stringify(catalog) + '\n', 'utf8');
    console.log(`Wrote ${catalog.routines.length} IDL entries`);
  }
}
