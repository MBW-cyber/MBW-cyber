from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from jsonschema.validators import Draft202012Validator

SPEC_PATH = Path(__file__).resolve().parents[1] / "SPEC.md"

EXPECTED_SCHEMA_IDS = {
    "mbw-cyber/prompt_payload",
    "mbw-cyber/experiment_spec",
    "mbw-cyber/scene_spec",
    "mbw-cyber/sim_spec",
    "mbw-cyber/assets_manifest",
    "mbw-cyber/compiled_sim",
    "mbw-cyber/scene_manifest",
    "mbw-cyber/trajectory",
    "mbw-cyber/metrics",
    "mbw-cyber/replay",
    "mbw-cyber/run_summary",
    "mbw-cyber/experiment_matrix",
}


def extract_json_blocks(text: str) -> list[str]:
    return re.findall(r"^```json\n(.*?)^```", text, flags=re.DOTALL | re.MULTILINE)


def spec_blocks() -> list[str]:
    return extract_json_blocks(SPEC_PATH.read_text(encoding="utf-8"))


@pytest.mark.parametrize("block_index", range(len(EXPECTED_SCHEMA_IDS)))
def test_json_block_is_valid_schema(block_index: int) -> None:
    blocks = spec_blocks()
    assert block_index < len(blocks), "fewer json blocks in SPEC.md than expected schemas"

    schema = json.loads(blocks[block_index])
    Draft202012Validator.check_schema(schema)

    assert schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema"
    assert str(schema.get("$id", "")).startswith("mbw-cyber/")


def test_all_expected_schemas_present_exactly_once() -> None:
    ids = [json.loads(block).get("$id") for block in spec_blocks()]
    assert sorted(ids) == sorted(EXPECTED_SCHEMA_IDS)
