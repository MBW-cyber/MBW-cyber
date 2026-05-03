from __future__ import annotations

import json
from pathlib import Path

from mbw_cyber.auto_research import CHATGPT_55_SCORING_WEIGHTS, ResearchRequest, rank_cars, run_auto_research


def test_rank_cars_returns_sorted_candidates() -> None:
    request = ResearchRequest(
        budget_eur=50000,
        target_range_km=500,
        min_cargo_l=450,
        annual_km=18000,
        preferred_powertrain="ev",
        prefer_segment="suv",
        top_k=5,
    )

    ranking = rank_cars(request)
    assert len(ranking) == 5
    assert ranking[0]["score"] >= ranking[-1]["score"]
    assert all("car" in item and "score_breakdown" in item and "labels" in item for item in ranking)


def test_run_auto_research_writes_outputs(tmp_path: Path) -> None:
    payload = {
        "budget_eur": 48000,
        "target_range_km": 450,
        "min_cargo_l": 430,
        "annual_km": 22000,
        "preferred_powertrain": "ev",
        "prefer_segment": "any",
        "top_k": 3,
    }

    output = run_auto_research(payload, tmp_path)
    assert Path(output["report_path"]).exists()
    assert Path(output["result_path"]).exists()

    result = json.loads(Path(output["result_path"]).read_text(encoding="utf-8"))
    assert result["engine"] == "chatgpt-5.5-style-local-mvp"
    assert result["weights"] == CHATGPT_55_SCORING_WEIGHTS
    assert len(result["ranking"]) == 3
    assert result["ranking"][0]["score"] >= result["ranking"][-1]["score"]
