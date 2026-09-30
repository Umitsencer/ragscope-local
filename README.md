# RAGScope Local

**Evidence-first, on-device MITRE ATT&CK retrieval with Microsoft Foundry Local.**

RAGScope Local is a local RAG research and education project that retrieves relevant MITRE ATT&CK definitions, asks a local language model to select evidence spans, and renders only text that can be verified against the source by offset and SHA-256. When the available evidence is insufficient, the application abstains instead of producing a free-form incident claim.

> **Scope:** This repository is an educational prototype and evaluation lab. It is not a SOC decision system, incident-confirmation service, legal opinion, or production security control.

## At a glance

| Item | Verified configuration |
|---|---|
| Runtime | Microsoft Foundry Local SDK `2.0.1`, in-process local inference |
| Retrieval model | `qwen3-embedding-0.6b-generic-cpu:1` |
| Evidence-selection model | `Phi-4-mini-instruct-generic-cpu:5` |
| Knowledge base | 697 active MITRE Enterprise ATT&CK 19.2 technique definitions |
| Controlled benchmark | 17,044 procedure queries; source-grouped train/dev/test split |
| Validated environment | Windows, Python 3.11.9, CPU |
| Current automated checks | 74 tests plus lint, format, compile, link/hash and dependency checks |

## Why this project exists

Many RAG demonstrations stop after returning a plausible answer with citations. RAGScope Local focuses on the harder boundary between a retrieved document and a claim that may safely be shown:

- procedure text is kept out of the retrieval corpus to prevent direct benchmark leakage;
- sparse, dense, hybrid and sibling-aware retrieval variants are evaluated under one frozen protocol;
- the language model selects immutable evidence IDs instead of authoring the displayed prose;
- source offsets and hashes are checked before any quotation is rendered;
- ambiguous, out-of-domain and instruction-injection cases can terminate with abstention.

The project does **not** claim a new embedding model, a new tokenizer, or universal retrieval superiority. Negative and inconclusive results remain part of the evaluation record.

## How it works

```text
User query
   │
   ▼
Input and resource validation
   │
   ▼
Foundry Local embedding ──► dense retrieval ──► ATT&CK evidence cards
                                                   │
                                                   ▼
                                   immutable sentence-span candidates
                                                   │
                                                   ▼
                               Phi-4-mini selects span IDs only
                                                   │
                                                   ▼
                         schema + scope + offset + SHA-256 validation
                                      │                     │
                                      ▼                     ▼
                              verified quotation       abstention/rejection
```

The local model output never becomes executable input and cannot supply the prose displayed to the user. A review pass may remove a proposed span, but it cannot introduce a span that was not retrieved and proposed. See [Architecture](docs/ARCHITECTURE.md) and [Security Policy](SECURITY.md) for the trust boundaries.

## Key capabilities

- **Local-first inference:** embedding and evidence selection run through Foundry Local on the target device.
- **Traceable evidence:** every displayed quotation carries its ATT&CK ID, source offsets and source hash.
- **Fail-closed runtime adapter:** wrong model tasks, malformed chat requests, incomplete embedding batches and dimension drift are rejected.
- **Controlled retrieval evaluation:** BM25, Foundry dense retrieval, dev-selected RRF and SAGE ablations use recorded inputs and manifests.
- **Reproducible provenance:** source commit IDs, raw-file hashes, corpus manifests and benchmark manifests are versioned.
- **Security-aware defaults:** bounded queries, chat context, output tokens, embedding batches and diagnostic logging.

## Prerequisites

- Windows 10/11
- Python `3.11` (`>=3.11,<3.12`)
- A working Microsoft Foundry Local runtime
- Cached model variants:
  - `qwen3-embedding-0.6b-generic-cpu:1`
  - `Phi-4-mini-instruct-generic-cpu:5` for the extractive demo

The demo does not silently download a model or fall back to a cloud service. Model weights, raw third-party datasets, embedding caches, virtual environments, credentials and private conversations are intentionally excluded from the repository.

## Installation

Run the following commands from the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python -m pip install -e .
python -m pip check
```

`data/acceptance/requirements-windows-py311.txt` records the transitive versions observed in the validated Windows environment. It is an environment record, not a cross-platform hash-locked dependency file.

## Quick start

Pass a Foundry cache directory that contains `foundry.modelinfo.json` either directly or under `cache/models`:

```powershell
powershell -NoProfile -File scripts/start_demo.ps1 -ModelCache 'D:\foundry-cache'
```

The launcher prompts for a synthetic question. Pressing Enter uses the documented OS Credential Dumping example. To inspect retrieval without running evidence selection:

```powershell
powershell -NoProfile -File scripts/start_demo.ps1 `
  -ModelCache 'D:\foundry-cache' `
  -Mode retrieval
```

Use synthetic or non-sensitive input. Command-line arguments may be visible in shell history or the operating-system process list, and the native runtime's complete logging behavior is not asserted as a privacy guarantee.

## Verified evaluation

The frozen retrieval test split contains 2,626 queries:

| Method | MRR | Hit@1 | Hit@10 | Interpretation |
|---|---:|---:|---:|---|
| BM25 | 0.292483 | 0.177075 | 0.520944 | Sparse baseline |
| Foundry dense | **0.537134** | **0.408225** | **0.793983** | Best measured result in this protocol |
| RRF, `k=10` selected on dev | 0.519792 | 0.383092 | 0.782559 | Did not outperform dense retrieval |

On the controlled sibling-eligible subset (`n=1,627`), SAGE exact-child Hit@1 changed from `0.377382` to `0.385372`. The bootstrap interval for the difference, `[0, 0.015980]`, includes zero; this is not evidence of a proven general improvement.

The current six-case Foundry Local acceptance run completed all child processes successfully:

- PowerShell, Spearphishing Attachment and OS Credential Dumping selected relevant source evidence;
- ambiguous phishing, an out-of-domain request and an instruction-injection request abstained;
- all five displayed quotations passed exact source-offset and SHA-256 verification;
- measured end-to-end CPU time was `48.802–77.829` seconds per case.

These six known synthetic cases are engineering checks, not an independent gold benchmark or a success-rate estimate. See [Evaluation](docs/EVALUATION.md) and the [acceptance review](data/acceptance/REVIEW.md) for the complete claim boundaries.

## Validation

Run the same offline quality gates used by CI:

```powershell
ruff check src scripts tests
ruff format --check src scripts tests
python -B -m compileall -q src scripts tests
python -B -m unittest discover -s tests -v
python -B scripts/check_project.py
python -m pip check
```

GitHub Actions runs these checks on Windows with Python 3.11. Real-model acceptance is intentionally not run in hosted CI because it requires local model assets and the target runtime/hardware.

## Repository structure

```text
.
├── src/ragscope/          # Runtime and security boundary modules
├── scripts/               # Demo, data-build and evaluation entry points
├── tests/                 # Unit, contract and regression tests
├── data/
│   ├── acceptance/        # Current fixed-case runtime evidence
│   ├── audit/             # Source and leakage audits
│   ├── derived/           # Versioned corpus and benchmark artifacts
│   └── evaluation/        # Canonical metric outputs
├── docs/                  # Architecture, evaluation and delivery documents
├── SECURITY.md            # Threat model and disclosure guidance
├── NOTICE.md              # Third-party attribution and data terms
└── pyproject.toml         # Package and quality-tool configuration
```

## Data provenance

The active corpus and controlled benchmark are derived from a pinned MITRE Enterprise ATT&CK 19.2 STIX release. The raw source commit, expected files, SHA-256 values and license notes are recorded in [`data/sources.lock.json`](data/sources.lock.json).

Raw sources are not committed. If they are required for a rebuild:

```powershell
python -B scripts/fetch_pinned_sources.py --download
python -B scripts/fetch_pinned_sources.py
```

The second command performs local hash verification. Review [NOTICE.md](NOTICE.md) before redistributing source or derived artifacts.

## Security model

User input, retrieved text, retrieval ranking and model output are all treated as untrusted. The implementation applies bounded inputs, strict message schemas, model-task checks, embedding response checks, source membership checks and deterministic quote rendering. The system does not execute tools or interpret model output as a command.

These controls do not prove resistance to every prompt-injection technique. Azure AI Content Safety and Prompt Shields are not integrated into this local prototype. Independent red-team testing, multi-user access control and deployment-environment review remain out of scope. Report security findings according to [SECURITY.md](SECURITY.md).

## Documentation

| Document | Purpose |
|---|---|
| [Architecture](docs/ARCHITECTURE.md) | Components, request flow and trust boundaries |
| [Evaluation](docs/EVALUATION.md) | Protocol, metrics and limitations |
| [Project state](docs/PROJECT_STATE.md) | Canonical current status and remaining risks |
| [Delivery guide](docs/DELIVERY.md) | Local demo and short presentation flow |
| [Submission plan](docs/SUBMISSION_PLAN.md) | External GitHub/video submission checklist |
| [Security policy](SECURITY.md) | Threat model and disclosure guidance |
| [Third-party notice](NOTICE.md) | Attribution and data/model licensing boundaries |

## Project status and support

The repository is maintained as a single-user educational project. There is no production support commitment. Reproducible defects should include the operating system, Python version, Foundry Local SDK version, model variant and the failing command—without prompts, credentials or private data.

The [official Foundry Local repository](https://github.com/microsoft/Foundry-Local) and [Foundry Local Python SDK documentation](https://github.com/microsoft/Foundry-Local/tree/main/sdk_v2/python) are the authoritative sources for runtime installation and SDK behavior.

## License and attribution

No repository-level open-source license has been selected; default copyright applies to the project code. A private GitHub submission does not require choosing an open-source license. Select an explicit code license before public reuse or accepting outside contributions.

Third-party data and model licenses remain separate from the project code. Required MITRE ATT&CK attribution and additional dataset notes are preserved in [NOTICE.md](NOTICE.md). This independent educational project is not endorsed by Microsoft or MITRE.
