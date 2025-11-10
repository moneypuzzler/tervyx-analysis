#!/usr/bin/env python3
"""
Assemble final analysis report (summary.md).

Combines:
- Metadata (commit, policy anchors)
- TEL-5 distribution tables/figures
- Gate statistics
- J-Oracle analysis
- Quality checks
"""

import argparse
import logging
from pathlib import Path
from datetime import datetime
import sys
import subprocess

import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def get_submodule_commit() -> str:
    """Get current tervyx submodule commit SHA."""
    try:
        result = subprocess.run(
            ['git', '-C', 'tervyx', 'rev-parse', 'HEAD'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()[:8]
    except Exception as e:
        logger.warning(f"Could not get submodule commit: {e}")
        return "unknown"


def load_metrics(metrics_dir: Path) -> dict:
    """Load all metric tables."""
    metrics = {}

    files = {
        'tel5': 'tel5_distribution.csv',
        'gates': 'gate_performance.csv',
        'j_oracle': 'j_oracle_distribution.csv',
        'policy': 'policy_anchors.csv',
        'summary': 'metrics.csv'
    }

    for key, filename in files.items():
        filepath = metrics_dir / filename
        if filepath.exists():
            metrics[key] = pd.read_csv(filepath)
        else:
            logger.warning(f"Metrics file not found: {filepath}")
            metrics[key] = None

    return metrics


def generate_report(metrics_dir: Path, figures_dir: Path, output_path: Path):
    """Generate markdown report."""
    logger.info("Generating report...")

    metrics = load_metrics(metrics_dir)
    commit_sha = get_submodule_commit()
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')

    # Build report
    lines = []

    # Header
    lines.append("# TERVYX Analysis Report")
    lines.append("")
    lines.append(f"**Generated:** {timestamp}")
    lines.append(f"**Submodule commit:** `{commit_sha}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")

    if metrics['summary'] is not None:
        summary = metrics['summary'].iloc[0]
        lines.append(f"- **Total entries:** {summary['total_entries']}")
        lines.append(f"- **PASS:** {summary['pass_count']} ({summary['pass_count']/summary['total_entries']*100:.1f}%)")
        lines.append(f"- **AMBER:** {summary['amber_count']} ({summary['amber_count']/summary['total_entries']*100:.1f}%)")
        lines.append(f"- **FAIL:** {summary['fail_count']} ({summary['fail_count']/summary['total_entries']*100:.1f}%)")
        lines.append("")

    # TEL-5 Distribution
    lines.append("## TEL-5 Tier Distribution")
    lines.append("")
    lines.append("TEL-5 tiers are determined by **P(effect > δ)** from REML + Monte Carlo simulation:")
    lines.append("")

    if metrics['tel5'] is not None:
        lines.append(metrics['tel5'].to_markdown(index=False))
        lines.append("")

    if (figures_dir / 'fig_tel5_hist.png').exists():
        lines.append("![TEL-5 Distribution](figures/fig_tel5_hist.png)")
        lines.append("")

    # Gate Performance
    lines.append("## Gate Performance")
    lines.append("")
    lines.append("**Five-gate validation (GGP):**")
    lines.append("")
    lines.append("- **Φ (Natural/Category):** Physiological plausibility check")
    lines.append("- **R (Relevance):** Semantic routing fit")
    lines.append("- **J (Journal Trust):** Oracle score with BLACK masking")
    lines.append("- **K (Safety):** Adverse event caps")
    lines.append("- **L (Exaggeration):** Language pattern detection")
    lines.append("")
    lines.append("**Safety-Monotone Invariant:** Φ-FAIL or K-FAIL forces Black tier (cannot be overridden by high J scores).")
    lines.append("")

    if metrics['gates'] is not None:
        lines.append(metrics['gates'].to_markdown(index=False))
        lines.append("")

    if (figures_dir / 'fig_gate_fail_phi_k.png').exists():
        lines.append("![Gate Performance](figures/fig_gate_fail_phi_k.png)")
        lines.append("")

    # J-Oracle
    lines.append("## J-Oracle Distribution")
    lines.append("")
    lines.append("J-Oracle scores combine quantitative (impact factor, citations) and qualitative (predatory lists, retractions) signals.")
    lines.append("")
    lines.append("**BLACK** indicates predatory journals, retracted studies, or non-peer-reviewed sources below threshold.")
    lines.append("")

    if metrics['j_oracle'] is not None:
        lines.append(metrics['j_oracle'].to_markdown(index=False))
        lines.append("")

    if (figures_dir / 'fig_jstar_hist.png').exists():
        lines.append("![J-Oracle Distribution](figures/fig_jstar_hist.png)")
        lines.append("")

    # Policy Anchors
    lines.append("## Policy Anchor Verification")
    lines.append("")
    lines.append("All entries should be built with consistent policy versions for reproducibility.")
    lines.append("")

    if metrics['policy'] is not None:
        lines.append(metrics['policy'].to_markdown(index=False))
        lines.append("")

    if (figures_dir / 'fig_policy_anchor_check.png').exists():
        lines.append("![Policy Anchors](figures/fig_policy_anchor_check.png)")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("**Analysis methodology:** LLM-free, deterministic aggregation of TERVYX policy-as-code outputs.")
    lines.append("")
    lines.append("Final labels are determined by GGP gates + TEL-5 thresholds + REML/Monte Carlo simulation (not by LLM).")
    lines.append("")

    # Write report
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    logger.info(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate TERVYX analysis report')
    parser.add_argument(
        '--metrics',
        type=Path,
        default=Path('reports/tables'),
        help='Metrics directory'
    )
    parser.add_argument(
        '--figures',
        type=Path,
        default=Path('reports/figures'),
        help='Figures directory'
    )
    parser.add_argument(
        '--out',
        type=Path,
        default=Path('reports/summary.md'),
        help='Output report file'
    )

    args = parser.parse_args()

    if not args.metrics.exists():
        logger.error(f"Metrics directory not found: {args.metrics}")
        sys.exit(1)

    args.out.parent.mkdir(parents=True, exist_ok=True)

    generate_report(args.metrics, args.figures, args.out)

    logger.info("\n=== Report Complete ===")


if __name__ == '__main__':
    main()
