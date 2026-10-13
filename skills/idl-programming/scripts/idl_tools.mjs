#!/usr/bin/env node
/** Standalone IDL discovery and validation. Node.js 18+, built-in modules only. */
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { spawn, execFileSync } from 'node:child_process';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const SCRIPT = fileURLToPath(import.meta.url);
const SKILL_ROOT = path.dirname(path.dirname(SCRIPT));
const ANSI = /\x1b\[[0-?]*[ -/]*[@-~]/g;
const ENTRY = /^[a-z_]\w*$/i;
export class IDLToolError extends Error {}
const isFile = p => { try { return fs.statSync(p).isFile(); } catch { return false; } };
const isDirectory = p => { try { return fs.statSync(p).isDirectory(); } catch { return false; } };
const cleanText = text => text.replace(/^\uFEFF/, '');
const expandHome = p => p === '~' ? os.homedir() : p.startsWith('~/') || p.startsWith('~\\') ? path.join(os.homedir(), p.slice(2)) : p;

export function windowsPaths() {
  if (process.platform !== 'win32') return [];
  // Read the registry-backed PATH as Unicode JSON; never change environment settings.
  const command = `[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); @([Environment]::GetEnvironmentVariable('Path','User'), [Environment]::GetEnvironmentVariable('Path','Machine')) | ConvertTo-Json -Compress`;
  try {
    const values = JSON.parse(execFileSync('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', command],
      { encoding: 'utf8', windowsHide: true, timeout: 10000 }));
    return values.flatMap(value => (value || '').split(';'));
  } catch { return []; }
}

export function findIDL(explicit = null, options = {}) {
  const platform = options.platform || process.platform;
  const environment = options.env || process.env;
  const current = Object.entries(environment).find(([key]) => key.toLowerCase() === 'path')?.[1] || '';
  const suffix = platform === 'win32' ? '.exe' : '';
  const findIn = (name, directories) => {
    for (let directory of directories) {
      directory = directory.trim().replace(/^"|"$/g, '').replace(/%([^%]+)%/g, (_, key) => environment[key] || `%${key}%`);
      if (!directory) continue;
      const candidate = path.resolve(directory, name);
      if (isFile(candidate)) {
        try { fs.accessSync(candidate, platform === 'win32' ? fs.constants.F_OK : fs.constants.X_OK); }
        catch { continue; }
        return fs.realpathSync(candidate);
      }
    }
    return null;
  };
  const currentDirectories = current.split(platform === 'win32' ? ';' : ':');
  if (explicit) {
    const candidate = path.resolve(expandHome(explicit));
    if (isFile(candidate)) return fs.realpathSync(candidate);
    const found = findIn(explicit.endsWith(suffix) ? explicit : explicit + suffix, currentDirectories);
    if (found) return found;
    throw new IDLToolError(`IDL executable not found: ${explicit}`);
  }
  const found = findIn('idl' + suffix, currentDirectories);
  if (found) return found;
  const registered = (options.registryPaths || windowsPaths)();
  const fallback = findIn('idl' + suffix, registered);
  if (fallback) return fallback;
  throw new IDLToolError('IDL not found in current/system/user PATH; pass --idl PATH. No configuration was changed.');
}

export function idlString(value) {
  if (/[\r\n\0]/.test(value)) throw new IDLToolError('Newlines and NUL are not allowed in IDL arguments');
  return "'" + value.replaceAll("'", "''") + "'";
}

export function compileCommand(filename) {
  if (/[\r\n\0"]/.test(filename)) throw new IDLToolError('File path cannot be represented in an IDL .compile command');
  return '.compile "' + filename + '"';
}

export function invoke(idl, commands, cwd, timeout, dataArgs = [], spawnImpl = spawn) {
  // Only ASCII command text crosses the Windows pipe. Unicode paths travel through native argv.
  if (process.platform === 'win32' && commands.some(command => /[^\x00-\x7f]/.test(command))) {
    throw new IDLToolError('Use native process arguments, not console command text, for Unicode paths');
  }
  return new Promise((resolve, reject) => {
    let child;
    try { child = spawnImpl(idl, ['-quiet', ...(dataArgs.length ? ['-args', ...dataArgs] : [])],
      { cwd, windowsHide: true, shell: false, stdio: ['pipe', 'pipe', 'pipe'] }); }
    catch (error) { reject(new IDLToolError(`Could not start IDL: ${error.message}`)); return; }
    const chunks = [];
    let timedOut = false;
    const timer = setTimeout(() => { timedOut = true; child.kill('SIGKILL'); }, timeout * 1000);
    child.stdout.on('data', data => chunks.push(Buffer.from(data)));
    child.stderr.on('data', data => chunks.push(Buffer.from(data)));
    child.stdin.on('error', () => {}); // Early exit/failed license: report process output, not EPIPE.
    child.on('error', error => { clearTimeout(timer); reject(new IDLToolError(`Could not start IDL: ${error.message}`)); });
    child.on('close', code => {
      clearTimeout(timer);
      resolve({ returncode: code, timed_out: timedOut, output: Buffer.concat(chunks).toString('utf8').replace(ANSI, '') });
    });
    child.stdin.end(commands.join('\n') + '\n', 'utf8');
  });
}

export async function doctor(idl, cwd, timeout = 60, execute = invoke) {
  const token = 'DKIDL' + randomUUID().replaceAll('-', '');
  const processResult = await execute(idl, [`print, '${token}BEGIN'`, `print, '${token}VERSION=' + !VERSION.RELEASE`,
    `print, '${token}DIR=' + !DIR`, `print, '${token}PATH=' + !PATH`, `print, '${token}END'`, 'exit'], cwd, timeout);
  const fields = {};
  for (const key of ['VERSION', 'DIR', 'PATH']) {
    fields[key] = processResult.output.match(new RegExp(token + key + '=([^\\r\\n]*)'))?.[1].trim() || '';
  }
  const ok = !processResult.timed_out && processResult.returncode === 0 && Object.values(fields).every(Boolean)
    && processResult.output.includes(token + 'END');
  const helpRoot = fields.DIR ? path.join(fields.DIR, 'help/online_help/Subsystems') : null;
  return { ok, executable: idl, version: fields.VERSION || null, idl_dir: fields.DIR || null,
    idl_path: fields.PATH.split(path.delimiter), help_root: helpRoot && isDirectory(helpRoot) ? helpRoot : null,
    process: processResult, note: ok ? null : 'Compilation/runtime verification is unavailable' };
}

export function loadCatalog() {
  return JSON.parse(fs.readFileSync(path.join(SKILL_ROOT, 'references/routine-index.json'), 'utf8')).routines;
}

export function docPath(helpRoot, link) {
  const raw = decodeURIComponent(link.split('#')[0]).replace(/^\/+/, '');
  const root = fs.existsSync(helpRoot) ? fs.realpathSync(helpRoot) : path.resolve(helpRoot);
  const lexical = path.resolve(root, raw);
  const candidate = fs.existsSync(lexical) ? fs.realpathSync(lexical) : lexical;
  const relative = path.relative(root, candidate);
  if (relative === '..' || relative.startsWith('..' + path.sep) || path.isAbsolute(relative)) {
    throw new IDLToolError('Documentation path escapes the help directory');
  }
  return candidate;
}

const ENTITIES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', ndash: '–', mdash: '—',
  minus: '−', times: '×', le: '≤', ge: '≥', pi: 'π', copy: '©', reg: '®', hellip: '…' };
function decodeEntities(text) {
  return text.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, entity) => {
    if (!entity.startsWith('#')) return ENTITIES[entity] ?? whole;
    const value = entity[1].toLowerCase() === 'x' ? parseInt(entity.slice(2), 16) : parseInt(entity.slice(1), 10);
    return value <= 0x10ffff && !(value >= 0xd800 && value <= 0xdfff) ? String.fromCodePoint(value) : whole;
  });
}

export function extractHelp(html) {
  const blocks = new Set(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'pre', 'br', 'li', 'tr', 'table']);
  const voids = new Set(['area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'wbr']);
  const chunks = [], stack = [];
  // Remove raw-text blocks before tokenization so embedded '<' cannot corrupt nesting.
  const source = html.replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, '').replace(/<!--[\s\S]*?-->/g, '');
  for (const token of source.match(/<[^>]*>|[^<]+/g) || []) {
    if (!token.startsWith('<')) {
      if (stack.at(-1)?.active && !stack.at(-1)?.skip) chunks.push(decodeEntities(token));
      continue;
    }
    const closing = token.match(/^<\/\s*([\w:-]+)/);
    if (closing) {
      const tag = closing[1].toLowerCase();
      const index = stack.map(item => item.tag).lastIndexOf(tag);
      if (index >= 0) {
        if (stack[index].active && !stack[index].skip && blocks.has(tag)) chunks.push('\n');
        stack.splice(index);
      }
      continue;
    }
    const opening = token.match(/^<\s*([\w:-]+)/);
    if (!opening) continue;
    const tag = opening[1].toLowerCase(), attrs = {};
    const attrText = token.slice(opening[0].length).replace(/\/?\s*>$/, '');
    for (const match of attrText.matchAll(/([\w:-]+)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+)))?/g)) {
      attrs[match[1].toLowerCase()] = decodeEntities(match[2] ?? match[3] ?? match[4] ?? '');
    }
    const active = stack.at(-1)?.active || attrs.id === 'mc-main-content' || tag === 'main';
    const skip = stack.at(-1)?.skip || tag === 'nav' || Object.hasOwn(attrs, 'hidden') || attrs['aria-hidden'] === 'true'
      || (attrs.class || '').toLowerCase().split(/\s+/).includes('hidden')
      || (attrs.style || '').replace(/\s/g, '').toLowerCase().includes('display:none');
    if (active && !skip) {
      if (blocks.has(tag)) chunks.push('\n');
      else if (tag === 'td' || tag === 'th') chunks.push(' | ');
    }
    if (!voids.has(tag) && !/\/\s*>$/.test(token)) stack.push({ tag, active, skip });
  }
  return chunks.join('').split(/\r?\n/).map(line => line.replace(/[\t \u00a0]+/g, ' ').trim()).join('\n')
    .replace(/\n{3,}/g, '\n\n').trim();
}

export function readHelp(filename) {
  const text = extractHelp(cleanText(fs.readFileSync(filename, 'utf8')));
  if (!text) throw new IDLToolError(`No main documentation content extracted from ${filename}`);
  return text;
}

function* walkFiles(root, excluded = new Set()) {
  if (!isDirectory(root)) return;
  for (const item of fs.readdirSync(root, { withFileTypes: true })) {
    if (item.isSymbolicLink()) continue;
    const filename = path.join(root, item.name);
    if (item.isDirectory() && !excluded.has(item.name)) yield* walkFiles(filename, excluded);
    else if (item.isFile()) yield filename;
  }
}

export function projectRoutines(project) {
  const excluded = new Set(['.git', '.venv', 'node_modules', 'outputs', 'output', 'tmp', 'temp']);
  const result = [];
  for (const filename of walkFiles(path.resolve(project), excluded)) {
    if (!filename.toLowerCase().endsWith('.pro')) continue;
    const text = cleanText(fs.readFileSync(filename, 'utf8'));
    for (const match of text.matchAll(/^[ \t]*(pro|function)\s+([a-z_]\w*(?:::[a-z_]\w*)?)\b/gim)) {
      result.push({ name: match[2], type: (match[1].toLowerCase() === 'pro' ? 'Procedure' : 'Function')
        + (match[2].includes('::') ? 'Method' : ''), source: 'project', file: filename,
        line: text.slice(0, match.index).split('\n').length });
    }
  }
  return result;
}

export function search(query, { kind = null, project = null, helpRoot = null, fullText = false, limit = 20, catalog = loadCatalog() } = {}) {
  const words = query.toLowerCase().trim().split(/\s+/);
  if (!words[0]) throw new IDLToolError('Search query must not be empty');
  const matches = [], documents = new Map();
  for (const row of [...catalog, ...(project ? projectRoutines(project) : [])]) {
    if (kind && row.type.toLowerCase() !== kind.toLowerCase()) continue;
    const name = row.name.toLowerCase();
    const inName = words.every(word => name.includes(word));
    let matched = inName, text = '';
    if (!matched && fullText && helpRoot && row.link) {
      const filename = docPath(helpRoot, row.link);
      if (isFile(filename)) {
        if (!documents.has(filename)) documents.set(filename, readHelp(filename));
        text = documents.get(filename);
        matched = words.every(word => text.toLowerCase().includes(word));
      }
    }
    if (matched) {
      const hit = { ...row };
      if (text) { const position = text.toLowerCase().indexOf(words[0]); hit.excerpt = text.slice(Math.max(0, position - 60), position + 240); }
      matches.push({ score: name === query.toLowerCase() ? 0 : inName ? 1 : 2, hit });
    }
  }
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  matches.sort((a, b) => a.score - b.score || compare(a.hit.name.toLowerCase(), b.hit.name.toLowerCase()) || compare(a.hit.type, b.hit.type));
  return { ok: true, query, total: matches.length, matches: matches.slice(0, limit).map(item => item.hit),
    note: 'Index is a discovery snapshot, not proof of installed availability or version compatibility.' };
}

export function getDocs(name, { kind = null, helpRoot = null, version = null, project = null, catalog = loadCatalog() } = {}) {
  const candidates = [...catalog, ...(project ? projectRoutines(project) : [])].filter(row => row.name.toLowerCase() === name.toLowerCase()
    && (!kind || row.type.toLowerCase() === kind.toLowerCase()));
  if (!candidates.length && helpRoot && ENTRY.test(name)) {
    for (const filename of walkFiles(path.join(helpRoot, 'idl'))) {
      if (path.extname(filename).toLowerCase() === '.htm' && path.basename(filename, path.extname(filename)).toLowerCase() === name.toLowerCase()) {
        candidates.push({ name, type: 'Unknown', source: 'local-help', link: '/' + path.relative(helpRoot, filename).split(path.sep).join('/') });
      }
    }
  }
  if (candidates.length !== 1) return { ok: false, error: candidates.length ? 'Ambiguous routine; specify --type or use the project source directly' : 'Routine not found', candidates };
  const row = candidates[0];
  if (row.source === 'project') return { ok: true, routine: row, text: cleanText(fs.readFileSync(row.file, 'utf8')),
    compatibility: 'Project code must be compiled and tested against the detected IDL version.' };
  const filename = helpRoot ? docPath(helpRoot, row.link) : null;
  const result = { routine: row, installed_version: version,
    online_url: 'https://www.nv5geospatialsoftware.com/docs/' + path.posix.parse(decodeURIComponent(row.link.split('#')[0])).name + '.html', local_file: filename };
  if (!filename || !isFile(filename)) return { ok: false, ...result, error: 'Local documentation missing; retrieve official online documentation and verify its version history before use.' };
  const text = readHelp(filename), match = /^Version History\s*$/im.exec(text);
  const history = match ? text.slice(match.index + match[0].length).split('See Also')[0].trim() : null;
  return { ok: true, ...result, text, version_history: history,
    compatibility: 'Read the syntax, keywords and version history; test the selected API. Missing history does not prove compatibility.' };
}

export function interpretExecution(processResult, token, fileCount, run) {
  const output = processResult.output, begin = token + 'BEGIN', end = token + 'END';
  const framed = output.includes(begin) && output.includes(end);
  const body = framed ? output.split(begin)[1].split(end)[0] : output;
  const errors = [...body.matchAll(new RegExp(token + 'COMPILE=\\s*(-?\\d+)', 'g'))].map(match => Number(match[1]));
  const diagnostics = body.split(/\r?\n/).filter(line => /%\s*(?:Syntax error|Compilation error|Error|Attempt to|Procedure was compiled|Function was compiled|Variable is undefined)/i.test(line)
    && !/%\s*Compiled module:/i.test(line)).map(line => line.trim());
  const compiled = framed && errors.length === fileCount && errors.every(value => value === 0) && !diagnostics.length;
  const ran = run ? body.includes(token + 'RUN_OK') && !body.includes(token + 'RUN_FAIL') : null;
  return { ok: !processResult.timed_out && processResult.returncode === 0 && compiled && (!run || ran), compiled, ran,
    compile_error_codes: errors, diagnostics, environment_output: { startup: output.includes(begin) ? output.split(begin)[0].trim() : '',
      shutdown: output.includes(end) ? output.split(end)[1].trim() : '' }, process: processResult };
}

export async function verifyFiles(idl, files, cwd, timeout = 60, entry = null, includes = [], execute = invoke) {
  files = files.map(filename => path.resolve(filename));
  cwd = path.resolve(cwd);
  for (const filename of files) {
    if (!isFile(filename)) throw new IDLToolError(`Code file not found: ${filename}`);
    compileCommand(filename);
  }
  for (const directory of includes) if (!isDirectory(directory)) throw new IDLToolError(`Include directory not found: ${directory}`);
  if (entry && !ENTRY.test(entry)) throw new IDLToolError('--entry must be a procedure name; put arguments/assertions in a test procedure');
  const token = 'DKIDL' + randomUUID().replaceAll('-', '');
  const directories = [...new Set([cwd, ...files.map(filename => path.dirname(filename)), ...includes.map(directory => path.resolve(directory))])];
  const dataArgs = [...directories];
  const commands = [`print, '${token}BEGIN'`, 'message, /reset', 'dk_idl_skill_args = command_line_args()'];
  directories.forEach((directory, index) => commands.push(`!PATH = dk_idl_skill_args[${index}] + path_sep(/search_path) + !PATH`));
  commands.push('dk_idl_skill_all_ok = 1b');
  const needsTemporary = Boolean(entry) || files.some(filename => /[^\x00-\x7f]/.test(path.basename(filename)));
  const temporary = needsTemporary ? fs.mkdtempSync(path.join(os.tmpdir(), 'dk-idl-')) : null;
  const staged = [];
  let compileFiles = [...files];
  try {
    let runnerName;
    if (entry) {
      runnerName = 'dk_idl_skill_run_' + randomUUID().replaceAll('-', '');
      const runner = path.join(temporary, runnerName + '.pro');
      fs.writeFileSync(runner, `pro ${runnerName}, entry\n  compile_opt idl2\n  catch, error_code\n  if error_code ne 0 then begin\n    catch, /cancel\n    print, '${token}RUN_FAIL=', !ERROR_STATE.MSG\n    return\n  endif\n  call_procedure, entry\n  catch, /cancel\n  print, '${token}RUN_OK'\nend\n`, 'ascii');
      compileFiles.unshift(runner);
    }
    compileFiles.forEach((filename, index) => {
      let actual = filename;
      if (/[^\x00-\x7f]/.test(path.basename(filename))) {
        actual = path.join(temporary, `source_${index}.pro`);
        fs.copyFileSync(filename, actual);
        staged.push({ source: filename, temporary_file: actual });
      }
      dataArgs.push(path.dirname(actual));
      commands.push(`cd, dk_idl_skill_args[${dataArgs.length - 1}]`, 'message, /reset', compileCommand(path.basename(actual)),
        `print, '${token}COMPILE=', !ERROR_STATE.CODE`, 'if !ERROR_STATE.CODE ne 0 then dk_idl_skill_all_ok = 0b');
    });
    commands.push('cd, dk_idl_skill_args[0]');
    if (entry) commands.push(`if dk_idl_skill_all_ok then ${runnerName}, ${idlString(entry)}`);
    commands.push(`print, '${token}END'`, 'exit');
    const processResult = await execute(idl, commands, cwd, timeout, dataArgs);
    return { ...interpretExecution(processResult, token, compileFiles.length, Boolean(entry)), files, entry, executable: idl, staged_sources: staged };
  } finally {
    // Exact mkdtemp-owned directory only; never recursively remove user-provided paths.
    if (temporary) fs.rmSync(temporary, { recursive: true, force: true });
  }
}

const USAGE = `node idl_tools.mjs <doctor|search|docs|check|run> [arguments]\nCommon: --idl PATH --cwd DIR --timeout SECONDS\nsearch QUERY: --type TYPE --project DIR --help-root DIR --text --limit N\ndocs NAME: --type TYPE --project DIR --help-root DIR\ncheck FILE... / run FILE... --entry PROCEDURE: --include DIR (repeatable)`;

export function parseArguments(argv) {
  const command = argv[0], args = { command, cwd: process.cwd(), timeout: 60, limit: 20, includes: [], positional: [] };
  if (!['doctor', 'search', 'docs', 'check', 'run'].includes(command)) throw new IDLToolError(USAGE);
  const options = new Set(['idl', 'cwd', 'timeout']);
  if (command === 'search' || command === 'docs') ['type', 'project', 'help-root'].forEach(key => options.add(key));
  if (command === 'search') options.add('limit');
  if (command === 'check' || command === 'run') options.add('include');
  if (command === 'run') options.add('entry');
  let positionalOnly = false;
  for (let i = 1; i < argv.length; i++) {
    const value = argv[i];
    if (value === '--') { positionalOnly = true; continue; }
    if (!positionalOnly && value === '--text' && command === 'search') { args.fullText = true; continue; }
    if (!positionalOnly && value.startsWith('--')) {
      const key = value.slice(2);
      if (!options.has(key) || i + 1 >= argv.length || argv[i + 1].startsWith('--')) throw new IDLToolError(`Unknown option or missing value: ${value}`);
      const next = argv[++i];
      if (key === 'include') args.includes.push(path.resolve(next));
      else args[key === 'type' ? 'kind' : key === 'help-root' ? 'helpRoot' : key] = next;
    } else args.positional.push(value);
  }
  args.cwd = path.resolve(args.cwd);
  args.timeout = Number(args.timeout);
  args.limit = Number(args.limit);
  if (!Number.isFinite(args.timeout) || args.timeout <= 0 || !isDirectory(args.cwd)) throw new IDLToolError('Positive timeout and existing --cwd are required');
  if (!Number.isInteger(args.limit) || args.limit <= 0) throw new IDLToolError('--limit must be a positive integer');
  if (args.project && !isDirectory(args.project)) throw new IDLToolError('--project must be an existing directory');
  const count = args.positional.length;
  if (command === 'doctor' && count || (command === 'search' || command === 'docs') && count !== 1
      || (command === 'check' || command === 'run') && !count || command === 'run' && !args.entry) throw new IDLToolError(USAGE);
  return args;
}

export async function main(argv = process.argv.slice(2)) {
  if (argv.includes('--help') || argv.includes('-h')) { console.log(USAGE); return 0; }
  let result;
  try {
    const args = parseArguments(argv), query = args.positional[0];
    if (args.command === 'search' && !args.fullText) result = search(query, args);
    else if (args.command === 'docs' || args.command === 'search') {
      let info = {}, runtimeError = null;
      if (!args.helpRoot) {
        try { info = await doctor(findIDL(args.idl), args.cwd, args.timeout); }
        catch (error) { runtimeError = error.message; }
        args.helpRoot = info.help_root;
      } else args.helpRoot = path.resolve(args.helpRoot);
      if (args.command === 'search') {
        if (!args.helpRoot || !isDirectory(args.helpRoot)) throw new IDLToolError('--text requires the local IDL help directory');
        result = search(query, args);
      } else {
        result = getDocs(query, { ...args, version: info.version || null });
        if (runtimeError) result.runtime_error = runtimeError;
      }
    } else {
      const idl = findIDL(args.idl);
      result = args.command === 'doctor' ? await doctor(idl, args.cwd, args.timeout)
        : await verifyFiles(idl, args.positional, args.cwd, args.timeout, args.entry || null, args.includes);
    }
  } catch (error) { result = { ok: false, error: error.message }; }
  console.log(JSON.stringify(result, null, 2));
  return result.ok ? 0 : 1;
}

if (process.argv[1] && path.resolve(process.argv[1]) === SCRIPT) process.exitCode = await main();
