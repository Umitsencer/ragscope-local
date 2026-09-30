"""Synthetic span and output-contract regression tests."""

import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from demo_local_extractive import (
    candidate_spans,
    enforce_named_scope,
    parse_selection,
    render_selection,
    select_evidence,
)

CARDS = [
    {
        "attack_id": "T0001",
        "name": "Synthetic",
        "definition": "Synthetic source sentence about a blue beacon. Another synthetic sentence is here.",
    }
]


def run_select(model, query, cards):
    return select_evidence(model, query, cards, chat_complete=model.chat_complete)


class ExtractiveTests(unittest.TestCase):
    def test_scope_preserves_explicit_id_and_does_not_match_parent_prefix(self):
        cards = [
            {"attack_id": "T0001", "name": "Synthetic Parent"},
            {"attack_id": "T0001.001", "name": "Synthetic Child"},
        ]
        spans = [{"attack_id": c["attack_id"]} for c in cards]
        scoped, mode = enforce_named_scope("Explain T0001.001", spans, cards)
        self.assertEqual(scoped, [spans[1]])
        self.assertEqual(mode, "explicit_id")
        self.assertEqual(enforce_named_scope("Explain T9999", spans, cards)[0], [])

    def test_named_parent_does_not_authorize_unnamed_child(self):
        cards = [
            {"attack_id": "T0001", "name": "Synthetic Parent"},
            {"attack_id": "T0001.001", "name": "Synthetic Child"},
        ]
        spans = [{"attack_id": c["attack_id"]} for c in cards]
        self.assertEqual(
            enforce_named_scope("Explain synthetic-parent.", spans, cards)[0], [spans[0]]
        )
        self.assertEqual(enforce_named_scope("An unnamed concept", spans, cards)[1], "unresolved")

    def test_ambiguous_selection_is_removed_by_scope_guard(self):
        query = "Explain Synthetic Parent."
        cards = [
            {
                "attack_id": "T0001",
                "name": "Synthetic Parent",
                "definition": "Parent-only synthetic evidence.",
            },
            {
                "attack_id": "T0001.001",
                "name": "Different Child",
                "definition": "Sibling-only synthetic evidence.",
            },
        ]
        quotes = [span for span in candidate_spans(cards) if span["attack_id"] == "T0001.001"]
        scoped, mode = enforce_named_scope(query, quotes, cards)
        self.assertEqual(mode, "explicit_name")
        self.assertEqual(scoped, [])
        model = Mock(id="synthetic-replay", is_loaded=True)
        selected = [q["span_id"] for q in quotes]
        model.chat_complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content=json.dumps({"selected": selected})),
                )
            ]
        )
        replay = run_select(model, query, cards)
        self.assertEqual(replay["status"], "insufficient_evidence")
        self.assertEqual(replay["scope_removed_count"], len(quotes))
        model.chat_complete.assert_called_once()

    def test_runtime_failure_propagates_without_fake_answer(self):
        model = Mock(id="synthetic", is_loaded=True)
        model.chat_complete.side_effect = RuntimeError("Synthetic cancellation")
        with self.assertRaises(RuntimeError):
            run_select(model, "Synthetic question", CARDS)
        model.unload.assert_called_once()

    def test_offsets_roundtrip(self):
        spans = candidate_spans(CARDS)
        for span in spans:
            quote = render_selection([span["span_id"]], spans, CARDS)[0]
            self.assertEqual(quote["quote"], CARDS[0]["definition"][quote["start"] : quote["end"]])
            self.assertTrue(quote["exact_source_match"])

    def test_forged_quote_or_offset_rejected(self):
        spans = candidate_spans(CARDS)
        for change in ({"quote": "An incident was confirmed."}, {"start": -1}, {"end": 9000}):
            with self.assertRaises(ValueError):
                render_selection(["E1"], [{**spans[0], **change}], CARDS)

    def test_strict_selection_and_single_fence(self):
        spans = candidate_spans(CARDS)
        self.assertEqual(parse_selection('{"selected":[]}', spans), [])
        self.assertEqual(parse_selection('```json\n{"selected":["E1"]}\n```', spans), ["E1"])
        for text in (
            '{"selected":["E999"]}',
            '{"selected":["E1","E1"]}',
            '{"selected":[1]}',
            '{"selected":[],"answer":"invented"}',
            '{"selected":[],"selected":["E1"]}',
            'prefix {"selected":[]}',
            '{"selected":["E1","E2","E3"]}',
            "[]",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_selection(text, spans)

    def test_model_output_cannot_supply_displayed_prose(self):
        model = Mock(id="synthetic", is_loaded=True)
        model.chat_complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop", message=SimpleNamespace(content='{"selected":["E1"]}')
                )
            ]
        )
        result = run_select(model, "Synthetic question", CARDS)
        self.assertEqual(result["status"], "evidence_selected")
        self.assertIn(result["quotes"][0]["quote"], CARDS[0]["definition"])
        model.unload.assert_called_once()

    def test_truncation_rejected_and_unloaded(self):
        model = Mock(id="synthetic", is_loaded=True)
        model.chat_complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="length", message=SimpleNamespace(content='{"selected":[]}')
                )
            ]
        )
        self.assertEqual(run_select(model, "question", CARDS)["status"], "rejected_output")
        model.unload.assert_called_once()

    def test_review_can_abstain_without_displaying_proposal(self):
        model = Mock(id="synthetic", is_loaded=True)

        def response(text):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text))
                ]
            )

        model.chat_complete.side_effect = [
            response('{"selected":["E1"]}'),
            response('{"selected":[]}'),
        ]
        result = run_select(model, "Synthetic question", CARDS)
        self.assertEqual(result["status"], "insufficient_evidence")
        self.assertEqual(result["quotes"], [])
        self.assertTrue(result["review_performed"])

    def test_review_cannot_add_unproposed_id(self):
        model = Mock(id="synthetic", is_loaded=True)

        def response(text):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text))
                ]
            )

        model.chat_complete.side_effect = [
            response('{"selected":["E1"]}'),
            response('{"selected":["E2"]}'),
        ]
        result = run_select(model, "Synthetic question", CARDS)
        self.assertEqual(result["status"], "rejected_output")
        self.assertEqual(result["rejection_stage"], "review")

    def test_empty_proposal_does_not_invoke_review(self):
        model = Mock(id="synthetic", is_loaded=True)
        model.chat_complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop", message=SimpleNamespace(content='{"selected":[]}')
                )
            ]
        )
        self.assertEqual(
            run_select(model, "Synthetic question", CARDS)["status"], "insufficient_evidence"
        )
        model.chat_complete.assert_called_once()

    def test_proposal_cardinality_is_distinct_from_final_contract(self):
        spans = [{"span_id": f"E{i}"} for i in range(1, 4)]
        text = '{"selected":["E1","E2","E3"]}'
        self.assertEqual(len(parse_selection(text, spans, max_selected=3)), 3)
        with self.assertRaises(ValueError):
            parse_selection(text, spans)

    def test_three_valid_reviewed_spans_have_explicit_display_budget(self):
        cards = [
            {
                "attack_id": "T0001",
                "name": "Synthetic",
                "definition": "First synthetic source sentence. Second synthetic source sentence. Third synthetic source sentence.",
            }
        ]
        model = Mock(id="synthetic", is_loaded=True)
        model.chat_complete.return_value = SimpleNamespace(
            choices=[
                SimpleNamespace(
                    finish_reason="stop",
                    message=SimpleNamespace(content='{"selected":["E1","E2","E3"]}'),
                )
            ]
        )
        result = run_select(model, "Explain Synthetic", cards)
        self.assertEqual(result["status"], "evidence_selected")
        self.assertEqual(result["validated_selection_count"], 3)
        self.assertEqual(result["display_omitted_count"], 1)
        self.assertEqual(len(result["quotes"]), 2)


if __name__ == "__main__":
    unittest.main()
