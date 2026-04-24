from __future__ import annotations

import json
from pathlib import Path

from mbw_cyber.auto_research import ResearchRequest, rank_cars, run_auto_research


def test_rank_cars_returns_sorted_candidates() -> None:
    request = ResearchRequest(
        budget_eur=50000,
        target_range_km=500,
        min_cargo_l=450,
        annual_km=18000,
        preferred_powertrain="ev",
    )

    ranking = rank_cars(request, limit=5)
    assert len(ranking) == 5
    assert ranking[0]["score"] >= ranking[-1]["score"]
    assert all("car" in item and "score_breakdown" in item for item in ranking)


def test_run_auto_research_writes_outputs(tmp_path: Path) -> None:
    payload = {
        "budget_eur": 48000,
        "target_range_km": 450,
        "min_cargo_l": 430,
        "annual_km": 22000,
        "preferred_powertrain": "ev",
    }

    output = run_auto_research(payload, tmp_path)
    assert Path(output["report_path"]).exists()
    assert Path(output["result_path"]).exists()

    result = json.loads(Path(output["result_path"]).read_text(encoding="utf-8"))
    assert result["ranking"]
    assert result["ranking"][0]["score"] >= result["ranking"][-1]["score"]
