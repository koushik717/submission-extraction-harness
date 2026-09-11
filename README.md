# Submission Extraction Harness

**Synthetic documents only.** This repository generates its own commercial-property / GL submission PDFs. No real insurance documents, no real insureds, and no PII are used in fixtures or experiments.

This is a **measurement harness**, not a production extraction product. It measures per-field extraction accuracy **and** run-to-run stability, then turns those numbers into a routing policy (auto-post vs human review).

## Headline finding

On the seeded 50-document corpus (10 per difficulty tier) with the offline `local` PDF-text provider:

- **Per-field accuracy ranges from 0.60 to 0.86** (headline aggregate **0.764** — which hides the spread).
- **Three fields flip between identical runs at default temperature** (`loss_history` 0.52, `year_built` 0.26, `named_insured` 0.16) while **temp_0 flip rates are all 0.00**.
- Majority vote recovers the temp_default accuracy gap (+0.017 aggregate).
- By tier: text-backed tiers stay high; **scanned is ~0.02** because the raster PDF has no text layer.

See [`REPORT.md`](REPORT.md) for full tables and charts.

## What surprised me

1. The **headline aggregate (0.76) looked “okay”** until the tier table showed scanned documents near zero — aggregate accuracy is a terrible summary statistic for routing decisions.
2. **temp_0 vs temp_default separation actually works**: zero flips at temperature 0 means the residual temp_default flips are sampling noise (here, deliberate local perturbation), not document ambiguity.
3. **Handwritten blanks hurt only specific fields** (named insured / deductible / year built → 0.60), which is exactly the kind of per-field signal a routing policy needs.

## Hard constraints

- Python 3.11+ (pinned to 3.12 via `.python-version`), `uv`
- All documents synthetic and seeded
- Every LLM call goes through one rate-limited, cost-governed client with a hard spend cap
- Experiment runs are checkpointed under `runs/`
- MIT license

## Quick start

```bash
cp .env.example .env   # add OPENAI_API_KEY / ANTHROPIC_API_KEY for cloud providers
uv sync --all-extras
make corpus            # 50 synthetic PDFs + ground_truth.json
make test              # verifier / normalizer / cost-guard tests
make extract           # single-run sanity on 5 docs (default provider: local)
make stability         # N=5 × {temp_0, temp_default}, checkpointed
make report            # REPORT.md + routing_policy.json + PNGs
```

Cloud providers are used when API keys are present and `--provider openai|anthropic` is passed. Without keys, the harness falls back to `local` (pdftotext + deterministic parsers).

## Layout

```
src/submission_harness/
  schema.py          # Pydantic ground-truth / extraction schema
  corpus/            # seeded generator + five difficulty tiers
  extract/           # agent + OpenAI / Anthropic / local providers
  client/            # rate limit + hard spend cap
  verify/            # normalizers + field-level scorer
  stability/         # flip rate, majority vote, checkpointed runner
  routing/           # auto_post / review / always_human policy
  report/            # REPORT.md + matplotlib charts
configs/             # seeds, spend cap, routing thresholds
tests/               # adversarial normalizer + verifier suite
```

## Spend discipline

Full `N=5` stability sweeps are expensive on cloud APIs. Run a single-pass sanity extract first (`make extract`). The spend cap in `configs/default.yaml` aborts the run when exceeded.

## License

MIT
