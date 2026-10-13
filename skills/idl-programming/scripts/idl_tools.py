#!/usr/bin/env python3
"""Standalone IDL discovery, local documentation, compilation and test execution.

Uses only Python's standard library. Output is JSON; unsuccessful commands exit 1.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import json
import locale
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser
from urllib.parse import unquote
import uuid

SKILL_ROOT = Path(__file__).resolve().parents[1]
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ROUTINE_RE = re.compile(r"^[ \t]*(pro|function)\s+([a-z_]\w*(?:::[a-z_]\w*)?)\b", re.I | re.ASCII)
ENTRY_RE = re.compile(r"^[a-z_]\w*$", re.I | re.ASCII)


class IDLToolError(Exception):
    pass


def windows_paths() -> list[str]:
    if os.name != "nt":
        return []
    import winreg
    result = []
    locations = [(winreg.HKEY_CURRENT_USER, r"Environment"),
                 (winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment")]
    for hive, key in locations:
        try:
            with winreg.OpenKey(hive, key) as handle:
                value, _ = winreg.QueryValueEx(handle, "Path")
            result.extend(os.path.expandvars(value).split(os.pathsep))
        except OSError:
            continue
    return result


def find_idl(explicit: str | None = None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser()
        if candidate.is_file():
            return candidate.resolve()
        found = shutil.which(explicit)
        if found:
            return Path(found).resolve()
        raise IDLToolError(f"IDL executable not found: {explicit}")
    found = shutil.which("idl")
    if found:
        return Path(found).resolve()
    for directory in windows_paths():
        candidate = Path(directory.strip().strip('"')) / "idl.exe"
        if candidate.is_file():
            return candidate.resolve()
    raise IDLToolError("IDL not found in current/system/user PATH; pass --idl PATH. No configuration was changed.")


def idl_string(value: str) -> str:
    if any(char in value for char in "\r\n\x00"):
        raise IDLToolError("Newlines and NUL are not allowed in IDL arguments")
    return "'" + value.replace("'", "''") + "'"


def compile_command(path: Path) -> str:
    value = str(path.resolve())
    if any(char in value for char in '\r\n\x00"'):
        raise IDLToolError("File path cannot be represented in an IDL .compile command")
    return '.compile "' + value + '"'


def invoke(idl: Path, commands: list[str], cwd: Path, timeout: float, data_args: list[str] | None = None) -> dict:
    # IDL's Windows console uses the system ANSI code page, independently of Python UTF-8 mode.
    encoding = "mbcs" if os.name == "nt" else locale.getpreferredencoding(False)
    try:
        stdin = ("\n".join(commands) + "\n").encode(encoding)
    except UnicodeError as exc:
        raise IDLToolError(f"Path/command not representable in the IDL console encoding: {exc}") from exc
    try:
        argv = [str(idl), "-quiet"] + (["-args", *data_args] if data_args else [])
        result = subprocess.run(argv, input=stdin, cwd=str(cwd),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
        output = ANSI_RE.sub("", result.stdout.decode(encoding, errors="replace"))
        return {"returncode": result.returncode, "timed_out": False, "output": output}
    except subprocess.TimeoutExpired as exc:
        output = ANSI_RE.sub("", (exc.stdout or b"").decode(encoding, errors="replace"))
        return {"returncode": None, "timed_out": True, "output": output}
    except OSError as exc:
        raise IDLToolError(f"Could not start IDL: {exc}") from exc


def doctor(idl: Path, cwd: Path, timeout: float) -> dict:
    token = "DKIDL" + uuid.uuid4().hex
    commands = [f"print, '{token}BEGIN'", f"print, '{token}VERSION=' + !VERSION.RELEASE",
                f"print, '{token}DIR=' + !DIR", f"print, '{token}PATH=' + !PATH",
                f"print, '{token}END'", "exit"]
    process = invoke(idl, commands, cwd, timeout)
    output = process["output"]
    fields = {}
    for key in ("VERSION", "DIR", "PATH"):
        match = re.search(re.escape(token + key + "=") + r"([^\r\n]*)", output)
        if match:
            fields[key] = match.group(1).strip()
    ok = (not process["timed_out"] and process["returncode"] == 0
          and all(fields.get(key) for key in ("VERSION", "DIR", "PATH")) and token + "END" in output)
    root = Path(fields["DIR"]) if fields.get("DIR") else None
    help_root = root / "help/online_help/Subsystems" if root else None
    return {"ok": ok, "executable": str(idl), "version": fields.get("VERSION"),
            "idl_dir": str(root) if root else None, "idl_path": fields.get("PATH", "").split(os.pathsep),
            "help_root": str(help_root) if help_root and help_root.is_dir() else None,
            "process": process, "note": "Compilation/runtime verification is unavailable" if not ok else None}


def load_catalog() -> list[dict]:
    return json.loads((SKILL_ROOT / "references/routine-index.json").read_text(encoding="utf-8"))["routines"]


def doc_path(help_root: Path, link: str) -> Path:
    raw = unquote(link.split("#", 1)[0]).lstrip("/")
    root = help_root.resolve()
    path = (root / raw).resolve()
    if not path.is_relative_to(root):
        raise IDLToolError("Documentation path escapes the help directory")
    return path


class HelpParser(HTMLParser):
    """Read MadCap main content, excluding navigation, hidden repetitions and scripts."""
    BLOCKS = {"p", "div", "h1", "h2", "h3", "h4", "pre", "br", "li", "tr", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr = dict(attrs)
        parent_active = self.stack[-1][1] if self.stack else False
        parent_skip = self.stack[-1][2] if self.stack else False
        active = parent_active or attr.get("id") == "mc-main-content" or tag == "main"
        skip = (parent_skip or tag in {"script", "style", "nav"} or "hidden" in attr
                or attr.get("aria-hidden") == "true"
                or "hidden" in (attr.get("class") or "").lower().split()
                or "display:none" in (attr.get("style") or "").replace(" ", "").lower())
        if active and not skip:
            if tag in self.BLOCKS:
                self.chunks.append("\n")
            elif tag in {"td", "th"}:
                self.chunks.append(" | ")
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "wbr"}:
            self.stack.append((tag, active, skip))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag: str):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                if self.stack[i][1] and not self.stack[i][2] and tag in self.BLOCKS:
                    self.chunks.append("\n")
                del self.stack[i:]
                break

    def handle_data(self, data: str):
        if self.stack and self.stack[-1][1] and not self.stack[-1][2]:
            self.chunks.append(data)

    def text(self) -> str:
        # Preserve the line boundaries used by examples and version tables.
        lines = [re.sub(r"[\t \xa0]+", " ", line).strip() for line in "".join(self.chunks).splitlines()]
        return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def read_help(path: Path) -> str:
    parser = HelpParser()
    parser.feed(path.read_text(encoding="utf-8-sig", errors="replace"))
    text = parser.text()
    if not text:
        raise IDLToolError(f"No main documentation content extracted from {path}")
    return text


def project_routines(project: Path) -> list[dict]:
    result = []
    excluded = {".git", ".venv", "node_modules", "outputs", "output", "tmp", "temp"}
    for directory, folders, files in os.walk(project):
        folders[:] = [name for name in folders if name not in excluded and not Path(directory, name).is_symlink()]
        for filename in files:
            if not filename.lower().endswith(".pro"):
                continue
            path = Path(directory, filename)
            if path.is_symlink():
                continue
            text = path.read_text(encoding="utf-8-sig", errors="replace")
            for match in re.finditer(ROUTINE_RE.pattern, text, re.I | re.M | re.ASCII):
                kind = "Procedure" if match.group(1).lower() == "pro" else "Function"
                if "::" in match.group(2):
                    kind += "Method"
                result.append({"name": match.group(2), "type": kind,
                               "source": "project", "file": str(path.resolve()), "line": text[:match.start()].count("\n") + 1})
    return result


def search(query: str, kind: str | None = None, project: Path | None = None,
           help_root: Path | None = None, full_text: bool = False, limit: int = 20) -> dict:
    rows = load_catalog() + (project_routines(project) if project else [])
    words = query.lower().split()
    if not words:
        raise IDLToolError("Search query must not be empty")
    matches = []
    documents = {}
    for row in rows:
        if kind and row["type"].lower() != kind.lower():
            continue
        name = row["name"].lower()
        exact = name == query.lower()
        matched = all(word in name for word in words)
        text = ""
        if not matched and full_text and help_root and row.get("link"):
            path = doc_path(help_root, row["link"])
            if path.is_file():
                if path not in documents:
                    documents[path] = read_help(path)
                text = documents[path]
                matched = all(word in text.lower() for word in words)
        if matched:
            hit = dict(row)
            if text:
                position = text.lower().find(words[0])
                hit["excerpt"] = text[max(0, position - 60):position + 240]
            matches.append((0 if exact else 1 if all(word in name for word in words) else 2, hit))
    matches.sort(key=lambda item: (item[0], item[1]["name"].lower(), item[1]["type"]))
    return {"ok": True, "query": query, "total": len(matches), "matches": [hit for _, hit in matches[:limit]],
            "note": "Index is a discovery snapshot, not proof of installed availability or version compatibility."}


def get_docs(name: str, kind: str | None, help_root: Path | None, version: str | None,
             project: Path | None = None) -> dict:
    rows = load_catalog() + (project_routines(project) if project else [])
    candidates = [row for row in rows if row["name"].lower() == name.lower()
                  and (not kind or row["type"].lower() == kind.lower())]
    # Newer local routines may not yet appear in the upstream discovery snapshot.
    if not candidates and help_root and ENTRY_RE.fullmatch(name):
        for path in (help_root / "idl").rglob("*.htm"):
            if path.stem.lower() == name.lower():
                candidates.append({"name": name, "type": "Unknown", "source": "local-help",
                                   "link": "/" + path.relative_to(help_root).as_posix()})
    if len(candidates) != 1:
        return {"ok": False, "error": "Routine not found" if not candidates else "Ambiguous routine; specify --type or use the project source directly",
                "candidates": candidates}
    row = candidates[0]
    if row["source"] == "project":
        return {"ok": True, "routine": row, "text": Path(row["file"]).read_text(encoding="utf-8-sig", errors="replace"),
                "compatibility": "Project code must be compiled and tested against the detected IDL version."}
    path = doc_path(help_root, row["link"]) if help_root else None
    result = {"routine": row, "installed_version": version,
              "online_url": "https://www.nv5geospatialsoftware.com/docs/" + Path(unquote(row["link"].split("#")[0])).stem + ".html",
              "local_file": str(path) if path else None}
    if not path or not path.is_file():
        return {"ok": False, **result, "error": "Local documentation missing; retrieve official online documentation and verify its version history before use."}
    text = read_help(path)
    match = re.search(r"(?im)^Version History\s*$", text)
    history = text[match.end():].split("See Also", 1)[0].strip() if match else None
    return {"ok": True, **result, "text": text, "version_history": history,
            "compatibility": "Read the syntax, keywords and version history; test the selected API. Missing history does not prove compatibility."}


def interpret_execution(process: dict, token: str, file_count: int, run: bool) -> dict:
    output = process["output"]
    begin, end = token + "BEGIN", token + "END"
    framed = begin in output and end in output
    body = output.split(begin, 1)[1].split(end, 1)[0] if framed else output
    errors = [int(value) for value in re.findall(re.escape(token) + r"COMPILE=\s*(-?\d+)", body)]
    # Some compiler failures can leave CODE at zero, so also inspect compiler diagnostics.
    bad_diagnostics = [line.strip() for line in body.splitlines()
                       if re.search(r"%\s*(?:Syntax error|Compilation error|Error|Attempt to|Procedure was compiled|Function was compiled|Variable is undefined)", line, re.I)
                       and not re.search(r"%\s*Compiled module:", line, re.I)]
    compiled = framed and len(errors) == file_count and all(value == 0 for value in errors) and not bad_diagnostics
    ran = token + "RUN_OK" in body and token + "RUN_FAIL" not in body if run else None
    ok = (not process["timed_out"] and process["returncode"] == 0 and compiled and (ran if run else True))
    warnings = output.split(end, 1)[1].strip() if end in output else ""
    startup = output.split(begin, 1)[0].strip() if begin in output else ""
    return {"ok": bool(ok), "compiled": compiled, "ran": ran, "compile_error_codes": errors,
            "diagnostics": bad_diagnostics, "environment_output": {"startup": startup, "shutdown": warnings},
            "process": process}


def verify_files(idl: Path, files: list[Path], cwd: Path, timeout: float, entry: str | None,
                 includes: list[Path] | None = None) -> dict:
    files = [path.resolve() for path in files]
    for path in files:
        if not path.is_file():
            raise IDLToolError(f"Code file not found: {path}")
        compile_command(path)  # Validate control characters/quotes before creating console commands.
    for directory in includes or []:
        if not directory.is_dir():
            raise IDLToolError(f"Include directory not found: {directory}")
    if entry and not ENTRY_RE.fullmatch(entry):
        raise IDLToolError("--entry must be a procedure name; put arguments/assertions in a test procedure")
    token = "DKIDL" + uuid.uuid4().hex
    directories = list(dict.fromkeys([cwd.resolve(), *[path.parent for path in files], *(includes or [])]))
    commands = [f"print, '{token}BEGIN'", "message, /reset", "dk_idl_skill_args = command_line_args()"]
    # Windows IDL pipes cannot reliably decode Unicode paths. Native argv works;
    # send paths as data, CD to each directory, and compile ASCII basenames.
    data_args = [str(directory) for directory in directories]
    for index, directory in enumerate(directories):
        commands.append(f"!PATH = dk_idl_skill_args[{index}] + path_sep(/search_path) + !PATH")
    # Compile first, then run only if every file compiled. No .run or top-level execution.
    commands += ["dk_idl_skill_all_ok = 1b"]
    needs_temporary = bool(entry) or any(not path.name.isascii() for path in files)
    temporary_context = tempfile.TemporaryDirectory(prefix="dk-idl-") if needs_temporary else nullcontext(None)
    with temporary_context as temporary:
        if entry:
            runner_name = "dk_idl_skill_run_" + uuid.uuid4().hex
            runner = Path(temporary) / (runner_name + ".pro")
            runner.write_text(f"""pro {runner_name}, entry
  compile_opt idl2
  catch, error_code
  if error_code ne 0 then begin
    catch, /cancel
    print, '{token}RUN_FAIL=', !ERROR_STATE.MSG
    return
  endif
  call_procedure, entry
  catch, /cancel
  print, '{token}RUN_OK'
end
""", encoding="ascii")
            compile_files = [runner, *files]
        else:
            compile_files = files
        staged = []
        for index, path in enumerate(compile_files):
            actual = path
            if not path.name.isascii():
                actual = Path(temporary) / f"source_{index}.pro"
                shutil.copyfile(path, actual)
                staged.append({"source": str(path), "temporary_file": str(actual)})
            data_args.append(str(actual.parent))
            commands += [f"cd, dk_idl_skill_args[{len(data_args) - 1}]", "message, /reset", '.compile "' + actual.name + '"',
                         f"print, '{token}COMPILE=', !ERROR_STATE.CODE",
                         "if !ERROR_STATE.CODE ne 0 then dk_idl_skill_all_ok = 0b"]
        commands.append("cd, dk_idl_skill_args[0]")
        if entry:
            commands.append(f"if dk_idl_skill_all_ok then {runner_name}, {idl_string(entry)}")
        commands += [f"print, '{token}END'", "exit"]
        process = invoke(idl, commands, cwd, timeout, data_args)
    return {**interpret_execution(process, token, len(compile_files), bool(entry)),
            "files": [str(path) for path in files], "entry": entry, "executable": str(idl), "staged_sources": staged}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("doctor", "search", "docs", "check", "run"):
        child = sub.add_parser(command)
        child.add_argument("--idl", help="Executable path or name; otherwise discover through PATH")
        child.add_argument("--cwd", type=Path, default=Path.cwd())
        child.add_argument("--timeout", type=float, default=60)
        if command in {"search", "docs"}:
            child.add_argument("query")
            child.add_argument("--type", dest="kind")
            child.add_argument("--project", type=Path)
            child.add_argument("--help-root", type=Path, help="The help/online_help/Subsystems directory")
            if command == "search":
                child.add_argument("--text", action="store_true", help="Search local documentation content too")
                child.add_argument("--limit", type=int, default=20)
        if command in {"check", "run"}:
            child.add_argument("files", type=Path, nargs="+")
            child.add_argument("--include", type=Path, action="append", default=[])
            if command == "run":
                child.add_argument("--entry", required=True)
    args = parser.parse_args()
    try:
        if args.timeout <= 0 or not args.cwd.is_dir():
            raise IDLToolError("Positive timeout and existing --cwd are required")
        if getattr(args, "project", None) and not args.project.is_dir():
            raise IDLToolError("--project must be an existing directory")
        if args.command == "search" and not args.text:
            if args.limit <= 0:
                raise IDLToolError("--limit must be positive")
            result = search(args.query, args.kind, args.project, limit=args.limit)
        elif args.command in {"search", "docs"}:
            info = None
            runtime_error = None
            if args.help_root:
                help_root = args.help_root.resolve()
            else:
                try:
                    info = doctor(find_idl(args.idl), args.cwd, args.timeout)
                except IDLToolError as exc:
                    # Project docs and official fallback links remain useful without a runtime.
                    info = {}
                    runtime_error = str(exc)
                help_root = Path(info["help_root"]) if info.get("help_root") else None
            if args.command == "search":
                if not help_root or not help_root.is_dir():
                    raise IDLToolError("--text requires the local IDL help directory")
                result = search(args.query, args.kind, args.project, help_root, True, args.limit)
            else:
                result = get_docs(args.query, args.kind, help_root, info.get("version") if info else None, args.project)
                if runtime_error:
                    result["runtime_error"] = runtime_error
        else:
            idl = find_idl(args.idl)
            result = doctor(idl, args.cwd, args.timeout) if args.command == "doctor" else verify_files(
                idl, args.files, args.cwd, args.timeout, getattr(args, "entry", None), args.include)
    except (IDLToolError, OSError, ValueError) as exc:
        result = {"ok": False, "error": str(exc)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
