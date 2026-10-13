/** Opt-in licensed runtime tests: set DK_IDL_EXECUTABLE; no Python required. */
import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { doctor, verifyFiles, search } from '../scripts/idl_tools.mjs';

const executable = process.env.DK_IDL_EXECUTABLE;
const options = { skip: !executable };
function work(t) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'dk-idl-live-'));
  const directory = path.join(root, 'IDL 中文 project with spaces'); fs.mkdirSync(directory);
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  return directory;
}

test('Actual installed IDL version and help directory', options, async t => {
  const result = await doctor(executable, work(t));
  assert.equal(result.ok, true, JSON.stringify(result)); assert.ok(result.version); assert.ok(result.help_root);
});

test('Unicode file/directory, array order, missing values, project calls and function graphics', options, async t => {
  const directory = work(t), helper = path.join(directory, 'project_double.pro'), filename = path.join(directory, '中文 science test.pro');
  fs.writeFileSync(helper, 'function project_double, data\n  compile_opt idl2\n  return, double(data) * 2d\nend\n');
  fs.writeFileSync(filename, `pro test_science
  compile_opt idl2
  values = [1d, 2d, 3d]
  scaled = project_double(values)
  if total(abs(scaled - [2d, 4d, 6d])) gt 1d-12 then message, 'project call failed'
  idx = where(values gt 42d, count)
  if count gt 0 then values[idx] = -1d
  if total(abs(values - [1d, 2d, 3d])) gt 1d-12 then message, 'empty where failed'
  samples = [1d, !VALUES.D_NAN, 3d]
  if abs(mean(samples, /nan) - 2d) gt 1d-12 then message, 'missing mean failed'
  grid = reform(dindgen(6), 2, 3)
  if grid[1, 2] ne 5d then message, 'dimension order failed'
  graphic = plot(dindgen(4), [0d, 1d, 4d, 9d], /buffer)
  cd, current=directory
  graphic.save, filepath('plot.png', root=directory)
  graphic.close
end
`);
  assert.equal(search('project_double', { project: directory }).matches[0].source, 'project');
  const compiled = await verifyFiles(executable, [helper, filename], directory);
  assert.equal(compiled.ok, true, JSON.stringify(compiled)); assert.equal(fs.existsSync(path.join(directory, 'plot.png')), false);
  const result = await verifyFiles(executable, [helper, filename], directory, 60, 'test_science');
  assert.equal(result.ok, true, JSON.stringify(result));
  const image = fs.readFileSync(path.join(directory, 'plot.png'));
  assert.equal(image.subarray(0, 8).toString('hex'), '89504e470d0a1a0a'); assert.ok(image.length > 100);
});

test('Compile errors never report success', options, async t => {
  const directory = work(t), filename = path.join(directory, 'broken.pro');
  fs.writeFileSync(filename, 'pro broken\ncompile_opt idl2\nx = (\nend\n');
  const result = await verifyFiles(executable, [filename], directory);
  assert.equal(result.ok, false, JSON.stringify(result));
  assert.ok(result.diagnostics.length || result.compile_error_codes.some(Boolean));
});

test('Compile-only does not execute main-level code', options, async t => {
  const directory = work(t), filename = path.join(directory, 'main_level.pro');
  fs.writeFileSync(filename, "compile_opt idl2\nmessage, 'MAIN_LEVEL_EXECUTED'\nend\n");
  const result = await verifyFiles(executable, [filename], directory);
  assert.equal(result.ok, true, JSON.stringify(result)); assert.ok(!result.process.output.includes('MAIN_LEVEL_EXECUTED'));
});

test('Runtime assertion failure is captured', options, async t => {
  const directory = work(t), filename = path.join(directory, 'test_failure.pro');
  fs.writeFileSync(filename, "pro test_failure\ncompile_opt idl2\nmessage, 'intentional assertion failure'\nend\n");
  const result = await verifyFiles(executable, [filename], directory, 60, 'test_failure');
  assert.equal(result.ok, false, JSON.stringify(result)); assert.equal(result.compiled, true); assert.equal(result.ran, false);
  assert.match(result.process.output, /intentional assertion failure/);
});

test('Timeout terminates the IDL process', options, async t => {
  const directory = work(t), filename = path.join(directory, 'test_timeout.pro');
  fs.writeFileSync(filename, 'pro test_timeout\ncompile_opt idl2\nwait, 30\nend\n');
  const result = await verifyFiles(executable, [filename], directory, 5, 'test_timeout');
  assert.equal(result.ok, false); assert.equal(result.process.timed_out, true);
});
