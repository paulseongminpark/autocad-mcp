"""producer_stamp.py -- record what produced a dwg_graph_ir.v1 document.

``stamp()`` returns the ``source.producer`` block: the repo commit and whether
the code paths that shape an IR were edited, the accoreconsole the router ran
and its file version, the sha256 of each native module the router loaded, the
operation, and the producing process's argv. With these, the same IR can be
made again later.

The stamp never raises. A part that cannot be determined is null, and the
reason goes into ``errors`` (present only when something failed).

Standard library only.
"""
from __future__ import annotations

import hashlib
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

REPO_NAME = "autocad-mcp"
REPO_ROOT = Path(__file__).resolve().parent.parent
# The repo always carries a regenerated reports/ status file, so "dirty" only
# looks at the paths whose content can change an IR.
_DIRTY_PATHS = ("tools", "src", "schemas", "prebuilt")
_GIT_TIMEOUT_S = 10
# engine_output keys under which router lanes report the native modules they loaded.
_MODULE_KEYS = ("crx_module", "dbx_module", "arx_module", "extractor_dll")


def stamp(engine_output, operation: str, *, repo_root: Path | str = REPO_ROOT) -> dict:
    """Build the ``source.producer`` block for one IR.

    engine_output: the router's ``envelope["execution"]["engine_output"]``; may be
    empty or not a dict. operation: the operation that produced the IR.
    """
    engine_output = engine_output if isinstance(engine_output, dict) else {}
    errors: list[str] = []

    commit, dirty, code_errors = _code_identity(str(repo_root))
    errors.extend(code_errors)

    engine_path = engine_output.get("engine")
    file_version = None
    if not isinstance(engine_path, str) or not engine_path:
        engine_path = None
        errors.append("engine: router did not report the accoreconsole path")
    else:
        try:
            file_version = _file_version(engine_path)
        except Exception as exc:
            errors.append(f"engine.file_version: {type(exc).__name__}: {exc}")

    native_modules: dict = {}
    for key in _MODULE_KEYS:
        module_path = engine_output.get(key)
        if not isinstance(module_path, str) or not module_path:
            continue
        name = Path(module_path).name
        try:
            native_modules[name] = _sha256_file(module_path)
        except Exception as exc:
            native_modules[name] = None
            errors.append(f"native_modules[{name}]: {type(exc).__name__}: {exc}")
    if not native_modules:
        errors.append("native_modules: router reported no native module paths")

    producer = {
        "code": {"repo": REPO_NAME, "commit": commit, "dirty": dirty},
        "engine": {"path": engine_path, "file_version": file_version},
        "native_modules": native_modules,
        "operation": operation,
        "argv": [str(a) for a in sys.argv],
    }
    if errors:
        producer["errors"] = errors
    return producer


@lru_cache(maxsize=None)
def _code_identity(repo_root: str) -> tuple:
    """(commit, dirty, errors) for repo_root, computed once per process."""
    errors = []
    commit = None
    dirty = None
    try:
        out = _git(repo_root, "rev-parse", "HEAD").strip()
        if len(out) == 40 and all(c in "0123456789abcdef" for c in out):
            commit = out
        else:
            errors.append(f"code.commit: unexpected git output {out[:60]!r}")
    except Exception as exc:
        errors.append(f"code.commit: {type(exc).__name__}: {exc}")
    try:
        out = _git(repo_root, "status", "--porcelain", "--untracked-files=no",
                   "--", *_DIRTY_PATHS)
        dirty = bool(out.strip())
    except Exception as exc:
        errors.append(f"code.dirty: {type(exc).__name__}: {exc}")
    return commit, dirty, tuple(errors)


def _git(repo_root: str, *args: str) -> str:
    proc = subprocess.run(
        ["git", *args], cwd=repo_root, stdin=subprocess.DEVNULL,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=_GIT_TIMEOUT_S,
    )
    if proc.returncode != 0:
        first = (proc.stderr or "").strip().splitlines()[:1]
        raise RuntimeError(f"git exit {proc.returncode}: {first[0] if first else ''}")
    return proc.stdout


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_version(path: str) -> str:
    """Windows FILEVERSION of path as 'a.b.c.d' (VS_FIXEDFILEINFO)."""
    import ctypes
    from ctypes import wintypes

    version = ctypes.WinDLL("version", use_last_error=True)
    version.GetFileVersionInfoSizeW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD)]
    version.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    version.GetFileVersionInfoW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    version.GetFileVersionInfoW.restype = wintypes.BOOL
    version.VerQueryValueW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR,
                                       ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT)]
    version.VerQueryValueW.restype = wintypes.BOOL

    size = version.GetFileVersionInfoSizeW(path, None)
    if not size:
        raise ctypes.WinError(ctypes.get_last_error())
    buf = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(path, 0, size, buf):
        raise ctypes.WinError(ctypes.get_last_error())
    info_ptr = ctypes.c_void_p()
    info_len = wintypes.UINT()
    if not version.VerQueryValueW(buf, "\\", ctypes.byref(info_ptr), ctypes.byref(info_len)) \
            or info_len.value < 4 * 4:
        raise OSError("no VS_FIXEDFILEINFO in version resource")
    # VS_FIXEDFILEINFO: dwSignature, dwStrucVersion, dwFileVersionMS, dwFileVersionLS, ...
    fields = (wintypes.DWORD * 4).from_address(info_ptr.value)
    if fields[0] != 0xFEEF04BD:
        raise OSError("bad VS_FIXEDFILEINFO signature")
    ms, ls = fields[2], fields[3]
    return f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
