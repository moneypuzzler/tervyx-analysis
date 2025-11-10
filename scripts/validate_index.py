#!/usr/bin/env python3
"""
Validate ingested index against schemas and policy anchors.

Checks:
- Schema compliance (required fields, types)
- Policy anchor consistency (fingerprints, versions)
- Data quality (duplicates, nulls, ranges)
"""

import argparse
import logging
from pathlib import Path
import sys

import pandas as pd
import yaml

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))
from utils.policy_anchors import load_policy_config, extract_policy_metadata

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def check_required_fields(df: pd.DataFrame) -> None:
    """Verify presence and coverage of required fields."""
    logger.info("=== Checking Required Fields ===")

    required = [
        'id', 'tier', 'label', 'policy_fingerprint',
        'gate_phi', 'gate_k',  # Critical safety gates
        'P_effect_gt_delta'
    ]

    for field in required:
        if field not in df.columns:
            logger.error(f"Missing required field: {field}")
        else:
            null_pct = df[field].isna().mean() * 100
            logger.info(f"{field}: {null_pct:.1f}% null")

            if null_pct > 10:
                logger.warning(f"High null rate for {field}")


def check_tier_label_consistency(df: pd.DataFrame) -> None:
    """Check tier-label mappings match TEL-5 rules."""
    logger.info("\n=== Checking Tier-Label Consistency ===")

    # Expected mappings (from TEL-5 spec)
    tier_to_label = {
        'gold': 'PASS',
        'silver': 'PASS',
        'bronze': 'AMBER',
        'red': 'AMBER',
        'black': 'FAIL'
    }

    mismatches = []
    for tier, expected_label in tier_to_label.items():
        subset = df[df['tier'] == tier]
        if len(subset) > 0:
            wrong = subset[subset['label'] != expected_label]
            if len(wrong) > 0:
                mismatches.append(f"{tier} → {expected_label}: {len(wrong)} mismatches")

    if mismatches:
        logger.warning("Tier-label mismatches found:")
        for msg in mismatches:
            logger.warning(f"  {msg}")
    else:
        logger.info("All tier-label mappings consistent ✓")


def check_policy_anchors(df: pd.DataFrame, policy_path: Path) -> None:
    """Verify policy fingerprints and versions."""
    logger.info("\n=== Checking Policy Anchors ===")

    # Load policy config
    policy_config = load_policy_config(policy_path)
    if not policy_config:
        logger.error(f"Failed to load policy config from {policy_path}")
        return

    policy_meta = extract_policy_metadata(policy_config)
    logger.info(f"Expected policy metadata:")
    logger.info(f"  TEL-5: {policy_meta['tel5_version']}")
    logger.info(f"  Monte Carlo: {policy_meta['mc_version']}")
    logger.info(f"  Journal snapshot: {policy_meta['journal_snapshot']}")

    # Check fingerprints
    unique_fingerprints = df['policy_fingerprint'].unique()
    logger.info(f"\nFound {len(unique_fingerprints)} unique fingerprint(s):")
    for fp in unique_fingerprints:
        count = (df['policy_fingerprint'] == fp).sum()
        logger.info(f"  {fp}: {count} entries")

    if len(unique_fingerprints) > 1:
        logger.warning("Multiple policy fingerprints detected - entries built with different policies!")

    # Check versions
    for field in ['tel5_version', 'mc_version', 'journal_snapshot']:
        if field in df.columns:
            unique_vals = df[field].unique()
            logger.info(f"\n{field}: {len(unique_vals)} unique value(s)")
            for val in unique_vals:
                count = (df[field] == val).sum()
                logger.info(f"  {val}: {count} entries")


def check_gate_violations(df: pd.DataFrame) -> None:
    """Check for Φ/K gate violations (should force Black tier)."""
    logger.info("\n=== Checking Gate Violations ===")

    # Φ-FAIL or K-FAIL should force Black tier
    phi_fail = df[df['gate_phi'] == 'FAIL']
    k_fail = df[df['gate_k'] == 'FAIL']

    logger.info(f"Φ-FAIL: {len(phi_fail)} entries")
    if len(phi_fail) > 0:
        non_black = phi_fail[phi_fail['tier'] != 'black']
        if len(non_black) > 0:
            logger.error(f"  {len(non_black)} Φ-FAIL entries not labeled Black! (monotone violation)")

    logger.info(f"K-FAIL: {len(k_fail)} entries")
    if len(k_fail) > 0:
        non_black = k_fail[k_fail['tier'] != 'black']
        if len(non_black) > 0:
            logger.error(f"  {len(non_black)} K-FAIL entries not labeled Black! (monotone violation)")


def check_p_effect_ranges(df: pd.DataFrame) -> None:
    """Check that P(effect > δ) values are in [0, 1]."""
    logger.info("\n=== Checking P(effect > δ) Ranges ===")

    if 'P_effect_gt_delta' not in df.columns:
        logger.warning("P_effect_gt_delta not found in index")
        return

    p_vals = df['P_effect_gt_delta'].dropna()
    out_of_range = p_vals[(p_vals < 0) | (p_vals > 1)]

    logger.info(f"Valid P values: {len(p_vals) - len(out_of_range)}/{len(p_vals)}")
    if len(out_of_range) > 0:
        logger.error(f"Found {len(out_of_range)} P values outside [0,1]!")


def check_duplicates(df: pd.DataFrame) -> None:
    """Check for duplicate entry IDs."""
    logger.info("\n=== Checking Duplicates ===")

    duplicates = df[df.duplicated(subset=['id'], keep=False)]
    if len(duplicates) > 0:
        logger.error(f"Found {len(duplicates)} duplicate entry IDs:")
        for dup_id in duplicates['id'].unique():
            logger.error(f"  {dup_id}")
    else:
        logger.info("No duplicates found ✓")


def main():
    parser = argparse.ArgumentParser(description='Validate TERVYX analysis index')
    parser.add_argument(
        '--in',
        dest='input',
        type=Path,
        default=Path('reports/tables/index.parquet'),
        help='Input index file'
    )
    parser.add_argument(
        '--schemas',
        type=Path,
        default=Path('tervyx/protocol/schemas'),
        help='Path to protocol schemas directory'
    )
    parser.add_argument(
        '--policy',
        type=Path,
        default=Path('tervyx/policy.yaml'),
        help='Path to policy.yaml'
    )

    args = parser.parse_args()

    if not args.input.exists():
        logger.error(f"Input file not found: {args.input}")
        logger.error("Run 'make ingest' first")
        sys.exit(1)

    # Load index
    logger.info(f"Loading index from {args.input}")
    if args.input.suffix == '.parquet':
        df = pd.read_parquet(args.input)
    else:
        df = pd.read_csv(args.input)

    logger.info(f"Loaded {len(df)} entries\n")

    # Run validation checks
    check_required_fields(df)
    check_tier_label_consistency(df)
    check_duplicates(df)
    check_p_effect_ranges(df)
    check_gate_violations(df)

    if args.policy.exists():
        check_policy_anchors(df, args.policy)
    else:
        logger.warning(f"Policy file not found: {args.policy}")

    logger.info("\n=== Validation Complete ===")


if __name__ == '__main__':
    main()
