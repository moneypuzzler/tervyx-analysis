#!/usr/bin/env python3
"""
Generate visualization figures from metrics.

Creates:
- TEL-5 tier histogram
- Gate performance bar chart
- J-Oracle distribution
- Policy anchor consistency
"""

import argparse
import logging
from pathlib import Path
import sys

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def plot_tel5_distribution(metrics_dir: Path, output_dir: Path):
    """Plot TEL-5 tier distribution histogram."""
    logger.info("Plotting TEL-5 distribution...")

    tel5_file = metrics_dir / 'tel5_distribution.csv'
    if not tel5_file.exists():
        logger.warning(f"TEL-5 metrics not found: {tel5_file}")
        return

    df = pd.read_csv(tel5_file)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Bar chart
    ax.bar(df['tier'], df['count'])
    ax.set_xlabel('TEL-5 Tier')
    ax.set_ylabel('Count')
    ax.set_title('TEL-5 Tier Distribution')

    # Add percentage labels
    for i, row in df.iterrows():
        ax.text(i, row['count'], f"{row['percentage']:.1f}%",
                ha='center', va='bottom')

    plt.tight_layout()
    output_path = output_dir / 'fig_tel5_hist.png'
    plt.savefig(output_path, dpi=150)
    plt.close()

    logger.info(f"Saved: {output_path}")


def plot_gate_performance(metrics_dir: Path, output_dir: Path):
    """Plot gate PASS/FAIL rates."""
    logger.info("Plotting gate performance...")

    gate_file = metrics_dir / 'gate_performance.csv'
    if not gate_file.exists():
        logger.warning(f"Gate metrics not found: {gate_file}")
        return

    df = pd.read_csv(gate_file)

    # Pivot for stacked bar
    # Filter to just Φ and K for key safety gates
    phi_k_df = df[df['gate'].isin(['phi', 'k'])]

    if len(phi_k_df) == 0:
        logger.warning("No Φ/K gate data")
        return

    fig, ax = plt.subplots(figsize=(8, 6))

    # Group by gate
    gates = phi_k_df['gate'].unique()
    metrics = phi_k_df['metric'].unique()

    width = 0.35
    x = range(len(gates))

    for i, metric in enumerate(metrics):
        values = [
            phi_k_df[(phi_k_df['gate'] == g) & (phi_k_df['metric'] == metric)]['percentage'].values[0]
            if len(phi_k_df[(phi_k_df['gate'] == g) & (phi_k_df['metric'] == metric)]) > 0
            else 0
            for g in gates
        ]
        ax.bar([xi + i*width for xi in x], values, width, label=metric)

    ax.set_xlabel('Gate')
    ax.set_ylabel('Percentage')
    ax.set_title('Φ/K Safety Gate Performance\n(Monotone Invariant: FAIL → Black tier)')
    ax.set_xticks([xi + width/2 for xi in x])
    ax.set_xticklabels([g.upper() for g in gates])
    ax.legend()

    plt.tight_layout()
    output_path = output_dir / 'fig_gate_fail_phi_k.png'
    plt.savefig(output_path, dpi=150)
    plt.close()

    logger.info(f"Saved: {output_path}")


def plot_j_oracle_distribution(metrics_dir: Path, output_dir: Path):
    """Plot J-Oracle score distribution."""
    logger.info("Plotting J-Oracle distribution...")

    j_file = metrics_dir / 'j_oracle_distribution.csv'
    if not j_file.exists():
        logger.warning(f"J-Oracle metrics not found: {j_file}")
        return

    df = pd.read_csv(j_file)

    fig, ax = plt.subplots(figsize=(10, 6))

    # Bar chart
    ax.bar(df['j_range'], df['count'])
    ax.set_xlabel('J-Oracle Score Range')
    ax.set_ylabel('Count')
    ax.set_title('J-Oracle Distribution\n(BLACK = predatory/retracted sources)')
    ax.tick_params(axis='x', rotation=45)

    # Add percentage labels
    for i, row in df.iterrows():
        ax.text(i, row['count'], f"{row['percentage']:.1f}%",
                ha='center', va='bottom')

    plt.tight_layout()
    output_path = output_dir / 'fig_jstar_hist.png'
    plt.savefig(output_path, dpi=150)
    plt.close()

    logger.info(f"Saved: {output_path}")


def plot_policy_anchors(metrics_dir: Path, output_dir: Path):
    """Plot policy anchor consistency."""
    logger.info("Plotting policy anchors...")

    policy_file = metrics_dir / 'policy_anchors.csv'
    if not policy_file.exists():
        logger.warning(f"Policy anchor metrics not found: {policy_file}")
        return

    df = pd.read_csv(policy_file)

    # Filter to just version fields (not fingerprint for clarity)
    version_fields = ['tel5_version', 'mc_version', 'journal_snapshot']
    version_df = df[df['anchor_type'].isin(version_fields)]

    if len(version_df) == 0:
        logger.warning("No version anchor data")
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    # Group by anchor type
    for anchor_type in version_fields:
        subset = version_df[version_df['anchor_type'] == anchor_type]
        if len(subset) == 0:
            continue

        # Simple bar per version
        x_pos = list(range(len(subset)))
        ax.barh([f"{anchor_type}\n{row['value']}" for _, row in subset.iterrows()],
                subset['percentage'])

    ax.set_xlabel('Percentage of Entries')
    ax.set_title('Policy Anchor Consistency\n(All entries should use same versions)')

    plt.tight_layout()
    output_path = output_dir / 'fig_policy_anchor_check.png'
    plt.savefig(output_path, dpi=150)
    plt.close()

    logger.info(f"Saved: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='Generate TERVYX visualizations')
    parser.add_argument(
        '--in',
        dest='input',
        type=Path,
        default=Path('reports/tables'),
        help='Input metrics directory'
    )
    parser.add_argument(
        '--out',
        type=Path,
        default=Path('reports/figures'),
        help='Output figures directory'
    )

    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Metrics directory not found: {args.input}")
        sys.exit(1)

    args.out.mkdir(parents=True, exist_ok=True)

    logger.info(f"Generating figures from {args.input}")

    # Generate plots
    plot_tel5_distribution(args.input, args.out)
    plot_gate_performance(args.input, args.out)
    plot_j_oracle_distribution(args.input, args.out)
    plot_policy_anchors(args.input, args.out)

    logger.info(f"\nAll figures saved to {args.out}/")


if __name__ == '__main__':
    main()
