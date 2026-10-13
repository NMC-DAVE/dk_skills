import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import * as tools from '../scripts/idl_tools.mjs';
import { buildCatalog } from '../scripts/build_catalog.mjs';

function temporary(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dk-idl-unit-'));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return root;
}
const row = (name, type, link) => ({ name, type, source: 'idl', link });
const transcript = (token, body) => ({ returncode: 0, timed_out: false,
  output: `${token}BEGIN\n${body}${token}END\n% Error opening history file` });

test('Current PATH wins without reading registry', t => {
  const root = temporary(t), executable = path.join(root, process.platform === 'win32' ? 'idl.exe' : 'idl');
  fs.writeFileSync(executable, ''); fs.chmodSync(executable, 0o755);
  assert.equal(tools.findIDL(null, { platform: process.platform, env: { PATH: root }, registryPaths: () => assert.fail('Unexpected registry access') }), fs.realpathSync(executable));
});

test('Registry-backed PATH resolves a stale Windows process PATH', t => {
  const root = temporary(t), executable = path.join(root, 'idl.exe');
  fs.writeFileSync(executable, '');
  assert.equal(tools.findIDL(null, { platform: 'win32', env: { Path: '' }, registryPaths: () => [root] }), fs.realpathSync(executable));
});

test('Explicit executable with spaces and missing executable', t => {
  const root = temporary(t), executable = path.join(root, 'IDL executable with spaces');
  fs.writeFileSync(executable, '');
  assert.equal(tools.findIDL(executable), fs.realpathSync(executable));
  assert.throws(() => tools.findIDL(path.join(root, 'missing')), /not found/);
});

test('Doctor parses version/path and requires complete framing', async t => {
  const root = temporary(t);
  const execute = async (idl, commands) => {
    const token = commands[0].split("'")[1].slice(0, -5);
    return transcript(token, `${token}VERSION=9.3.0\n${token}DIR=${root}\n${token}PATH=a;b\n`);
  };
  const result = await tools.doctor('idl', root, 60, execute);
  assert.equal(result.ok, true); assert.equal(result.version, '9.3.0');
  const blocked = await tools.doctor('idl', root, 60, async () => ({ returncode: 0, timed_out: false, output: 'license unavailable' }));
  assert.equal(blocked.ok, false);
});

test('Documentation mapping decodes spaces and rejects traversal', t => {
  const root = temporary(t);
  assert.equal(tools.docPath(root, '/idl/Content/Reference%20Material/W/WHERE.htm#anchor'), path.join(root, 'idl/Content/Reference Material/W/WHERE.htm'));
  assert.throws(() => tools.docPath(root, '/../private.htm'), /escapes/);
});

test('Documentation mapping also rejects symlink/junction escapes', t => {
  const root = temporary(t), help = path.join(root, 'help'), outside = path.join(root, 'outside');
  fs.mkdirSync(help); fs.mkdirSync(outside); fs.writeFileSync(path.join(outside, 'secret.htm'), '<main>private</main>');
  try { fs.symlinkSync(outside, path.join(help, 'idl'), process.platform === 'win32' ? 'junction' : 'dir'); }
  catch (error) { if (error.code === 'EPERM' || error.code === 'EACCES') { t.skip('Link creation unavailable'); return; } throw error; }
  assert.throws(() => tools.docPath(help, '/idl/secret.htm'), /escapes/);
});

test('HTML extraction preserves example lines and version tables, excludes hidden content', () => {
  const text = tools.extractHelp(`<nav>navigation</nav><div id="mc-main-content"><h1>WHERE</h1>
    <p>Meaning &amp; use. &#x3c0; &lt; 5</p><pre>idx = where(a, count)\nif count gt 0 then print, a[idx]</pre>
    <h2>Version History</h2><table><tr><td>8.0</td><td>Added NULL keyword.</td></tr></table>
    <p class="Hidden">WHERE WHERE noise</p><div style="display: none"><p>private</p></div>
    <script>if (x < y) { something = '</div>'; }</script><h2>See Also</h2><p>Other</p></div><footer>footer</footer>`);
  assert.ok(text.includes('Meaning & use. π < 5'));
  assert.ok(text.includes('idx = where(a, count)\nif count'));
  assert.ok(text.includes('Added NULL keyword.'));
  for (const word of ['navigation', 'noise', 'private', 'something', 'footer']) assert.ok(!text.includes(word));
});

test('Function/procedure ambiguity is not silently resolved', () => {
  const catalog = [row('plot', 'Function', '/idl/plot.htm'), row('plot', 'Procedure', '/idl/plot_old.htm')];
  assert.equal(tools.getDocs('PLOT', { catalog }).candidates.length, 2);
  const result = tools.getDocs('plot', { catalog, kind: 'Function', version: '9.3.0' });
  assert.equal(result.routine.type, 'Function'); assert.match(result.error, /missing/i);
});

test('Project definitions include methods, line numbers and source documentation', t => {
  const root = temporary(t), filename = path.join(root, 'project with space.pro');
  fs.writeFileSync(filename, '; pro fake\n\nfunction sample, data\n return, data\nend\npro container::go\nend\n');
  const rows = tools.projectRoutines(root);
  assert.deepEqual(rows.map(item => item.name), ['sample', 'container::go']);
  assert.equal(rows[0].line, 3); assert.equal(rows[1].type, 'ProcedureMethod');
  const result = tools.getDocs('sample', { project: root, catalog: [], kind: 'Function' });
  assert.equal(result.ok, true); assert.match(result.text, /return, data/);
});

test('New local topics and version history remain available outside the snapshot', t => {
  const root = temporary(t), filename = path.join(root, 'idl/Content/new_feature.htm');
  fs.mkdirSync(path.dirname(filename), { recursive: true });
  fs.writeFileSync(filename, '<main><h1>NEW_FEATURE</h1><h2>Version History</h2><p>9.3 Added feature</p><h2>See Also</h2><p>other</p></main>');
  const result = tools.getDocs('new_feature', { catalog: [], helpRoot: root, version: '9.3.0' });
  assert.equal(result.ok, true); assert.equal(result.routine.source, 'local-help'); assert.equal(result.version_history, '9.3 Added feature');
});

test('Body search finds routines from technical terms', t => {
  const root = temporary(t), filename = path.join(root, 'idl/fft.htm');
  fs.mkdirSync(path.dirname(filename)); fs.writeFileSync(filename, '<main><h1>FFT</h1><p>Computes a Fourier transform.</p></main>');
  const catalog = [row('fft', 'Function', '/idl/fft.htm')];
  assert.equal(tools.search('Fourier transform', { catalog }).total, 0);
  const result = tools.search('Fourier transform', { catalog, helpRoot: root, fullText: true });
  assert.equal(result.matches[0].name, 'fft'); assert.match(result.matches[0].excerpt, /Fourier/);
});

for (const [body, run, ok] of [
  ['COMPILE=0\n', false, true], ['COMPILE=-237\n', false, false],
  ['COMPILE=0\n% Syntax error.\n', false, false], ['COMPILE=0\nRUN_FAIL=assertion failed\n', true, false],
  ['COMPILE=0\nRUN_OK\n', true, true], ['RUN_OK\n', true, false],
]) test(`Execution state: ${body.trim().replaceAll('\n', ' ')}; run=${run}`, () => {
  const token = 'DK_TEST_';
  const marked = body.replaceAll('COMPILE=', token + 'COMPILE=').replaceAll('RUN_', token + 'RUN_');
  const result = tools.interpretExecution(transcript(token, marked), token, 1, run);
  assert.equal(result.ok, ok); assert.match(result.environment_output.shutdown, /history/);
});

test('Missing markers, nonzero exit and timeout fail validation', () => {
  const token = 'DK_', valid = transcript(token, token + 'COMPILE=0\n');
  for (const processResult of [{ returncode: 0, timed_out: false, output: 'license failure' },
    { ...valid, returncode: 1 }, { ...valid, timed_out: true, returncode: null }]) {
    assert.equal(tools.interpretExecution(processResult, token, 1, false).ok, false);
  }
});

test('Process timeout kills the child and preserves partial output and native argv', async () => {
  let killed = false;
  const fakeSpawn = (executable, argv, options) => {
    assert.equal(executable, 'IDL with spaces');
    assert.deepEqual(argv, ['-quiet', '-args', '中文 path']);
    assert.equal(options.shell, false); assert.equal(options.windowsHide, true);
    const child = new EventEmitter(); child.stdin = new PassThrough(); child.stdout = new PassThrough(); child.stderr = new PassThrough();
    child.kill = () => { killed = true; child.emit('close', null); };
    queueMicrotask(() => child.stdout.write('partial output'));
    return child;
  };
  const result = await tools.invoke('IDL with spaces', ['exit'], process.cwd(), 0.02, ['中文 path'], fakeSpawn);
  assert.equal(killed, true); assert.equal(result.timed_out, true); assert.equal(result.output, 'partial output');
});

test('Unicode file names are staged with original-to-temporary mapping', async t => {
  const root = temporary(t), filename = path.join(root, '中文 file with spaces.pro');
  fs.writeFileSync(filename, 'pro example\nend\n');
  const execute = async (idl, commands, cwd, timeout, dataArgs) => {
    assert.ok(commands.some(line => line.startsWith('.compile "source_')));
    assert.ok(!commands.some(line => line.includes('call_procedure') || line.includes('.run')));
    assert.ok(dataArgs.includes(root));
    const token = commands[0].split("'")[1].slice(0, -5);
    return transcript(token, token + 'COMPILE=0\n');
  };
  const result = await tools.verifyFiles('idl', [filename], root, 60, null, [], execute);
  assert.equal(result.ok, true); assert.equal(result.staged_sources[0].source, filename);
  assert.equal(fs.existsSync(result.staged_sources[0].temporary_file), false);
  assert.equal(fs.readFileSync(filename, 'utf8'), 'pro example\nend\n');
  assert.equal(tools.idlString("a'b"), "'a''b'");
  assert.throws(() => tools.idlString('a\nexit'), /Newlines/);
  await assert.rejects(tools.verifyFiles('idl', [filename], root, 60, 'test & exit'), /procedure name/);
});

test('ASCII compilation does not create temporary source copies', async t => {
  const root = temporary(t), filename = path.join(root, 'example.pro'); fs.writeFileSync(filename, 'pro example\nend\n');
  const execute = async (idl, commands) => {
    assert.ok(commands.includes('.compile "example.pro"'));
    const token = commands[0].split("'")[1].slice(0, -5);
    return transcript(token, token + 'COMPILE=0\n');
  };
  const result = await tools.verifyFiles('idl', [filename], root, 60, null, [], execute);
  assert.equal(result.ok, true); assert.deepEqual(result.staged_sources, []);
});

test('Catalog remains compact official discovery metadata', () => {
  const rows = tools.loadCatalog();
  assert.ok(rows.length > 0); assert.equal(new Set(rows.map(row => row.name.toLowerCase() + '\0' + row.type)).size, rows.length);
  for (const item of rows) {
    assert.ok(['idl', 'internal'].includes(item.source)); assert.ok(item.link.startsWith('/idl/'));
    assert.deepEqual(Object.keys(item).sort(), ['link', 'name', 'source', 'type']);
  }
});

test('Catalog builder filters, deduplicates and records the source digest', t => {
  const root = temporary(t), directory = path.join(root, 'resources/idl/routines'); fs.mkdirSync(directory, { recursive: true });
  fs.writeFileSync(path.join(root, 'package.json'), '{"version":"6.2.2"}');
  fs.writeFileSync(path.join(directory, 'routines.json'), JSON.stringify([
    { name: 'WHERE', type: 'f', source: 'internal', link: '/idl/where.htm' },
    { name: 'where', type: 'f', source: 'internal', link: '/idl/where.htm' },
    { name: 'ENVI', type: 'f', source: 'envi', link: '/envi/envi.htm' },
  ]));
  const catalog = buildCatalog(root);
  assert.equal(catalog.routines.length, 1); assert.equal(catalog.upstream_version, '6.2.2'); assert.match(catalog.source_sha256, /^[a-f0-9]{64}$/);
});

test('CLI validates input and offline search does not need Python or IDL', () => {
  assert.throws(() => tools.parseArguments(['run', 'a.pro']), /--entry/);
  assert.throws(() => tools.parseArguments(['search', 'where', '--timeout', 'NaN']), /Positive timeout/);
  assert.throws(() => tools.parseArguments(['search', 'where', '--limit', '0']), /positive integer/);
  const script = fileURLToPath(new URL('../scripts/idl_tools.mjs', import.meta.url));
  const processResult = spawnSync(process.execPath, [script, 'search', 'where', '--type', 'Function'],
    { encoding: 'utf8', env: { ...process.env, PATH: '', Path: '' }, windowsHide: true });
  assert.equal(processResult.status, 0, processResult.stderr);
  assert.equal(JSON.parse(processResult.stdout).matches[0].name, 'where');
});
