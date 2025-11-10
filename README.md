# tervyx-analysis

**Deterministic analysis and visualization of TERVYX protocol outputs.**

## Purpose

This repository analyzes TERVYX outputs (`entry.jsonld`, `simulation.json`, `citations.json`) from the [tervyx](https://github.com/moneypuzzler/tervyx) repository using **LLM-free, deterministic methods**. It generates reports covering:

- **TEL-5 distribution** (Gold/Silver/Bronze/Red/Black tiers)
- **Gate performance** (Φ/R/J/K/L pass/fail rates)
- **J-Oracle statistics** (journal trust scores and BLACK masking)
- **Policy anchor verification** (policy fingerprints, snapshot dates, versions)
- **Label stability analysis** (when multiple snapshots/δ combinations exist)

All final labels are determined by TERVYX's policy-as-code rules (GGP gates + TEL-5 thresholds); this repository **reads and summarizes** those results without LLM intervention.

---

## Repository Structure

```
tervyx-analysis/
├── tervyx/                      # Submodule: upstream source (sparse checkout)
├── scripts/
│   ├── update_submodule.sh      # Pin commit & configure sparse paths
│   ├── ingest.py                # Scan entries → build index.parquet
│   ├── validate_index.py        # Schema/anchor/quality checks
│   ├── build_metrics.py         # Compute TEL-5/gate/J* metrics
│   ├── plot_figures.py          # Generate matplotlib visualizations
│   ├── make_report.py           # Assemble summary.md report
│   └── utils/
│       ├── jsonld_reader.py     # Safe parsers for entry/simulation/citations
│       ├── policy_anchors.py    # Policy fingerprint validation
│       └── shard.py             # Memory-efficient sharding for large datasets
├── reports/
│   ├── figures/                 # .png/.svg visualizations
│   ├── tables/                  # .csv metrics and index files
│   └── summary.md               # Final analysis report
├── Makefile                     # Orchestration targets
├── requirements.txt             # Python dependencies
└── .github/workflows/
    └── analysis.yml             # CI pipeline
```

---

## Quick Start

### 1. Clone and Initialize

```bash
git clone https://github.com/<org>/tervyx-analysis.git
cd tervyx-analysis

# Add tervyx as submodule (if not already present)
git submodule add -b main https://github.com/moneypuzzler/tervyx tervyx

# Pin to specific commit and configure sparse checkout
bash scripts/update_submodule.sh
```

### 2. Set Up Python Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Run Analysis Pipeline

```bash
make all
```

This executes:
1. `update` - Update submodule to pinned commit
2. `ingest` - Parse all entries into `reports/tables/index.parquet`
3. `validate` - Check schema compliance and policy anchors
4. `metrics` - Generate TEL-5/gate/J* statistics
5. `figures` - Create visualization charts
6. `report` - Assemble `reports/summary.md`

---

## Inputs

### From `tervyx/` Submodule (Sparse Checkout)

- **Entry artifacts**: `entries/**/{entry.jsonld, simulation.json, citations.json}`
- **Protocol schemas**: `protocol/schemas/*.json` (ESV, entry, simulation, citations)
- **Journal trust data**: `protocol/journal_trust/*` (snapshot files)
- **Policy configuration**: `policy.yaml` (TEL-5 thresholds, Monte Carlo settings, gate rules)

The sparse checkout includes only these paths to minimize repository size.

---

## Outputs

### `reports/summary.md`

Markdown report with:
- Analysis metadata (commit SHA, policy fingerprint, schema versions)
- TEL-5 tier distribution tables and charts
- Gate statistics (Φ/K monotone invariant violations, J-Oracle patterns)
- Policy anchor verification summary
- Quality checks (schema compliance, duplicate detection)

### `reports/figures/`

- `fig_tel5_hist.png` - TEL-5 tier histogram
- `fig_gate_fail_phi_k.png` - Φ/K failure rates
- `fig_jstar_hist.png` - J-Oracle score distribution
- `fig_policy_anchor_check.png` - Policy version/snapshot consistency

### `reports/tables/`

- `index.parquet` - Parsed entry data (ID, tier, label, P_effect, gates, policy refs)
- `metrics.csv` - Aggregated statistics

---

## Design Principles

### 1. LLM-Free Analysis

Final labels in TERVYX are determined by **deterministic policy rules** (GGP gates + TEL-5 thresholds + REML+Monte Carlo). This repository:
- **Reads** those labels from `entry.jsonld`
- **Aggregates** statistics
- **Visualizes** distributions

LLMs are **not used** to assign, modify, or interpret labels.

### 2. Policy Anchor Verification

Every entry includes:
- `policy_fingerprint` - SHA256 hash of policy configuration
- `policy_refs.tel5_levels.version` - e.g., "1.2.0"
- `policy_refs.monte_carlo.version` - e.g., "1.0.1-reml-grid"
- `policy_refs.journal_trust.snapshot_date` - e.g., "2025-10-05"

The validation script checks:
- All entries use the **same policy fingerprint** (or groups by version if multiple exist)
- Snapshot dates align with `protocol/journal_trust/*` files
- Schema compliance with `protocol/schemas/*.json`

### 3. Safety-Monotone Invariant

**Φ (Natural/Category)** and **K (Safety)** gate failures cannot be overridden by high J-Oracle scores:

> If Φ = FAIL or K = FAIL → TEL-5 tier is automatically **Black**, regardless of P(effect > δ) or J value.

This "monotone invariant" prevents unsafe/impossible claims from passing.

### 4. J-Oracle BLACK Masking

The J-Oracle assigns **BLACK (0.0)** to entries with:
- Predatory journals (Beall's List)
- Retracted studies
- Non-peer-reviewed sources below quality threshold

A J-BLACK result forces the final label to **FAIL** tier (Black).

---

## Sparse Checkout Configuration

To minimize disk usage, only essential paths are checked out from `tervyx/`:

```bash
git sparse-checkout set \
  "entries/*/*/*/*/entry.jsonld" \
  "entries/*/*/*/*/simulation.json" \
  "entries/*/*/*/*/citations.json" \
  "protocol/schemas/*.json" \
  "protocol/journal_trust/*" \
  "policy.yaml"
```

This excludes:
- `engine/` (processing code, not needed for analysis)
- `scripts/` (CLI tools)
- `.github/` (CI workflows)
- Large evidence CSV files (unless explicitly needed)

---

## Makefile Targets

```bash
make update          # Update submodule to pinned commit
make ingest          # Parse entries → index.parquet
make validate        # Check schema/policy compliance
make metrics         # Generate statistics
make figures         # Create visualizations
make report          # Assemble summary.md
make all             # Run full pipeline
make clean           # Remove generated reports
```

---

## CI/CD Pipeline

`.github/workflows/analysis.yml` runs on:
- Manual trigger (`workflow_dispatch`)
- Push to main branch
- Scheduled runs (optional)

**Key features:**
- **Ephemeral runners** - No persistent state; all outputs committed or uploaded as artifacts
- **Sharding support** - Matrix strategy for large entry sets
- **Python 3.11** - Matches TERVYX engine environment
- **Artifact upload** - `reports/` directory preserved for review

---

## Performance and Security

### Memory Protection

- `ingest.py` uses **streaming parsers** (generator-based)
- Large datasets can be **sharded** via `--shard-index`/`--shard-count`
- Parquet format with Snappy compression for efficient storage

### File Integrity

- JSON parsing failures are **logged** but don't halt analysis
- Schema mismatches are **isolated** to error reports
- `policy_fingerprint` cross-checked against `policy.yaml` hash

### Reproducibility

- Submodule pinned to **specific commit SHA**
- Policy anchors verified for **exact version matching**
- Monte Carlo seed (if present in simulation.json) recorded in reports

---

## Key Metrics Explained

### TEL-5 Tiers

Based on **P(effect > δ)** from REML + Monte Carlo simulation (10,000 draws):

| Tier | P(effect > δ) | Label | Notes |
|------|---------------|-------|-------|
| Gold | ≥ 0.80 | PASS | Strong evidence |
| Silver | 0.60 – 0.80 | PASS | Moderate evidence |
| Bronze | 0.40 – 0.60 | AMBER | Weak evidence |
| Red | 0.20 – 0.40 | AMBER | Very weak evidence |
| Black | < 0.20 or Φ/K FAIL | FAIL | Insufficient/unsafe |

### Gate Results

- **Φ (Natural/Category)** - FAIL if physiologically impossible or non-local wearables
- **R (Relevance)** - Semantic routing between claim and category
- **J (Journal Trust)** - Oracle score (0–1) or BLACK for predatory/retracted sources
- **K (Safety)** - Absolute caps for adverse events
- **L (Exaggeration)** - Pattern detection for "cure"/"miracle"/"instant" language

### Policy Fingerprint

SHA256 hash of concatenated policy components:
```
SHA256(tel5_levels || monte_carlo_config || journal_trust_snapshot)
```

Ensures identical inputs → identical outputs (reproducible builds).

---

## Contributing

This is an **analysis-only** repository. To modify TERVYX protocol rules or add entries, contribute to:
- [tervyx](https://github.com/moneypuzzler/tervyx) - Main protocol repository

For analysis improvements:
1. Fork this repository
2. Create feature branch
3. Add tests for new metrics
4. Submit pull request

---

## References

- **TERVYX Protocol**: [https://github.com/moneypuzzler/tervyx](https://github.com/moneypuzzler/tervyx)
- **GGP Gates**: Five-gate validation (Φ/R/J/K/L) as policy-as-code
- **TEL-5 Classification**: Tiered evidence labels based on posterior probability
- **J-Oracle**: Quantitative + qualitative journal trust scoring with BLACK masking
- **DAG Partial Re-evaluation**: Incremental updates when policy changes affect subset of entries

---

## License

MIT License - See LICENSE file for details

---

## Contact

For questions about:
- **This analysis repository**: Open an issue here
- **TERVYX protocol**: See [tervyx repository](https://github.com/moneypuzzler/tervyx/issues)
