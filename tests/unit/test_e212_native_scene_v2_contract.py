#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Hermetic E212 Phase A contract tests for the native graph producer and IR schema.

These tests intentionally do not need AutoCAD. They pin the C++ producer seam that a
native build exercises and the profile-specific schema union. Live ObjectARX validation
is a separate, environment-gated receipt.
"""
from __future__ import annotations

import copy
import json
import os
import sys
import unittest
from unittest import mock

try:
    import jsonschema
except Exception:  # pragma: no cover - optional in minimal stdlib environments
    jsonschema = None


_THIS = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(os.path.dirname(_THIS))
_TOOLS = os.path.join(_REPO, "tools")
if _TOOLS not in sys.path:
    sys.path.insert(0, _TOOLS)
_CPP = os.path.join(
    _REPO, "src", "Ariadne.AcadNative", "AriadneNativeJob.cpp")
_SCHEMA = os.path.join(_REPO, "schemas", "dwg_graph_ir.v1.schema.json")
_PROFILE = "ariadne.dwg_graph_ir.e212_native_scene_v2"
_NUMERIC_CONTRACT = "binary64_max_digits10;row_major;column_vector;right_handed"
_SOURCE_SHA256 = "a" * 64
_SOURCE_META = {
    "dwg_path": "staged.dwg",
    "format": "dwg",
    "sha256": _SOURCE_SHA256,
}
_TRANSFORM_CONVENTION = (
    "row_major; q=M@[x,y,z,1]; definition_to_immediate_owner; "
    "btr_origin_included_once"
)
_BLOCKED_RECEIPT = {
    "status": "BLOCKED",
    "reason_code": "NATIVE_EXACT_POPULATION_EXTENT_NOT_IMPLEMENTED",
    "algorithm_id": "cadagent.e212_native_scene_v2.extent.unavailable.v1",
    "block_expanded": False,
    "paper_included": False,
    "off_frozen_included_without_reading_style": True,
    "xref_mode": "none",
}
_IDENTITY_4X4 = [
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
]
_PLANE = {
    "origin": [0.0, 0.0, 0.0],
    "x_axis": [1.0, 0.0, 0.0],
    "y_axis": [0.0, 1.0, 0.0],
    "normal": [0.0, 0.0, 1.0],
    "handedness": "x_cross_y_equals_normal",
    "positive_angle": "x_toward_y_radians",
}


def _load_schema():
    with open(_SCHEMA, "r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def _minimal_profile_ir(*, entities=None, receipt=None):
    normalized_entities = list(entities or [])
    entities_by_type = {}
    for entity in normalized_entities:
        dxf_name = entity["dxf_name"]
        entities_by_type[dxf_name] = entities_by_type.get(dxf_name, 0) + 1
    return {
        "schema": "ariadne.dwg_graph_ir.v1",
        "ir_version": "1.1.0",
        "producer_profile": _PROFILE,
        "producer_profile_version": "1.0.0",
        "numeric_contract": _NUMERIC_CONTRACT,
        "coverage_level": "native_full",
        "source": {"format": "dwg", "sha256": _SOURCE_SHA256},
        "database": {
            "insbase": [0.0, 0.0, 0.0],
            "extents": {"extmin": [0.0, 0.0, 0.0], "extmax": [0.0, 0.0, 0.0]},
            "units": {"insunits": 4},
            "header_vars": {},
            "modelspace_realized_extent_receipt": copy.deepcopy(
                _BLOCKED_RECEIPT if receipt is None else receipt),
        },
        "symbol_tables": {
            "layers": [],
            "block_table_records": [{
                "handle": "1F", "name": "*Model_Space", "is_layout": True,
                "is_anonymous": False, "is_xref": False,
                "origin": [0.0, 0.0, 0.0],
                "entity_count": len(normalized_entities),
            }],
        },
        "block_definitions": [],
        "block_references": [],
        "xrefs": [],
        "layouts": [{
            "name": "Model",
            "block_table_record_handle": "1F",
        }],
        "entities": normalized_entities,
        "diagnostics": {
            "entity_count": len(normalized_entities),
            "realized_entity_count": len(normalized_entities),
            "count_scope": "modelspace",
            "entities_by_type": entities_by_type,
            "warnings": [],
            "errors": [],
            "coverage": {
                "modelspace_count_from_native": len(normalized_entities),
                "paperspace_count_from_native": 0,
                "realized_entity_count": len(normalized_entities),
                "match": True,
                "proxy_or_undecoded_count": 0,
                "section_status": {
                    "population_entities": "implemented",
                    "proxy_objects": "partial",
                }
            },
        },
    }


def _entity(handle, class_name, dxf_name, kind, geometry):
    entity = {
        "handle": handle,
        "class": class_name,
        "dxf_name": dxf_name,
        "owner_handle": "1F",
        "space": "model",
        "layer": "0",
        "bbox": [],
        "geometry": {"kind": kind, **geometry},
        "source": {},
    }
    if kind == "block_reference" and "block_record_handle" in geometry:
        entity["block_record_handle"] = geometry["block_record_handle"]
    return entity


def _native_profile_graph():
    static_semantics = {
        "mode": "STATIC_SINGLE",
        "row_count": 1,
        "column_count": 1,
        "row_spacing": 0.0,
        "column_spacing": 0.0,
        "dynamic_evaluated_btr_handle": None,
        "xclip": "NONE",
        "xref_source_sha256": None,
    }
    minsert_semantics = {
        **static_semantics,
        "mode": "MINSERT",
        "row_count": 2,
        "column_count": 3,
        "row_spacing": 4.0,
        "column_spacing": 5.0,
    }
    return {
        "producer_profile": _PROFILE,
        "profile_version": "1.0.0",
        "numeric_contract": _NUMERIC_CONTRACT,
        "modelspace_entities": 2,
        "paperspace_entities": 0,
        "database": {
            "insbase": [0.0, 0.0, 0.0],
            "extents": {"extmin": [0.0, 0.0, 0.0], "extmax": [1.0, 1.0, 1.0]},
            "units": {"insunits": 4},
            "header_vars": {},
            "modelspace_realized_extent_receipt": copy.deepcopy(_BLOCKED_RECEIPT),
        },
        "symbol_tables": {"layers": []},
        "block_table_records": [
            {"handle": "1F", "name": "*Model_Space", "is_layout": True,
             "is_anonymous": False, "is_xref": False,
             "origin": [0.0, 0.0, 0.0], "entity_count": 2},
            {"handle": "A0", "name": "OUTER", "is_layout": False,
             "is_anonymous": False, "is_xref": False,
             "origin": [0.0, 0.0, 0.0], "entity_count": 1},
            {"handle": "B0", "name": "INNER", "is_layout": False,
             "is_anonymous": False, "is_xref": False,
             "origin": [0.0, 0.0, 0.0], "entity_count": 0},
        ],
        "entities": [
            {
                "handle": "20", "dxf_name": "AcDbArc",
                "owner_handle": "1F", "space": "model", "layer": "0",
                "center": [0.0, 0.0, 0.0], "radius": 1.0,
                "start_angle": 0.0, "end_angle": 1.0,
                "normal": [0.0, 0.0, 1.0],
                "coordinates_frame": "immediate_owner",
                "plane_basis_owner": copy.deepcopy(_PLANE),
                "legacy_polyline_type": None,
            },
            {
                "handle": "21", "dxf_name": "AcDbBlockReference",
                "owner_handle": "1F", "space": "model", "layer": "0",
                "block_name": "OUTER", "block_record_handle": "A0",
                "position": [1.0, 2.0, 3.0], "scale": [1.0, 1.0, 1.0],
                "rotation": 0.0, "normal": [0.0, 0.0, 1.0],
                "definition_to_owner_transform": list(_IDENTITY_4X4),
                "transform_convention": _TRANSFORM_CONVENTION,
                "instance_semantics": static_semantics,
            },
        ],
        "block_definitions": [
            {
                "handle": "A0", "name": "OUTER",
                "origin": [0.0, 0.0, 0.0], "entity_count": 1,
                "def_entities": [
                    {
                        "handle": "31", "dxf_name": "AcDbMInsertBlock",
                        "layer": "0", "block_name": "INNER",
                        "block_record_handle": "B0",
                        "position": [0.0, 0.0, 0.0],
                        "scale": [1.0, 1.0, 1.0], "rotation": 0.0,
                        "normal": [0.0, 0.0, 1.0],
                        "definition_to_owner_transform": list(_IDENTITY_4X4),
                        "transform_convention": _TRANSFORM_CONVENTION,
                        "instance_semantics": minsert_semantics,
                    }
                ],
            },
            {
                "handle": "B0", "name": "INNER",
                "origin": [0.0, 0.0, 0.0], "entity_count": 0,
                "def_entities": [],
            },
        ],
        "layouts": [{
            "name": "Model",
            "block_table_record_handle": "1F",
        }],
        "coverage": {
            "population_entities": "implemented",
            "proxy_objects": "partial",
            "sections_present": ["entities", "database", "block_definitions"],
            "sections_skipped": [],
        },
    }


class TestNativeSourceContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(_CPP, "r", encoding="utf-8-sig") as stream:
            cls.source = stream.read()
        # C++ JSON literals escape their quotes. This view makes assertions read
        # like the resulting wire keys while retaining all surrounding source.
        cls.rendered_literals = cls.source.replace(r'\"', '"')

    def test_insert_transform_comes_directly_from_objectarx(self):
        self.assertIn(
            "const AcGeMatrix3d definitionToOwner = pRef->blockTransform();",
            self.source,
        )
        self.assertIn("matrix.entry[row][column]", self.source)
        self.assertIn(_TRANSFORM_CONVENTION, self.source)
        self.assertIn("jsonNumberWithoutNegativeZero", self.source)

    def test_instance_families_are_explicit(self):
        for token in (
            "AcDbMInsertBlock::cast(pRef)",
            "AcDbDynBlockReference dynamicReference(referenceId)",
            "anonymousBlockTableRecord()",
            "ACRX_PE_PTR(pRef, AcDbAnnotativeObjectPE)",
            'mode = "STATIC_SINGLE"',
            'mode = "MINSERT"',
            'mode = "DYNAMIC"',
            'mode = "ANNOTATIVE"',
            'mode = "OTHER"',
            '"xref_source_sha256":null',
        ):
            haystack = self.rendered_literals if token.startswith('"') else self.source
            self.assertIn(token, haystack)

    def test_planar_metadata_uses_owner_basis_and_legacy_wcs_accessor(self):
        self.assertIn("AcGeMatrix3d::planeToWorld", self.source)
        self.assertIn('"coordinates_frame":"immediate_owner"', self.rendered_literals)
        self.assertIn("p2d->vertexPosition(*pV)", self.source)
        self.assertNotIn("ownerPlaneOrigin(", self.source)

        line_start = self.source.index(
            "if (AcDbLine* pLine = AcDbLine::cast(pEnt))")
        line_end = self.source.index(
            "else if (AcDbArc* pArc = AcDbArc::cast(pEnt))", line_start)
        self.assertNotIn("ownerPlaneMetadata", self.source[line_start:line_end])

    def test_raw_profile_and_honest_extent_receipt_are_native_output(self):
        graph_start = self.source.index('else if (op == "inspect.database.graph")')
        graph_end = self.source.index('else if (op == "write.layer.create")', graph_start)
        graph = self.source[graph_start:graph_end].replace(r'\"', '"')
        self.assertIn('"producer_profile":"' + _PROFILE + '"', graph)
        self.assertIn('"profile_version":"1.0.0"', graph)
        self.assertNotIn("producer_profile_version", graph)
        self.assertIn(_NUMERIC_CONTRACT, graph)

        db_start = self.source.index("static std::string databaseMetaJson")
        db_end = self.source.index("static std::string collectDatabaseGraph", db_start)
        database = self.source[db_start:db_end].replace(r'\"', '"')
        for value in (
            "modelspace_realized_extent_receipt",
            _BLOCKED_RECEIPT["reason_code"],
            _BLOCKED_RECEIPT["algorithm_id"],
            '"block_expanded":false',
            '"paper_included":false',
            '"off_frozen_included_without_reading_style":true',
            '"xref_mode":"none"',
        ):
            self.assertIn(value, database)
        self.assertIn('(populationComplete ? "implemented" : "error")', self.source)

    def test_population_and_xclip_access_fail_closed(self):
        for token in (
            "populationComplete = false;",
            "successfulEntityOpens == total",
            "pointStatus != Acad::eOk || bulgeStatus != Acad::eOk",
            "widthsStatus != Acad::eOk",
            "successfulVertexReads != n",
            "successfulVertexOpens != vertexMembers",
            "definitionPopulationComplete = collectEntitiesFromBlock(",
            "successfulBtrOpens != btrCount",
            "paperPopulationComplete = false;",
            'graphPopulationComplete ? "ok" : "error"',
        ):
            self.assertIn(token, self.source)
        self.assertIn("++total;  // count iterator members independently", self.source)
        self.assertIn("++btrCount;  // count table members independently", self.source)

        xclip_start = self.source.index("static std::string spatialFilterJson")
        xclip_end = self.source.index("static bool resbufCodeIsString", xclip_start)
        xclip = self.source[xclip_start:xclip_end]
        self.assertIn("bool& lookupComplete", xclip)
        self.assertIn("es == Acad::eKeyNotFound", xclip)
        self.assertIn("lookupComplete = true;", xclip)
        self.assertIn("if (!spatialFilterLookupComplete)", self.source)


class TestBuilderProfilePropagation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import ir_builder
        cls.ir = ir_builder.build_ir_from_database_graph(
            _native_profile_graph(), _SOURCE_META)

    def test_raw_profile_version_maps_to_one_normalized_name(self):
        self.assertEqual(self.ir["producer_profile"], _PROFILE)
        self.assertEqual(self.ir["producer_profile_version"], "1.0.0")
        self.assertEqual(self.ir["numeric_contract"], _NUMERIC_CONTRACT)
        self.assertNotIn("profile_version", self.ir)

    def test_database_receipt_and_population_status_survive(self):
        self.assertEqual(
            self.ir["database"]["modelspace_realized_extent_receipt"],
            _BLOCKED_RECEIPT,
        )
        coverage = self.ir["diagnostics"]["coverage"]
        self.assertEqual(coverage["modelspace_count_from_native"], 2)
        self.assertEqual(coverage["paperspace_count_from_native"], 0)
        status = coverage["section_status"]
        self.assertEqual(status["population_entities"], "implemented")
        self.assertEqual(status["proxy_objects"], "partial")

    def test_diagnostic_inventory_mismatches_fail_conformance(self):
        import ir_builder

        malformed_count = copy.deepcopy(self.ir)
        malformed_count["diagnostics"]["coverage"][
            "realized_entity_count"] = 1
        ok, _, errors = ir_builder.validate_ir(malformed_count)
        self.assertFalse(ok)
        self.assertTrue(any(
            "diagnostics.coverage.realized_entity_count mismatch" in error
            for error in errors
        ))

        malformed_types = copy.deepcopy(self.ir)
        malformed_types["diagnostics"]["entities_by_type"]["ARC"] = 99
        ok, _, errors = ir_builder.validate_ir(malformed_types)
        self.assertFalse(ok)
        self.assertTrue(any(
            "diagnostics.entities_by_type mismatch" in error
            for error in errors
        ))

    def test_native_space_partition_count_mismatch_fails_conformance(self):
        import ir_builder
        malformed = copy.deepcopy(self.ir)
        malformed["diagnostics"]["coverage"]["paperspace_count_from_native"] = 1
        ok, _, errors = ir_builder.validate_ir(malformed)
        self.assertFalse(ok)
        self.assertTrue(any(
            "paperspace_count_from_native mismatch" in error for error in errors))

    def test_geometry_preserves_required_nulls_and_transform(self):
        entities = {item["handle"]: item for item in self.ir["entities"]}
        arc_geometry = entities["20"]["geometry"]
        self.assertIn("legacy_polyline_type", arc_geometry)
        self.assertIsNone(arc_geometry["legacy_polyline_type"])
        self.assertEqual(arc_geometry["plane_basis_owner"], _PLANE)

        insert_geometry = entities["21"]["geometry"]
        self.assertEqual(insert_geometry["block_record_handle"], "A0")
        self.assertEqual(
            insert_geometry["definition_to_owner_transform"], _IDENTITY_4X4)
        semantics = insert_geometry["instance_semantics"]
        self.assertIn("dynamic_evaluated_btr_handle", semantics)
        self.assertIsNone(semantics["dynamic_evaluated_btr_handle"])
        self.assertIn("xref_source_sha256", semantics)
        self.assertIsNone(semantics["xref_source_sha256"])

    def test_vertex_count_is_preserved_and_mismatch_fails_conformance(self):
        import ir_builder
        graph = _native_profile_graph()
        graph["modelspace_entities"] = 3
        graph["block_table_records"][0]["entity_count"] = 3
        graph["entities"].append({
            "handle": "22", "dxf_name": "AcDbPolyline",
            "owner_handle": "1F", "space": "model", "layer": "0",
            "vertex_count": 1, "closed": False,
            "vertices": [{"point": [0.0, 0.0, 0.0], "bulge": 0.0}],
            "elevation": 0.0, "normal": [0.0, 0.0, 1.0],
            "coordinates_frame": "immediate_owner",
            "plane_basis_owner": copy.deepcopy(_PLANE),
            "legacy_polyline_type": None,
        })
        ir = ir_builder.build_ir_from_database_graph(
            graph, _SOURCE_META)
        polyline = next(item for item in ir["entities"] if item["handle"] == "22")
        self.assertEqual(polyline["geometry"]["vertex_count"], 1)
        ok, _, errors = ir_builder.validate_ir(ir)
        self.assertTrue(ok, errors)

        polyline["geometry"]["vertex_count"] = 2
        ok, _, errors = ir_builder.validate_ir(ir)
        self.assertFalse(ok)
        self.assertTrue(any("vertex_count mismatch" in error for error in errors))

    def test_block_definition_member_count_mismatch_fails_conformance(self):
        import ir_builder
        malformed = copy.deepcopy(self.ir)
        malformed["block_definitions"][0]["entity_count"] = 2
        ok, _, errors = ir_builder.validate_ir(malformed)
        self.assertFalse(ok)
        self.assertTrue(any("entity_count mismatch" in error for error in errors))

    def test_nested_minsert_is_normalized_and_projected_with_owner(self):
        nested = self.ir["block_definitions"][0]["def_entities"][0]
        self.assertEqual(nested["class"], "AcDbMInsertBlock")
        self.assertEqual(nested["dxf_name"], "INSERT")
        self.assertEqual(nested["geometry"]["kind"], "block_reference")
        self.assertEqual(nested["geometry"]["block_record_handle"], "B0")
        self.assertEqual(nested["owner_handle"], "A0")
        self.assertEqual(nested["space"], "block")

        projections = {item["handle"]: item for item in self.ir["block_references"]}
        self.assertEqual(set(projections), {"21", "31"})
        self.assertEqual(projections["31"]["owner_handle"], "A0")
        self.assertEqual(
            projections["31"]["instance_semantics"]["mode"], "MINSERT")
        self.assertIsNone(
            projections["31"]["instance_semantics"]["xref_source_sha256"])

    def test_unknown_closed_semantics_survive_for_fail_closed_validation(self):
        import ir_builder
        graph = _native_profile_graph()
        graph["entities"][0]["plane_basis_owner"]["future_basis_rule"] = True
        graph["entities"][1]["instance_semantics"]["future_instance_rule"] = True
        ir = ir_builder.build_ir_from_database_graph(
            graph, _SOURCE_META)
        entities = {item["handle"]: item for item in ir["entities"]}
        self.assertTrue(
            entities["20"]["geometry"]["plane_basis_owner"]["future_basis_rule"])
        self.assertTrue(
            entities["21"]["geometry"]["instance_semantics"]["future_instance_rule"])
        if jsonschema is not None:
            self.assertTrue(list(
                jsonschema.Draft7Validator(_load_schema()).iter_errors(ir)))

    def test_fractional_instance_count_is_not_truncated(self):
        import ir_builder
        graph = _native_profile_graph()
        graph["entities"][1]["instance_semantics"]["row_count"] = 1.5
        ir = ir_builder.build_ir_from_database_graph(
            graph, _SOURCE_META)
        semantics = ir["entities"][1]["geometry"]["instance_semantics"]
        self.assertEqual(semantics["row_count"], 1.5)
        if jsonschema is not None:
            self.assertTrue(list(
                jsonschema.Draft7Validator(_load_schema()).iter_errors(ir)))

    def test_numeric_strings_in_profile_fields_are_not_sanitized(self):
        import ir_builder
        graph = _native_profile_graph()
        graph["entities"][0]["plane_basis_owner"]["origin"][0] = "0"
        graph["entities"][1]["definition_to_owner_transform"][0] = "1"
        graph["entities"][1]["instance_semantics"]["row_count"] = "1"
        ir = ir_builder.build_ir_from_database_graph(
            graph, _SOURCE_META)
        entities = {item["handle"]: item for item in ir["entities"]}
        self.assertEqual(
            entities["20"]["geometry"]["plane_basis_owner"]["origin"][0], "0")
        self.assertEqual(
            entities["21"]["geometry"]["definition_to_owner_transform"][0], "1")
        self.assertEqual(
            entities["21"]["geometry"]["instance_semantics"]["row_count"], "1")
        ok, _, _ = ir_builder.validate_ir(ir)
        self.assertFalse(ok)

    def test_numeric_insert_target_is_preserved_and_rejected(self):
        import ir_builder
        graph = _native_profile_graph()
        graph["entities"][1]["block_record_handle"] = 279
        ir = ir_builder.build_ir_from_database_graph(
            graph, _SOURCE_META)
        entity = ir["entities"][1]
        self.assertEqual(entity["geometry"]["block_record_handle"], 279)
        self.assertEqual(entity["block_record_handle"], "279")
        ok, _, errors = ir_builder.validate_ir(ir)
        self.assertFalse(ok)
        self.assertTrue(errors)

    def test_profile_fails_closed_when_jsonschema_is_unavailable(self):
        import ir_builder
        real_import = __import__

        def import_without_jsonschema(name, *args, **kwargs):
            if name == "jsonschema":
                raise ImportError("intentional E212 fallback test")
            return real_import(name, *args, **kwargs)

        with mock.patch("builtins.__import__", side_effect=import_without_jsonschema):
            ok, method, errors = ir_builder.validate_ir(copy.deepcopy(self.ir))
        self.assertFalse(ok)
        self.assertEqual(method, "structural")
        self.assertEqual(
            errors,
            ["E212 profile requires jsonschema; structural fallback is insufficient"],
        )

    def test_mismatched_duplicate_insert_target_fails_conformance_gate(self):
        import ir_builder
        ir = copy.deepcopy(self.ir)
        ir["entities"][1]["block_record_handle"] = "BAD"
        ok, method, errors = ir_builder.validate_ir(ir)
        self.assertFalse(ok)
        self.assertIn(method, ("jsonschema", "structural"))
        self.assertTrue(any("block_record_handle mismatch" in error for error in errors))

    def test_profile_projection_requires_owner_and_insertion_point(self):
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        validator = jsonschema.Draft7Validator(_load_schema())
        for missing_key in ("owner_handle", "insertion_point"):
            ir = copy.deepcopy(self.ir)
            del ir["block_references"][0][missing_key]
            self.assertTrue(
                list(validator.iter_errors(ir)),
                "profile projection unexpectedly accepted missing %s" % missing_key,
            )

    def test_normalized_profile_ir_conforms_to_schema(self):
        if jsonschema is None:
            self.skipTest("SKIPPED_DEP: jsonschema not importable")
        errors = list(jsonschema.Draft7Validator(_load_schema()).iter_errors(self.ir))
        self.assertEqual(errors, [], "; ".join(error.message for error in errors[:10]))


@unittest.skipIf(jsonschema is None, "SKIPPED_DEP: jsonschema not importable")
class TestProfileSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = _load_schema()
        jsonschema.Draft7Validator.check_schema(cls.schema)
        cls.validator = jsonschema.Draft7Validator(cls.schema)

    def assertValid(self, document):
        errors = sorted(self.validator.iter_errors(document), key=lambda e: list(e.path))
        self.assertEqual(
            errors,
            [],
            "; ".join(
                "%s: %s" % ("/".join(str(p) for p in error.path), error.message)
                for error in errors[:10]
            ),
        )

    def assertInvalid(self, document):
        self.assertTrue(list(self.validator.iter_errors(document)))

    def test_unprofiled_legacy_branch_does_not_require_e212_envelope(self):
        legacy = _minimal_profile_ir()
        for key in (
                "producer_profile", "producer_profile_version",
                "numeric_contract", "layouts"):
            del legacy[key]
        legacy["source"] = {}
        legacy["database"]["units"] = {}
        del legacy["diagnostics"]["entities_by_type"]
        for key in (
                "realized_entity_count", "match",
                "proxy_or_undecoded_count", "section_status"):
            del legacy["diagnostics"]["coverage"][key]
        self.assertValid(legacy)

    def test_exact_blocked_receipt_validates_without_fake_measurements(self):
        self.assertValid(_minimal_profile_ir())

        extra = copy.deepcopy(_BLOCKED_RECEIPT)
        extra["bounds_xyz"] = [0.0] * 6
        self.assertInvalid(_minimal_profile_ir(receipt=extra))

    def test_fully_populated_pass_is_a_distinct_valid_shape(self):
        digest = "sha256:" + "a" * 64
        receipt = {
            "status": "PASS",
            "population_contract_sha256": digest,
            "model_btr_handle": "1F",
            "bounds_xyz": [-1.0, -2.0, -3.0, 4.0, 5.0, 6.0],
            "expected_realized_entity_events_total": 7,
            "expected_realized_leaf_count": 5,
            "population_digest_sha256": digest,
            "realized_event_extent_ledger_sha256": digest,
            "block_expanded": True,
            "paper_included": False,
            "off_frozen_included_without_reading_style": True,
            "xref_mode": "none",
            "algorithm_id": "cadagent.e212_native_scene_v2.extent.exact.v1",
        }
        self.assertValid(_minimal_profile_ir(receipt=receipt))

        incomplete = copy.deepcopy(receipt)
        del incomplete["realized_event_extent_ledger_sha256"]
        self.assertInvalid(_minimal_profile_ir(receipt=incomplete))

    def test_profile_requires_normalized_metadata_and_nested_population_status(self):
        missing_version = _minimal_profile_ir()
        del missing_version["producer_profile_version"]
        self.assertInvalid(missing_version)

        wrong_location = _minimal_profile_ir()
        wrong_location["diagnostics"]["coverage"] = {
            "population_entities": "implemented"
        }
        self.assertInvalid(wrong_location)

        missing_paper_count = _minimal_profile_ir()
        del missing_paper_count["diagnostics"]["coverage"][
            "paperspace_count_from_native"]
        self.assertInvalid(missing_paper_count)

    def test_profile_requires_exact_source_identity(self):
        for required_field in ("format", "sha256"):
            malformed = _minimal_profile_ir()
            del malformed["source"][required_field]
            with self.subTest(missing=required_field):
                self.assertInvalid(malformed)

        for field, invalid_value in (
                ("format", "dxf"),
                ("sha256", "A" * 64),
                ("sha256", "a" * 64 + "\n"),
                ("sha256", "sha256:" + "a" * 64)):
            malformed = _minimal_profile_ir()
            malformed["source"][field] = invalid_value
            with self.subTest(field=field, invalid_value=invalid_value):
                self.assertInvalid(malformed)

    def test_profile_requires_supported_integer_insunits(self):
        missing = _minimal_profile_ir()
        del missing["database"]["units"]["insunits"]
        self.assertInvalid(missing)

        for invalid_value in ("4", 0, True):
            malformed = _minimal_profile_ir()
            malformed["database"]["units"]["insunits"] = invalid_value
            with self.subTest(invalid_value=invalid_value):
                self.assertInvalid(malformed)

    def test_profile_requires_layout_handles_and_at_least_one_model_row(self):
        missing_name = _minimal_profile_ir()
        del missing_name["layouts"][0]["name"]
        self.assertInvalid(missing_name)

        missing_handle = _minimal_profile_ir()
        del missing_handle["layouts"][0]["block_table_record_handle"]
        self.assertInvalid(missing_handle)

        malformed_handle = _minimal_profile_ir()
        malformed_handle["layouts"][0]["block_table_record_handle"] = 31
        self.assertInvalid(malformed_handle)

        no_model = _minimal_profile_ir()
        no_model["layouts"][0]["name"] = "Layout1"
        self.assertInvalid(no_model)

    def test_profile_semantic_gate_requires_exactly_one_model_row(self):
        import ir_builder
        duplicate = _minimal_profile_ir()
        duplicate["layouts"].append({
            "name": "Model",
            "block_table_record_handle": "2F",
        })
        # Draft-07 has contains but no maxContains. The schema proves at least
        # one Model row; the public semantic gate proves exact cardinality.
        self.assertValid(duplicate)
        ok, method, errors = ir_builder.validate_ir(duplicate)
        self.assertFalse(ok)
        self.assertEqual(method, "jsonschema")
        self.assertTrue(any(
            "layouts must contain exactly one Model row" in error
            for error in errors
        ))

    def test_profile_requires_diagnostic_type_inventory(self):
        missing = _minimal_profile_ir()
        del missing["diagnostics"]["entities_by_type"]
        self.assertInvalid(missing)

        for invalid_value in ([], {"LINE": -1}, {"LINE": "1"}):
            malformed = _minimal_profile_ir()
            malformed["diagnostics"]["entities_by_type"] = invalid_value
            with self.subTest(invalid_value=invalid_value):
                self.assertInvalid(malformed)

    def test_profile_requires_coverage_envelope_fields(self):
        cases = (
            ("realized_entity_count", "0"),
            ("match", "true"),
            ("proxy_or_undecoded_count", -1),
        )
        for field, invalid_value in cases:
            missing = _minimal_profile_ir()
            del missing["diagnostics"]["coverage"][field]
            with self.subTest(field=field, case="missing"):
                self.assertInvalid(missing)

            malformed = _minimal_profile_ir()
            malformed["diagnostics"]["coverage"][field] = invalid_value
            with self.subTest(field=field, case="malformed"):
                self.assertInvalid(malformed)

        honest_blocker = _minimal_profile_ir()
        honest_blocker["diagnostics"]["coverage"]["match"] = False
        honest_blocker["diagnostics"]["coverage"][
            "proxy_or_undecoded_count"] = 2
        self.assertValid(honest_blocker)

    def test_profile_requires_proxy_object_section_status(self):
        missing = _minimal_profile_ir()
        del missing["diagnostics"]["coverage"]["section_status"][
            "proxy_objects"]
        self.assertInvalid(missing)

        malformed = _minimal_profile_ir()
        malformed["diagnostics"]["coverage"]["section_status"][
            "proxy_objects"] = "unknown"
        self.assertInvalid(malformed)

        honest_blocker = _minimal_profile_ir()
        honest_blocker["diagnostics"]["coverage"]["section_status"][
            "proxy_objects"] = "partial"
        self.assertValid(honest_blocker)

    def test_profile_pins_ir_version_and_coverage_level(self):
        for field, invalid_value in (
                ("ir_version", "1.2.0"),
                ("coverage_level", "partial")):
            malformed = _minimal_profile_ir()
            malformed[field] = invalid_value
            with self.subTest(field=field):
                self.assertInvalid(malformed)

    def test_profile_requires_complete_scene_envelope_and_btr_definition_headers(self):
        import ir_builder
        for root_key in (
                "ir_version", "coverage_level", "block_definitions",
                "block_references", "xrefs", "layouts"):
            malformed = _minimal_profile_ir()
            del malformed[root_key]
            self.assertInvalid(malformed)

        missing_btrs = _minimal_profile_ir()
        del missing_btrs["symbol_tables"]["block_table_records"]
        self.assertInvalid(missing_btrs)

        built = ir_builder.build_ir_from_database_graph(
            _native_profile_graph(), _SOURCE_META)
        for required_field in (
                "handle", "name", "is_layout", "is_anonymous", "is_xref",
                "origin", "entity_count"):
            malformed = copy.deepcopy(built)
            del malformed["symbol_tables"]["block_table_records"][0][required_field]
            self.assertInvalid(malformed)
        for required_field in ("handle", "name", "origin", "entity_count", "def_entities"):
            malformed = copy.deepcopy(built)
            del malformed["block_definitions"][0][required_field]
            self.assertInvalid(malformed)

    def test_planar_and_insert_profile_semantics_validate(self):
        arc = _entity(
            "20", "AcDbArc", "ARC", "arc",
            {
                "center": [0.0, 0.0, 0.0],
                "radius": 1.0,
                "start_angle": 0.0,
                "end_angle": 1.0,
                "normal": [0.0, 0.0, 1.0],
                "coordinates_frame": "immediate_owner",
                "plane_basis_owner": copy.deepcopy(_PLANE),
                "legacy_polyline_type": None,
            },
        )
        insert = _entity(
            "21", "AcDbBlockReference", "INSERT", "block_reference",
            {
                "block_name": "B",
                "block_record_handle": "A0",
                "position": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
                "rotation": 0.0,
                "normal": [0.0, 0.0, 1.0],
                "definition_to_owner_transform": list(_IDENTITY_4X4),
                "transform_convention": _TRANSFORM_CONVENTION,
                "instance_semantics": {
                    "mode": "STATIC_SINGLE",
                    "row_count": 1,
                    "column_count": 1,
                    "row_spacing": 0.0,
                    "column_spacing": 0.0,
                    "dynamic_evaluated_btr_handle": None,
                    "xclip": "NONE",
                    "xref_source_sha256": None,
                },
            },
        )
        line = _entity(
            "22", "AcDbLine", "LINE", "line",
            {"start": [0.0, 0.0, 0.0], "end": [1.0, 2.0, 3.0]},
        )
        self.assertValid(_minimal_profile_ir(entities=[arc, insert, line]))

        missing_top_target = copy.deepcopy(insert)
        del missing_top_target["block_record_handle"]
        self.assertInvalid(_minimal_profile_ir(entities=[missing_top_target]))

        wrong_insert_kind = copy.deepcopy(insert)
        wrong_insert_kind["geometry"]["kind"] = "line"
        self.assertInvalid(_minimal_profile_ir(entities=[wrong_insert_kind]))
        wrong_insert_dxf = copy.deepcopy(insert)
        wrong_insert_dxf["dxf_name"] = "OTHER"
        self.assertInvalid(_minimal_profile_ir(entities=[wrong_insert_dxf]))

        missing_explicit_null = copy.deepcopy(insert)
        del missing_explicit_null["geometry"]["instance_semantics"][
            "dynamic_evaluated_btr_handle"]
        self.assertInvalid(_minimal_profile_ir(entities=[missing_explicit_null]))

        for audit_field in ("position", "scale", "rotation", "normal"):
            missing_audit = copy.deepcopy(insert)
            del missing_audit["geometry"][audit_field]
            self.assertInvalid(_minimal_profile_ir(entities=[missing_audit]))

        missing_plane = copy.deepcopy(arc)
        del missing_plane["geometry"]["plane_basis_owner"]
        self.assertInvalid(_minimal_profile_ir(entities=[missing_plane]))

    def test_profile_requires_structural_fields_for_supported_primitives(self):
        plane_fields = {
            "coordinates_frame": "immediate_owner",
            "plane_basis_owner": copy.deepcopy(_PLANE),
            "legacy_polyline_type": None,
        }
        cases = [
            (
                _entity("40", "AcDbLine", "LINE", "line", {
                    "start": [0.0, 0.0, 0.0], "end": [1.0, 1.0, 1.0],
                }),
                ("start", "end"),
            ),
            (
                _entity("41", "AcDbArc", "ARC", "arc", {
                    **plane_fields, "center": [0.0, 0.0, 0.0], "radius": 1.0,
                    "start_angle": 0.0, "end_angle": 1.0,
                    "normal": [0.0, 0.0, 1.0],
                }),
                ("center", "radius", "start_angle", "end_angle", "normal"),
            ),
            (
                _entity("42", "AcDbCircle", "CIRCLE", "circle", {
                    **plane_fields, "center": [0.0, 0.0, 0.0], "radius": 1.0,
                    "normal": [0.0, 0.0, 1.0],
                }),
                ("center", "radius", "normal"),
            ),
            (
                _entity("43", "AcDbPolyline", "LWPOLYLINE", "lwpolyline", {
                    **plane_fields, "closed": False, "vertex_count": 0,
                    "vertices": [], "elevation": 0.0,
                    "normal": [0.0, 0.0, 1.0],
                }),
                ("closed", "vertex_count", "vertices", "elevation", "normal"),
            ),
        ]
        for entity, required_fields in cases:
            self.assertValid(_minimal_profile_ir(entities=[entity]))
            for required_field in required_fields:
                malformed = copy.deepcopy(entity)
                del malformed["geometry"][required_field]
                self.assertInvalid(_minimal_profile_ir(entities=[malformed]))

    def test_legacy_2d_polyline_requires_objectarx_enum_name(self):
        polyline = _entity(
            "30", "AcDb2dPolyline", "POLYLINE", "polyline",
            {
                "vertex_count": 0,
                "vertices": [],
                "closed": False,
                "elevation": 0.0,
                "normal": [0.0, 0.0, 1.0],
                "coordinates_frame": "immediate_owner",
                "plane_basis_owner": copy.deepcopy(_PLANE),
                "legacy_polyline_type": "k2dSimplePoly",
            },
        )
        self.assertValid(_minimal_profile_ir(entities=[polyline]))
        for required_field in ("closed", "vertex_count", "vertices", "elevation", "normal"):
            malformed = copy.deepcopy(polyline)
            del malformed["geometry"][required_field]
            self.assertInvalid(_minimal_profile_ir(entities=[malformed]))
        polyline["geometry"]["legacy_polyline_type"] = None
        self.assertInvalid(_minimal_profile_ir(entities=[polyline]))


if __name__ == "__main__":
    unittest.main()
