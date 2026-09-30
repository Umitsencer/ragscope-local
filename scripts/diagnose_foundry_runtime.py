"""Phase-level diagnostics using fixed synthetic inputs; never download models.

Reports exclude prompts, completions, paths and native exception messages.
Native information logs remain in ignored data/local_cache, not the report.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from audit_sources import ROOT
from demo_local_extractive import select_evidence
from demo_local_rag import require_cached_chat_model

from ragscope.foundry import complete_chat, sdk_version


class Trace:
    def __init__(self, stream):
        self.stream = stream
        self.started = time.perf_counter()

    def emit(self, event, **fields):
        row = {
            "event": event,
            "wall_seconds": round(time.perf_counter() - self.started, 3),
            **fields,
        }
        self.stream.write(json.dumps(row) + "\n")
        self.stream.flush()
        print(event, fields.get("phase", ""), flush=True)

    def call(self, phase, function, **fields):
        started = time.perf_counter()
        cpu = sum(os.times()[:2])
        self.emit("start", phase=phase, **fields)
        try:
            result = function()
        except Exception as error:
            self.emit(
                "error",
                phase=phase,
                error_type=type(error).__name__,
                native_cancelled="cancel" in str(error).lower(),
                elapsed_seconds=round(time.perf_counter() - started, 3),
            )
            raise
        self.emit(
            "end",
            phase=phase,
            elapsed_seconds=round(time.perf_counter() - started, 3),
            process_cpu_seconds=round(sum(os.times()[:2]) - cpu, 3),
        )
        return result


class RuntimeProbe:
    def __init__(self, trace, invoke=complete_chat):
        self.trace, self.invoke = trace, invoke
        self.calls = 0

    def __call__(self, model, messages, **options):
        self.calls += 1
        phase = f"completion_{self.calls}"
        payload = json.dumps(messages, ensure_ascii=False).encode("utf-8")
        return self.trace.call(
            phase,
            lambda: self.invoke(model, messages, **options),
            input_bytes=len(payload),
            input_sha256=hashlib.sha256(payload).hexdigest(),
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=("minimal", "phishing_saved"), required=True)
    parser.add_argument("--streaming", action="store_true")
    parser.add_argument(
        "--model-cache", type=Path, help="Optional existing cache; no model downloads"
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.streaming:
        parser.error("SDK 2.x diagnostic uses the supported non-streaming Session API")
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "data/acceptance").resolve()):
        parser.error("Output must be under data/acceptance")
    logs = ROOT / "data/local_cache/runtime_diagnostics" / output.stem
    logs.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        trace = Trace(stream)
        trace.emit(
            "configuration",
            scenario=args.scenario,
            streaming=False,
            sdk=sdk_version(),
            application_sha256=hashlib.sha256(
                (ROOT / "scripts/demo_local_extractive.py").read_bytes()
            ).hexdigest(),
            diagnostic_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        )
        from foundry_local_sdk import Configuration, FoundryLocalManager
        from foundry_local_sdk.logging_helper import LogLevel

        try:
            trace.call(
                "initialize",
                lambda: FoundryLocalManager.initialize(
                    Configuration(
                        app_name="ragscope_local_demo",
                        app_data_dir=os.environ.get("RAGSCOPE_FOUNDRY_APP_DATA_DIR"),
                        model_cache_dir=str(args.model_cache.resolve())
                        if args.model_cache
                        else None,
                        logs_dir=str(logs),
                        log_level=LogLevel.INFORMATION,
                    )
                ),
            )
            raw = trace.call(
                "catalog",
                lambda: require_cached_chat_model(
                    FoundryLocalManager.instance, "Phi-4-mini-instruct-generic-cpu:5"
                ),
            )
            probe = RuntimeProbe(trace)
            if args.scenario == "minimal":
                try:
                    trace.call("load", raw.load)
                    response = probe(
                        raw,
                        [{"role": "user", "content": 'Return only this JSON: {"selected":[]}'}],
                        max_output_tokens=96,
                        temperature=0.0,
                    )
                    choice = response.choices[0]
                    trace.emit(
                        "result",
                        finish_reason=choice.finish_reason,
                        expected_json=json.loads(choice.message.content) == {"selected": []},
                    )
                finally:
                    if raw.is_loaded:
                        trace.call("unload", raw.unload)
            else:
                record = json.loads(
                    (ROOT / "data/acceptance/2026-09-28-deployment-final/case-02.json").read_text(
                        encoding="utf-8"
                    )
                )
                corpus = ROOT / "data/derived/mitre_definition_corpus.jsonl"
                if (
                    record["output"]["corpus_sha256"]
                    != hashlib.sha256(corpus.read_bytes()).hexdigest()
                ):
                    raise ValueError("Saved evidence corpus mismatch")
                cases = json.loads(
                    (ROOT / "data/acceptance/cases.json").read_text(encoding="utf-8")
                )["cases"]
                query = next(c["query"] for c in cases if c["id"] == "phishing")
                result = select_evidence(
                    raw, query, record["output"]["evidence_cards"], chat_complete=probe
                )
                trace.emit(
                    "result",
                    status=result["status"],
                    quote_count=len(result["quotes"]),
                    source="saved_context_no_retrieval",
                )
        except Exception as error:
            trace.emit("failed", error_type=type(error).__name__)
            return 1
        trace.emit("completed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
