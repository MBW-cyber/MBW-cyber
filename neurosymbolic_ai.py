#!/usr/bin/env python3
"""
Direct bruikbare Neurosymbolic AI (zonder externe dependencies).

Neuraal deel:
- Lichtgewicht intent-scorer op basis van gewogen token-features

Symbolisch deel:
- Verklaarbare IF-THEN regels
- Prioriteiten en constraints

Gebruik:
    python neurosymbolic_ai.py "Ik heb koorts en hoofdpijn"
    python neurosymbolic_ai.py --interactive
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class SymbolicRule:
    name: str
    condition: Callable[[str, set[str]], bool]
    recommendation: str
    confidence_boost: float
    priority: int


class NeuralScorer:
    """Simpel 'neuraal' scoringsmodel met feature-gewichten per intent."""

    def __init__(self) -> None:
        self.intent_weights: dict[str, dict[str, float]] = {
            "gezondheid": {
                "koorts": 1.5,
                "pijn": 1.1,
                "hoofdpijn": 1.4,
                "ziek": 1.3,
                "verkouden": 1.2,
                "misselijk": 1.4,
                "arts": 1.0,
            },
            "productiviteit": {
                "planning": 1.4,
                "focus": 1.5,
                "deadline": 1.4,
                "taak": 1.2,
                "werk": 1.0,
                "prioriteit": 1.5,
            },
            "leren": {
                "leren": 1.5,
                "studie": 1.4,
                "oefenen": 1.3,
                "samenvatting": 1.4,
                "uitleg": 1.2,
                "begrijpen": 1.3,
            },
            "financien": {
                "budget": 1.6,
                "geld": 1.3,
                "besparen": 1.4,
                "uitgaven": 1.4,
                "investeren": 1.2,
            },
        }

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

    def tokenize(self, text: str) -> set[str]:
        text = self._normalize(text)
        tokens = re.findall(r"[a-zà-ÿ0-9]+", text)
        return set(tokens)

    def score_intents(self, text: str) -> dict[str, float]:
        tokens = self.tokenize(text)
        scores: dict[str, float] = {}
        for intent, weights in self.intent_weights.items():
            score = 0.0
            for token in tokens:
                score += weights.get(token, 0.0)
            scores[intent] = score
        return scores


class NeuroSymbolicAI:
    def __init__(self) -> None:
        self.neural = NeuralScorer()
        self.rules = self._build_rules()

    def _build_rules(self) -> list[SymbolicRule]:
        return [
            SymbolicRule(
                name="medisch_urgent",
                condition=lambda text, t: (
                    ("ernstige" in t and "pijn" in t)
                    or ("benauwd" in t)
                    or ("bloed" in t and "braken" in t)
                ),
                recommendation=(
                    "Dit klinkt mogelijk urgent. Neem direct contact op met "
                    "huisartsenpost of 112 bij acute nood."
                ),
                confidence_boost=0.45,
                priority=100,
            ),
            SymbolicRule(
                name="gezondheid_basis",
                condition=lambda _text, t: ("koorts" in t) or ("ziek" in t),
                recommendation=(
                    "Rust, drink voldoende water en monitor symptomen. "
                    "Neem contact op met een arts als klachten verergeren."
                ),
                confidence_boost=0.25,
                priority=60,
            ),
            SymbolicRule(
                name="focus_plan",
                condition=lambda _text, t: ("deadline" in t) or ("focus" in t),
                recommendation=(
                    "Gebruik een 3-blokken plan: 1) topprioriteit 2) medium "
                    "3) quick wins, met 25 minuten focus per blok."
                ),
                confidence_boost=0.30,
                priority=50,
            ),
            SymbolicRule(
                name="studie_hulp",
                condition=lambda text, t: ("leren" in t) or ("uitleg" in t) or ("hoe" in text.lower()),
                recommendation=(
                    "Gebruik actief leren: leg het onderwerp uit in je eigen woorden, "
                    "maak 5 oefenvragen en test jezelf zonder aantekeningen."
                ),
                confidence_boost=0.22,
                priority=40,
            ),
            SymbolicRule(
                name="budget_hulp",
                condition=lambda _text, t: ("budget" in t) or ("uitgaven" in t),
                recommendation=(
                    "Start met een 50/30/20-budget en check wekelijks je uitgaven "
                    "tegen je geplande categorieen."
                ),
                confidence_boost=0.28,
                priority=45,
            ),
        ]

    def infer(self, user_input: str) -> dict[str, object]:
        tokens = self.neural.tokenize(user_input)
        intent_scores = self.neural.score_intents(user_input)
        best_intent = max(intent_scores, key=intent_scores.get)
        best_score = intent_scores[best_intent]

        fired_rules = [r for r in self.rules if r.condition(user_input, tokens)]
        fired_rules.sort(key=lambda r: r.priority, reverse=True)

        confidence = min(0.2 + (best_score / 4.0), 0.85)
        for rule in fired_rules:
            confidence = min(confidence + rule.confidence_boost, 0.99)

        if fired_rules:
            recommendation = fired_rules[0].recommendation
        else:
            recommendation = self.default_recommendation(best_intent)

        explanation = {
            "intent": best_intent,
            "intent_scores": intent_scores,
            "fired_rules": [r.name for r in fired_rules],
            "confidence": round(confidence, 2),
            "recommendation": recommendation,
        }
        return explanation

    @staticmethod
    def default_recommendation(intent: str) -> str:
        fallback = {
            "gezondheid": "Beschrijf je klachten met duur en ernst; ik help je met een veilig stappenplan.",
            "productiviteit": "Noem je doel en deadline; ik maak een compact dagplan voor je.",
            "leren": "Noem het onderwerp en niveau; ik geef een leerroute met oefeningen.",
            "financien": "Noem je inkomsten en vaste lasten; ik maak een startbudget.",
        }
        return fallback.get(intent, "Vertel wat meer context, dan geef ik gericht advies.")


def format_output(result: dict[str, object]) -> str:
    lines = [
        "\n=== NeuroSymbolic AI Resultaat ===",
        f"Intent: {result['intent']}",
        f"Confidence: {result['confidence']}",
        f"Actieve regels: {', '.join(result['fired_rules']) if result['fired_rules'] else 'geen'}",
        f"Advies: {result['recommendation']}",
        "Intent-scores:",
    ]
    for intent, score in sorted(result["intent_scores"].items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  - {intent}: {score:.2f}")
    return "\n".join(lines)


def run_interactive() -> None:
    ai = NeuroSymbolicAI()
    print("NeuroSymbolic AI gestart. Typ 'stop' om af te sluiten.\n")
    while True:
        user_input = input("Jij> ").strip()
        if user_input.lower() in {"stop", "quit", "exit"}:
            print("Tot ziens!")
            break
        if not user_input:
            print("Geef een vraag of situatie op.")
            continue
        result = ai.infer(user_input)
        print(format_output(result))
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Direct bruikbare Neurosymbolic AI.")
    parser.add_argument("text", nargs="*", help="Vraag of situatie")
    parser.add_argument("--interactive", action="store_true", help="Start interactieve modus")
    args = parser.parse_args()

    if args.interactive:
        run_interactive()
        return

    if not args.text:
        parser.print_help()
        return

    ai = NeuroSymbolicAI()
    result = ai.infer(" ".join(args.text))
    print(format_output(result))


if __name__ == "__main__":
    main()
