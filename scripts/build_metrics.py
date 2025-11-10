#!/usr/bin/env python3
"""
Generate metrics from ingested index.

Computes:
- TEL-5 tier distribution
- Gate performance (Φ/R/J/K/L pass/fail rates)
- J-Oracle statistics
- Policy anchor summary
"""

import argparse
import logging
from pathlib import Path
import sys

import pandas as pd
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def compute_tel5_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute TEL-5 tier distribution.

    Returns:
        DataFrame with tier, count, percentage, label
    """
    tier_order = ['gold', 'silver', 'bronze', 'red', 'black']
    tier_counts = df['tier'].value_counts()

    metrics = []
    for tier in tier_order:
        count = tier_counts.get(tier, 0)
        pct = (count / len(df)) * 100 if len(df) > 0 else 0

        # Infer label
        if tier in ['gold', 'silver']:
            label = 'PASS'
        elif tier in ['bronze', 'red']:
            label = 'AMBER'
        else:
            label = 'FAIL'

        metrics.append({
            'tier': tier,
            'count': count,
            'percentage': pct,
            'label': label
        })

    return pd.DataFrame(metrics)


def compute_gate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute gate performance statistics.

    Returns:
        DataFrame with gate, pass_count, fail_count, fail_percentage
    """
    gates = ['phi', 'r', 'j', 'k', 'l']
    metrics = []

    for gate in gates:
        col = f'gate_{gate}'
        if col not in df.columns:
            logger.warning(f"Gate column not found: {col}")
            continue

        # For J, handle BLACK as special case
        if gate == 'j':
            # J can be 0-1 (numeric) or "BLACK"
            j_vals = df[col].dropna()
            # Count BLACK as FAIL
            black_count = (j_vals == 'BLACK').sum()
            # For numeric values, consider < 0.5 as "weak" (but not necessarily FAIL)
            # Just report BLACK separately
            metrics.append({
                'gate': 'j',
                'metric': 'BLACK_count',
                'value': black_count,
                'percentage': (black_count / len(df)) * 100
            })
        else:
            # Φ/R/K/L are PASS/FAIL
            fail_count = (df[col] == 'FAIL').sum()
            pass_count = (df[col] == 'PASS').sum()

            metrics.append({
                'gate': gate,
                'metric': 'PASS',
                'value': pass_count,
                'percentage': (pass_count / len(df)) * 100
            })
            metrics.append({
                'gate': gate,
                'metric': 'FAIL',
                'value': fail_count,
                'percentage': (fail_count / len(df)) * 100
            })

    return pd.DataFrame(metrics)


def compute_j_oracle_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute J-Oracle distribution statistics.

    Returns:
        DataFrame with J score bins and BLACK count
    """
    if 'gate_j' not in df.columns:
        logger.warning("gate_j not found")
        return pd.DataFrame()

    j_vals = df['gate_j'].dropna()

    # Separate BLACK from numeric
    black_count = (j_vals == 'BLACK').sum()
    numeric_j = pd.to_numeric(j_vals, errors='coerce').dropna()

    # Bin numeric J scores
    bins = [0, 0.25, 0.5, 0.75, 1.0]
    labels = ['0-0.25', '0.25-0.5', '0.5-0.75', '0.75-1.0']

    if len(numeric_j) > 0:
        j_binned = pd.cut(numeric_j, bins=bins, labels=labels, include_lowest=True)
        bin_counts = j_binned.value_counts().sort_index()
    else:
        bin_counts = pd.Series(0, index=labels)

    metrics = []
    for label, count in bin_counts.items():
        metrics.append({
            'j_range': label,
            'count': count,
            'percentage': (count / len(df)) * 100
        })

    metrics.append({
        'j_range': 'BLACK',
        'count': black_count,
        'percentage': (black_count / len(df)) * 100
    })

    return pd.DataFrame(metrics)


def compute_policy_anchor_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute policy anchor consistency metrics.

    Returns:
        DataFrame with policy version distribution
    """
    metrics = []

    # Fingerprints
    if 'policy_fingerprint' in df.columns:
        fps = df['policy_fingerprint'].value_counts()
        for fp, count in fps.items():
            metrics.append({
                'anchor_type': 'policy_fingerprint',
                'value': fp[:16] + '...' if len(fp) > 16 else fp,
                'count': count,
                'percentage': (count / len(df)) * 100
            })

    # Versions
    for field in ['tel5_version', 'mc_version', 'journal_snapshot']:
        if field in df.columns:
            vals = df[field].value_counts()
            for val, count in vals.items():
                metrics.append({
                    'anchor_type': field,
                    'value': val,
                    'count': count,
                    'percentage': (count / len(df)) * 100
                })

    return pd.DataFrame(metrics)


def compute_p_effect_stats(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute P(effect > δ) distribution statistics.

    Returns:
        DataFrame with percentile stats
    """
    if 'P_effect_gt_delta' not in df.columns:
        logger.warning("P_effect_gt_delta not found")
        return pd.DataFrame()

    p_vals = df['P_effect_gt_delta'].dropna()

    percentiles = [0, 10, 25, 50, 75, 90, 100]
    values = np.percentile(p_vals, percentiles)

    metrics = []
    for pct, val in zip(percentiles, values):
        metrics.append({
            'percentile': f'p{pct}',
            'P_effect_value': val
        })

    return pd.DataFrame(metrics)


def main():
    parser = argparse.ArgumentParser(description='Build TERVYX metrics')
    parser.add_argument(
        '--in',
        dest='input',
        type=Path,
        default=Path('reports/tables/index.parquet'),
        help='Input index file'
    )
    parser.add_argument(
        '--out',
        type=Path,
        default=Path('reports/tables/metrics.csv'),
        help='Output metrics CSV'
    )

    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        sys.exit(1)

    # Load index
    logger.info(f"Loading index from {args.input}")
    if args.input.suffix == '.parquet':
        df = pd.read_parquet(args.input)
    else:
        df = pd.read_csv(args.input)

    logger.info(f"Loaded {len(df)} entries")

    # Compute metrics
    logger.info("\n=== Computing Metrics ===")

    tel5_metrics = compute_tel5_metrics(df)
    logger.info(f"TEL-5 metrics: {len(tel5_metrics)} rows")

    gate_metrics = compute_gate_metrics(df)
    logger.info(f"Gate metrics: {len(gate_metrics)} rows")

    j_oracle_metrics = compute_j_oracle_stats(df)
    logger.info(f"J-Oracle metrics: {len(j_oracle_metrics)} rows")

    policy_metrics = compute_policy_anchor_stats(df)
    logger.info(f"Policy anchor metrics: {len(policy_metrics)} rows")

    p_effect_metrics = compute_p_effect_stats(df)
    logger.info(f"P(effect) metrics: {len(p_effect_metrics)} rows")

    # Save individual metric tables
    out_dir = args.out.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    tel5_metrics.to_csv(out_dir / 'tel5_distribution.csv', index=False)
    gate_metrics.to_csv(out_dir / 'gate_performance.csv', index=False)
    j_oracle_metrics.to_csv(out_dir / 'j_oracle_distribution.csv', index=False)
    policy_metrics.to_csv(out_dir / 'policy_anchors.csv', index=False)
    p_effect_metrics.to_csv(out_dir / 'p_effect_percentiles.csv', index=False)

    logger.info(f"\nSaved metric tables to {out_dir}/")

    # Create summary
    summary = {
        'total_entries': len(df),
        'pass_count': len(df[df['label'] == 'PASS']),
        'amber_count': len(df[df['label'] == 'AMBER']),
        'fail_count': len(df[df['label'] == 'FAIL']),
    }

    summary_df = pd.DataFrame([summary])
    summary_df.to_csv(args.out, index=False)
    logger.info(f"Saved summary to {args.out}")

    logger.info("\n=== Metrics Complete ===")


if __name__ == '__main__':
    main()
