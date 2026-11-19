"""source.producer -- every dwg_graph_ir.v1 records what produced it.

The same drawing converted at two times can differ because the code changed,
so an IR must name the code commit, the engine, and the native modules that
made it. The stamp must never fail a conversion: what it cannot determine is
null with a reason in ``errors``.

No AutoCAD, router, or real drawing is used.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_TOOLS = _REPO / "tools"
for _p in (str(_REPO), str(_TOOLS)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cadctl  # noqa: E402
import ir_builder  # noqa: E402
import producer_stamp  # noqa: E402

_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _graph_result():
    return {
        "modelspace_entities": 1,
        "entities": [{
            "handle": "10", "dxf_name": "AcDbLine", "layer": "0",
            "owner_handle": "1F", "space": "model",
            "start": [0.0, 0.0, 0.0], "end": [10.0, 0.0, 0.0],
        }],
    }


def _modules(tmp_path):
    crx = tmp_path / "Ariadne.AcadNative.crx"
    dbx = tmp_path / "Ariadne.AcadNativeDbx.dbx"
    crx.write_bytes(b"crx bytes")
    dbx.write_bytes(b"dbx bytes")
    return crx, dbx


def test_stamp_in_git_checkout_names_the_commit():
    producer = producer_stamp.stamp({}, "inspect.database.graph")

    assert producer["code"]["repo"] == "autocad-mcp"
    assert _HEX40.match(producer["code"]["commit"])
    assert isinstance(producer["code"]["dirty"], bool)
    assert producer["operation"] == "inspect.database.graph"
    assert producer["argv"] == [str(a) for a in sys.argv]
    json.dumps(producer)  # the block must serialize as-is


def test_stamp_without_git_returns_nulls_and_reasons(tmp_path, monkeypatch):
    def no_git(*args, **kwargs):
        raise FileNotFoundError("git not found")

    monkeypatch.setattr(subprocess, "run", no_git)
    producer = producer_stamp.stamp({}, "inspect.geometry.extract", repo_root=tmp_path)

    assert producer["code"]["commit"] is None
    assert producer["code"]["dirty"] is None
    assert any(e.startswith("code.commit:") for e in producer["errors"])
    assert any(e.startswith("code.dirty:") for e in producer["errors"])


def test_module_hashes_equal_sha256_of_the_reported_files(tmp_path):
    crx, dbx = _modules(tmp_path)
    producer = producer_stamp.stamp(
        {"crx_module": str(crx), "dbx_module": str(dbx)}, "inspect.database.graph")

    assert producer["native_modules"] == {
        "Ariadne.AcadNative.crx": hashlib.sha256(b"crx bytes").hexdigest(),
        "Ariadne.AcadNativeDbx.dbx": hashlib.sha256(b"dbx bytes").hexdigest(),
    }
    assert not any(e.startswith("native_modules") for e in producer.get("errors", []))


def test_geometry_extract_path_hashes_the_extractor_dll(tmp_path):
    # inspect.geometry.extract NETLOADs a managed extractor DLL instead of crx/dbx.
    dll = tmp_path / "Ariadne.AutoCad.Extractor.dll"
    dll.write_bytes(b"dll bytes")
    producer = producer_stamp.stamp({"extractor_dll": str(dll)}, "inspect.geometry.extract")

    assert producer["native_modules"] == {
        "Ariadne.AutoCad.Extractor.dll": hashlib.sha256(b"dll bytes").hexdigest(),
    }
    assert not any(e.startswith("native_modules") for e in producer.get("errors", []))


def test_missing_module_is_null_with_reason(tmp_path):
    missing = tmp_path / "Ariadne.AcadNative.crx"
    producer = producer_stamp.stamp({"crx_module": str(missing)}, "inspect.database.graph")

    assert producer["native_modules"] == {"Ariadne.AcadNative.crx": None}
    assert any("Ariadne.AcadNative.crx" in e for e in producer["errors"])


def test_unreported_engine_is_null_with_reason():
    producer = producer_stamp.stamp("accoreconsole not found", "inspect.database.graph")

    assert producer["engine"] == {"path": None, "file_version": None}
    assert any(e.startswith("engine:") for e in producer["errors"])
    assert any(e.startswith("native_modules:") for e in producer["errors"])


@pytest.mark.skipif(os.name != "nt", reason="Windows version resource")
def test_engine_file_version_is_read_from_the_exe():
    producer = producer_stamp.stamp({"engine": sys.executable}, "inspect.database.graph")

    assert producer["engine"]["path"] == sys.executable
    assert re.match(r"^\d+\.\d+\.\d+\.\d+$", producer["engine"]["file_version"])


def test_engine_without_version_resource_is_null_with_reason(tmp_path):
    fake = tmp_path / "accoreconsole.exe"
    fake.write_bytes(b"not a PE file")
    producer = producer_stamp.stamp({"engine": str(fake)}, "inspect.database.graph")

    assert producer["engine"] == {"path": str(fake), "file_version": None}
    assert any(e.startswith("engine.file_version:") for e in producer["errors"])


def test_ir_keeps_producer_and_passes_the_schema_gate(tmp_path):
    crx, dbx = _modules(tmp_path)
    producer = producer_stamp.stamp(
        {"engine": sys.executable, "crx_module": str(crx), "dbx_module": str(dbx)},
        "inspect.database.graph")
    source_meta = {"dwg_path": "staged.dwg", "format": "dwg", "producer": producer}

    ir = ir_builder.build_ir_from_database_graph(_graph_result(), source_meta)
    written = Path(ir_builder.write_ir(ir, tmp_path / "dwg_graph_ir.json"))

    on_disk = json.loads(written.read_text(encoding="utf-8"))
    assert on_disk["source"]["producer"] == json.loads(json.dumps(producer))


def test_schema_rejects_a_producer_that_is_not_an_object(tmp_path):
    ir = ir_builder.build_ir_from_database_graph(
        _graph_result(), {"dwg_path": "staged.dwg", "producer": "a218c35"})

    with pytest.raises(ir_builder.IRConformanceError):
        ir_builder.write_ir(ir, tmp_path / "dwg_graph_ir.json")


def test_rich_inspect_writes_producer_from_the_router_envelope(tmp_path, monkeypatch):
    crx, dbx = _modules(tmp_path)
    engine_output = {"engine": sys.executable, "crx_module": str(crx), "dbx_module": str(dbx)}

    def fake_runner(staged_dwg, run_dir, operation, **kwargs):
        return {
            "stdout_path": str(tmp_path / "stdout.txt"),
            "stderr_path": str(tmp_path / "stderr.txt"),
            "envelope": {"execution": {"engine_output": engine_output}},
            "result_json": None,
            "result": _graph_result(),
        }

    monkeypatch.setattr(cadctl.run_job, "run_router_cad_job", fake_runner)
    src = tmp_path / "original.bin"
    staged = tmp_path / "staged.bin"
    src.write_bytes(b"synthetic input")
    staged.write_bytes(b"synthetic input")
    out = tmp_path / "out"
    out.mkdir()
    ir_path = out / "dwg_graph_ir.json"

    cadctl.Cad(router_home=tmp_path)._inspect_rich_native(
        src, staged, {"byte_size": staged.stat().st_size}, out,
        out / "cad_job.json", out / "cad_result.json", ir_path)

    producer = json.loads(ir_path.read_text(encoding="utf-8"))["source"]["producer"]
    assert producer["operation"] == "inspect.database.graph"
    assert producer["engine"]["path"] == sys.executable
    assert set(producer["native_modules"]) == {crx.name, dbx.name}
    assert all(_HEX64.match(h) for h in producer["native_modules"].values())
