from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/idl_tools.py"
SPEC = importlib.util.spec_from_file_location("idl_tools", SCRIPT)
tools = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tools)


def test_current_path_precedes_registry(monkeypatch, tmp_path):
    executable = tmp_path / "idl"
    executable.touch()
    monkeypatch.setattr(tools.shutil, "which", lambda name: str(executable))
    monkeypatch.setattr(tools, "windows_paths", lambda: pytest.fail("Should not inspect registry after a PATH match"))
    assert tools.find_idl() == executable.resolve()


def test_stale_process_path_falls_back_to_registry(monkeypatch, tmp_path):
    executable = tmp_path / "idl.exe"
    executable.touch()
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    monkeypatch.setattr(tools, "windows_paths", lambda: [str(tmp_path)])
    assert tools.find_idl() == executable.resolve()


def test_explicit_executable_and_missing(monkeypatch, tmp_path):
    executable = tmp_path / "IDL path with spaces" / "idl.exe"
    executable.parent.mkdir()
    executable.touch()
    assert tools.find_idl(str(executable)) == executable.resolve()
    monkeypatch.setattr(tools.shutil, "which", lambda name: None)
    with pytest.raises(tools.IDLToolError, match="not found"):
        tools.find_idl(str(tmp_path / "missing.exe"))


def test_doctor_requires_all_fields_and_completed_process(monkeypatch, tmp_path):
    def fake_invoke(idl, commands, cwd, timeout):
        token = commands[0].split("'")[1][:-5]
        output = f"{token}BEGIN\n{token}VERSION=9.3.0\n{token}DIR={tmp_path}\n{token}PATH=a;b\n{token}END\n"
        return {"returncode": 0, "timed_out": False, "output": output}
    monkeypatch.setattr(tools, "invoke", fake_invoke)
    result = tools.doctor(tmp_path / "idl", tmp_path, 60)
    assert result["ok"] and result["version"] == "9.3.0"
    monkeypatch.setattr(tools, "invoke", lambda *args: {"returncode": 0, "timed_out": False, "output": "license unavailable"})
    assert not tools.doctor(tmp_path / "idl", tmp_path, 60)["ok"]


def test_help_mapping_decodes_spaces_and_rejects_escape(tmp_path):
    assert tools.doc_path(tmp_path, "/idl/Content/Reference%20Material/W/WHERE.htm#anchor") == (
        tmp_path / "idl/Content/Reference Material/W/WHERE.htm").resolve()
    with pytest.raises(tools.IDLToolError, match="escapes"):
        tools.doc_path(tmp_path, "/../private.htm")


def test_help_parser_excludes_hidden_content_preserves_examples_and_history(tmp_path):
    path = tmp_path / "help.htm"
    path.write_text('''<html><nav>navigation</nav><div id="mc-main-content"><h1>WHERE</h1>
      <p>Meaning &amp; use.</p><pre>idx = where(a, count)\nif count gt 0 then print, a[idx]</pre>
      <h2>Version History</h2><table><tr><td>8.0</td><td>Added NULL keyword.</td></tr></table>
      <p class="Hidden">WHERE WHERE noise</p><div style="display: none"><p>private</p></div>
      <script>bad()</script><h2>See Also</h2><p>Other</p></div><footer>footer</footer></html>''', encoding="utf-8")
    text = tools.read_help(path)
    assert "Meaning & use." in text and "Added NULL keyword." in text
    assert "idx = where(a, count)\nif count" in text
    assert all(word not in text for word in ("navigation", "noise", "private", "bad()", "footer"))


def test_function_procedure_ambiguity(monkeypatch):
    monkeypatch.setattr(tools, "load_catalog", lambda: [
        {"name": "plot", "type": "Function", "source": "idl", "link": "/idl/plot.htm"},
        {"name": "plot", "type": "Procedure", "source": "internal", "link": "/idl/plot_old.htm"}])
    result = tools.get_docs("PLOT", None, None, None)
    assert not result["ok"] and len(result["candidates"]) == 2
    result = tools.get_docs("plot", "Function", None, "9.3.0")
    assert result["routine"]["type"] == "Function" and "missing" in result["error"].lower()


def test_project_routines_and_name_collision(monkeypatch, tmp_path):
    source = tmp_path / "project with space.pro"
    source.write_text("; pro fake\nfunction sample, data\n return, data\nend\npro container::go\nend\n", encoding="utf-8")
    rows = tools.project_routines(tmp_path)
    assert [row["name"] for row in rows] == ["sample", "container::go"]
    assert rows[1]["type"] == "ProcedureMethod"
    assert rows[0]["line"] == 2 and rows[0]["source"] == "project"
    monkeypatch.setattr(tools, "load_catalog", lambda: [])
    result = tools.get_docs("sample", "Function", None, None, tmp_path)
    assert result["ok"] and "return, data" in result["text"]


def test_local_version_history_and_new_routine(monkeypatch, tmp_path):
    path = tmp_path / "idl/Content/new_feature.htm"
    path.parent.mkdir(parents=True)
    path.write_text('<main><h1>NEW_FEATURE</h1><p>Syntax</p><h2>Version History</h2><p>9.3 Added feature</p><h2>See Also</h2><p>other</p></main>', encoding="utf-8")
    monkeypatch.setattr(tools, "load_catalog", lambda: [])
    result = tools.get_docs("new_feature", None, tmp_path, "9.3.0")
    assert result["ok"] and result["routine"]["source"] == "local-help"
    assert result["version_history"] == "9.3 Added feature"


def test_search_content_and_project(monkeypatch, tmp_path):
    path = tmp_path / "idl/fft.htm"
    path.parent.mkdir()
    path.write_text('<main><h1>FFT</h1><p>Computes a Fourier transform.</p></main>', encoding="utf-8")
    monkeypatch.setattr(tools, "load_catalog", lambda: [{"name": "fft", "type": "Function", "source": "internal", "link": "/idl/fft.htm"}])
    assert tools.search("Fourier transform")["total"] == 0
    result = tools.search("Fourier transform", help_root=tmp_path, full_text=True)
    assert result["matches"][0]["name"] == "fft" and "Fourier" in result["matches"][0]["excerpt"]


@pytest.mark.parametrize("body,run,ok", [
    ("COMPILE=0\n", False, True),
    ("COMPILE=-237\n", False, False),
    ("COMPILE=0\n% Syntax error.\n", False, False),
    ("COMPILE=0\nRUN_FAIL=assertion failed\n", True, False),
    ("COMPILE=0\nRUN_OK\n", True, True),
    ("RUN_OK\n", True, False),
])
def test_execution_states_with_zero_process_exit(body, run, ok):
    token = "DK_TEST_"
    marked = body.replace("COMPILE=", token + "COMPILE=").replace("RUN_", token + "RUN_")
    process = {"returncode": 0, "timed_out": False, "output": token + "BEGIN\n" + marked + token + "END\n% Error opening history file"}
    result = tools.interpret_execution(process, token, 1, run)
    assert result["ok"] is ok
    assert "history" in result["environment_output"]["shutdown"]


def test_missing_markers_nonzero_exit_and_timeout():
    token = "DK_"
    valid = f"{token}BEGIN\n{token}COMPILE=0\n{token}END"
    for output, returncode, timed_out in [("license failure", 0, False), (valid, 1, False), (valid, None, True)]:
        assert not tools.interpret_execution({"output": output, "returncode": returncode, "timed_out": timed_out}, token, 1, False)["ok"]


def test_invoke_timeout_and_argument_array(monkeypatch, tmp_path):
    def fake_run(argv, **kwargs):
        assert argv == [str(tmp_path / "IDL executable"), "-quiet"]
        assert isinstance(kwargs["input"], bytes) and kwargs["cwd"] == str(tmp_path)
        raise subprocess.TimeoutExpired(argv, 0.1, output=b"partial output")
    monkeypatch.setattr(tools.subprocess, "run", fake_run)
    result = tools.invoke(tmp_path / "IDL executable", ["exit"], tmp_path, 0.1)
    assert result["timed_out"] and result["output"] == "partial output"


def test_check_does_not_invoke_main_and_preserves_quoting(monkeypatch, tmp_path):
    path = tmp_path / "中文 file with spaces.pro"
    path.write_text("pro example\nend\n", encoding="ascii")
    def fake_invoke(idl, commands, cwd, timeout, data_args):
        assert any('.compile "source_' in line for line in commands)
        assert str(path.parent) in data_args
        assert not any("call_procedure" in line or ".run" in line for line in commands)
        token = commands[0].split("'")[1][:-5]
        return {"returncode": 0, "timed_out": False, "output": f"{token}BEGIN\n{token}COMPILE=0\n{token}END"}
    monkeypatch.setattr(tools, "invoke", fake_invoke)
    assert tools.verify_files(tmp_path / "idl", [path], tmp_path, 60, None)["ok"]
    assert tools.idl_string("a'b") == "'a''b'"
    with pytest.raises(tools.IDLToolError):
        tools.idl_string("a\nexit")
    with pytest.raises(tools.IDLToolError):
        tools.verify_files(tmp_path / "idl", [path], tmp_path, 60, "test & exit")


def test_catalog_contains_only_idl_discovery_metadata():
    rows = tools.load_catalog()
    assert rows and all(row["source"] in {"idl", "internal"} for row in rows)
    assert all(set(row) == {"name", "type", "source", "link"} and row["link"].startswith("/idl/") for row in rows)
    assert len({(row["name"].lower(), row["type"]) for row in rows}) == len(rows)


def test_ascii_check_needs_no_temporary_directory(monkeypatch, tmp_path):
    path = tmp_path / "example.pro"
    path.write_text("pro example\nend\n", encoding="ascii")
    monkeypatch.setattr(tools.tempfile, "TemporaryDirectory", lambda **kwargs: pytest.fail("Compilation-only check must not create unnecessary temporary directories"))
    def fake_invoke(idl, commands, cwd, timeout, data_args):
        token = commands[0].split("'")[1][:-5]
        return {"returncode": 0, "timed_out": False, "output": f"{token}BEGIN\n{token}COMPILE=0\n{token}END"}
    monkeypatch.setattr(tools, "invoke", fake_invoke)
    assert tools.verify_files(tmp_path / "idl", [path], tmp_path, 60, None)["ok"]
