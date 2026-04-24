from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any


@dataclass(frozen=True)
class CarOption:
    model: str
    powertrain: str
    msrp_eur: int
    wlpt_range_km: int
    safety_score: float
    cargo_l: int
    service_cost_year_eur: int
    reliability_score: float
    warranty_years: int


@dataclass(frozen=True)
class ResearchRequest:
    budget_eur: int
    target_range_km: int
    min_cargo_l: int
    annual_km: int
    preferred_powertrain: str

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "ResearchRequest":
        return cls(
            budget_eur=int(payload.get("budget_eur", 45000)),
            target_range_km=int(payload.get("target_range_km", 450)),
            min_cargo_l=int(payload.get("min_cargo_l", 400)),
            annual_km=int(payload.get("annual_km", 18000)),
            preferred_powertrain=str(payload.get("preferred_powertrain", "ev")).lower(),
        )


CAR_DATABASE = [
    CarOption("Tesla Model 3 RWD", "ev", 41990, 513, 4.7, 561, 410, 4.2, 4),
    CarOption("Hyundai IONIQ 5 77kWh", "ev", 46995, 507, 4.8, 527, 430, 4.4, 5),
    CarOption("Kia EV6 Air", "ev", 45895, 528, 4.8, 490, 420, 4.3, 7),
    CarOption("Skoda Enyaq 85", "ev", 49990, 565, 4.9, 585, 390, 4.5, 2),
    CarOption("Toyota Corolla Touring Hybrid", "hybrid", 36995, 900, 4.9, 596, 360, 4.8, 10),
    CarOption("Volvo XC40 Recharge Single Motor", "ev", 52995, 480, 4.9, 452, 470, 4.2, 3),
    CarOption("MG4 Long Range", "ev", 36985, 450, 4.4, 363, 350, 4.0, 7),
    CarOption("BMW i4 eDrive35", "ev", 57900, 483, 4.8, 470, 520, 4.1, 2),
]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _score_car(car: CarOption, request: ResearchRequest) -> tuple[float, dict[str, float]]:
    budget_fit = _clamp01((request.budget_eur - car.msrp_eur + 12000) / 24000)
    range_fit = _clamp01(car.wlpt_range_km / max(request.target_range_km, 1))
    cargo_fit = _clamp01(car.cargo_l / max(request.min_cargo_l, 1))
    safety_fit = _clamp01(car.safety_score / 5)
    reliability_fit = _clamp01(car.reliability_score / 5)

    preferred = request.preferred_powertrain
    powertrain_fit = 1.0 if preferred in {"any", car.powertrain} else 0.45

    yearly_energy_cost = 0.04 * request.annual_km if car.powertrain == "ev" else 0.07 * request.annual_km
    yearly_total_cost = yearly_energy_cost + car.service_cost_year_eur
    cost_fit = _clamp01(1 - (yearly_total_cost / 2600))

    score_breakdown = {
        "budget_fit": budget_fit,
        "range_fit": range_fit,
        "cargo_fit": cargo_fit,
        "safety_fit": safety_fit,
        "reliability_fit": reliability_fit,
        "powertrain_fit": powertrain_fit,
        "cost_fit": cost_fit,
    }
    weighted_score = (
        budget_fit * 0.22
        + range_fit * 0.22
        + cargo_fit * 0.1
        + safety_fit * 0.16
        + reliability_fit * 0.12
        + powertrain_fit * 0.08
        + cost_fit * 0.1
    )
    return round(weighted_score * 100, 2), score_breakdown


def rank_cars(request: ResearchRequest, limit: int = 5) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for car in CAR_DATABASE:
        score, breakdown = _score_car(car, request)
        ranked.append(
            {
                "score": score,
                "car": asdict(car),
                "score_breakdown": {k: round(v, 3) for k, v in breakdown.items()},
            }
        )

    ranked.sort(key=lambda item: item["score"], reverse=True)
    return ranked[:limit]


def build_report(request: ResearchRequest, ranking: list[dict[str, Any]]) -> str:
    lines = [
        "# AI Auto Research Report",
        "",
        "## Requestprofiel",
        f"- Budget: €{request.budget_eur:,}",
        f"- Gewenste range: {request.target_range_km} km",
        f"- Minimaal bagageruimte: {request.min_cargo_l} liter",
        f"- Jaarlijkse kilometers: {request.annual_km:,}",
        f"- Voorkeur aandrijving: {request.preferred_powertrain}",
        "",
        "## Top aanbevelingen",
    ]

    for index, candidate in enumerate(ranking, start=1):
        car = candidate["car"]
        score = candidate["score"]
        breakdown = candidate["score_breakdown"]
        lines.extend(
            [
                f"### {index}. {car['model']} ({score}/100)",
                f"- Prijs: €{car['msrp_eur']:,}",
                f"- Range (WLTP): {car['wlpt_range_km']} km",
                f"- Kofferbak: {car['cargo_l']} liter",
                f"- Veiligheid: {car['safety_score']}/5 | Betrouwbaarheid: {car['reliability_score']}/5",
                (
                    "- Match breakdown: "
                    f"budget {breakdown['budget_fit']}, range {breakdown['range_fit']}, "
                    f"cost {breakdown['cost_fit']}"
                ),
                "",
            ]
        )

    avg_score = round(mean([item["score"] for item in ranking]), 2) if ranking else 0
    lines.extend(
        [
            "## Volgende stap",
            f"- Gemiddelde kwaliteit van shortlist: {avg_score}/100.",
            "- Plan 2 proefritten: #1 voor ratio, #2 voor comfort/afwerking.",
            "- Vraag dealer-offertes op met verzekering + levertijd en herhaal ranking met echte offertes.",
        ]
    )
    return "\n".join(lines)


def run_auto_research(payload: dict[str, Any], out_root: Path) -> dict[str, Any]:
    request = ResearchRequest.from_payload(payload)
    ranking = rank_cars(request)
    report = build_report(request, ranking)

    out_root.mkdir(parents=True, exist_ok=True)
    report_path = out_root / "auto_research_report.md"
    result_path = out_root / "auto_research_result.json"

    report_path.write_text(report, encoding="utf-8")
    result_path.write_text(
        json.dumps(
            {
                "request": asdict(request),
                "ranking": ranking,
                "files": {
                    "report": str(report_path),
                    "result": str(result_path),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    return {
        "request": asdict(request),
        "ranking": ranking,
        "report_path": str(report_path),
        "result_path": str(result_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Simple AI auto research MVP")
    parser.add_argument("--input", required=True, help="Path to input request JSON")
    parser.add_argument("--out", default="runs/auto_research", help="Output directory")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output = run_auto_research(payload, Path(args.out))

    print(f"Top advies: {output['ranking'][0]['car']['model']} ({output['ranking'][0]['score']}/100)")
    print(f"Report: {output['report_path']}")
    print(f"Data: {output['result_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
