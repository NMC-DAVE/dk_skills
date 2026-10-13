"""Opt-in licensed-runtime tests: set DK_IDL_EXECUTABLE to an IDL executable."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/idl_tools.py"
SPEC = importlib.util.spec_from_file_location("idl_tools_integration", SCRIPT)
tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tools)
EXECUTABLE = os.environ.get("DK_IDL_EXECUTABLE")
pytestmark = pytest.mark.skipif(not EXECUTABLE, reason="Set DK_IDL_EXECUTABLE for licensed local integration tests")


@pytest.fixture
def work(tmp_path):
    path = tmp_path / "IDL 中文 project with spaces"
    path.mkdir()
    return path


def test_runtime_version(work):
    result = tools.doctor(Path(EXECUTABLE), work, 60)
    assert result["ok"], result
    assert result["version"] and result["help_root"]


def test_arrays_missing_data_graphics_and_project_call(work):
    helper = work / "project_double.pro"
    helper.write_text("function project_double, data\n  compile_opt idl2\n  return, double(data) * 2d\nend\n", encoding="ascii")
    test = work / "中文 science test.pro"
    test.write_text('''pro test_science
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
''', encoding="ascii")
    assert tools.search("project_double", project=work)["matches"][0]["source"] == "project"
    compiled = tools.verify_files(Path(EXECUTABLE), [helper, test], work, 60, None)
    assert compiled["ok"], compiled
    assert not (work / "plot.png").exists(), "check must not execute the test"
    result = tools.verify_files(Path(EXECUTABLE), [helper, test], work, 60, "test_science")
    assert result["ok"], result
    image = (work / "plot.png").read_bytes()
    assert image[:8] == b"\x89PNG\r\n\x1a\n" and len(image) > 100


def test_compiler_error_never_reports_success(work):
    source = work / "broken.pro"
    source.write_text("pro broken\ncompile_opt idl2\nx = (\nend\n", encoding="ascii")
    result = tools.verify_files(Path(EXECUTABLE), [source], work, 60, None)
    assert not result["ok"], result
    assert result["diagnostics"] or any(result["compile_error_codes"]), result


def test_check_does_not_execute_main_level(work):
    source = work / "main_level.pro"
    source.write_text("compile_opt idl2\nmessage, 'MAIN_LEVEL_EXECUTED'\nend\n", encoding="ascii")
    result = tools.verify_files(Path(EXECUTABLE), [source], work, 60, None)
    assert result["ok"], result
    assert "MAIN_LEVEL_EXECUTED" not in result["process"]["output"], result


def test_runtime_assertion_never_reports_success(work):
    source = work / "test_failure.pro"
    source.write_text("pro test_failure\ncompile_opt idl2\nmessage, 'intentional assertion failure'\nend\n", encoding="ascii")
    result = tools.verify_files(Path(EXECUTABLE), [source], work, 60, "test_failure")
    assert not result["ok"] and result["compiled"] and not result["ran"], result
    assert "intentional assertion failure" in result["process"]["output"], result


def test_runtime_timeout(work):
    source = work / "test_timeout.pro"
    source.write_text("pro test_timeout\ncompile_opt idl2\nwait, 30\nend\n", encoding="ascii")
    result = tools.verify_files(Path(EXECUTABLE), [source], work, 5, "test_timeout")
    assert not result["ok"] and result["process"]["timed_out"], result
