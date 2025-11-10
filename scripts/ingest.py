#!/usr/bin/env python3
"""
Ingest TERVYX entry artifacts and build analysis index.

Scans entries directory, parses entry.jsonld/simulation.json/citations.json,
and generates a consolidated index file (parquet/csv).
"""

import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any
import sys

import pandas as pd
from tqdm import tqdm

# Add utils to path
sys.path.insert(0, str(Path(__file__).parent))
from utils.jsonld_reader import parse_entry, parse_simulation, parse_citations
from utils.shard import ShardedProcessor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def find_entry_dirs(root_path: Path) -> List[Path]:
    """
    Find all entry directories containing entry.jsonld.

    Expected structure:
      entries/
        supplements/
          vitamin-d/
            mood-improvement/
              entry.jsonld
              simulation.json
              citations.json
    """
    logger.info(f"Scanning for entries in {root_path}")
    entry_files = list(root_path.rglob('**/entry.jsonld'))
    logger.info(f"Found {len(entry_files)} entry directories")
    return [f.parent for f in entry_files]


def process_entry_dir(entry_dir: Path) -> Dict[str, Any]:
    """
    Parse all artifacts in an entry directory.

    Returns:
        Dictionary with combined data from entry/simulation/citations.
    """
    entry_path = entry_dir / 'entry.jsonld'
    sim_path = entry_dir / 'simulation.json'
    cit_path = entry_dir / 'citations.json'

    # Parse entry (required)
    entry_data = parse_entry(entry_path)
    if not entry_data:
        logger.warning(f"Skipping {entry_dir}: failed to parse entry.jsonld")
        return None

    # Parse simulation (required)
    sim_data = parse_simulation(sim_path)
    if not sim_data:
        logger.warning(f"Missing simulation data for {entry_dir}")

    # Parse citations (optional)
    cit_data = parse_citations(cit_path)
    if not cit_data:
        logger.debug(f"Missing citations data for {entry_dir}")

    # Combine
    result = {
        'entry_path': str(entry_dir.relative_to(entry_dir.parents[4])),  # Relative to repo root
        **entry_data,
    }

    if sim_data:
        result.update(sim_data)

    if cit_data:
        result.update(cit_data)

    return result


def main():
    parser = argparse.ArgumentParser(description='Ingest TERVYX entries')
    parser.add_argument(
        '--root',
        type=Path,
        default=Path('tervyx/entries'),
        help='Root directory containing entries'
    )
    parser.add_argument(
        '--out',
        type=Path,
        default=Path('reports/tables/index.parquet'),
        help='Output file (parquet or csv)'
    )
    parser.add_argument(
        '--shard-index',
        type=int,
        default=0,
        help='Shard index (0-based)'
    )
    parser.add_argument(
        '--shard-count',
        type=int,
        default=1,
        help='Total number of shards'
    )
    parser.add_argument(
        '--format',
        choices=['parquet', 'csv'],
        default='parquet',
        help='Output format'
    )

    args = parser.parse_args()

    if not args.root.exists():
        logger.error(f"Root path does not exist: {args.root}")
        logger.error("Run 'bash scripts/update_submodule.sh' first to initialize submodule")
        sys.exit(1)

    # Find all entry directories
    entry_dirs = find_entry_dirs(args.root)

    if not entry_dirs:
        logger.error("No entries found. Check submodule initialization.")
        sys.exit(1)

    # Shard processing
    processor = ShardedProcessor(
        entry_dirs,
        shard_index=args.shard_index,
        shard_count=args.shard_count
    )

    # Process entries
    logger.info(f"Processing {len(processor.shard_files)} entries (shard {args.shard_index}/{args.shard_count})")
    records = []

    for entry_dir in tqdm(processor.iter_files(), desc='Ingesting', total=len(processor.shard_files)):
        record = process_entry_dir(entry_dir)
        if record:
            records.append(record)

    if not records:
        logger.error("No valid entries processed!")
        sys.exit(1)

    # Build dataframe
    df = pd.DataFrame(records)
    logger.info(f"Created index with {len(df)} rows, {len(df.columns)} columns")

    # Save
    args.out.parent.mkdir(parents=True, exist_ok=True)

    if args.format == 'parquet':
        df.to_parquet(args.out, index=False, compression='snappy')
    else:
        df.to_csv(args.out, index=False)

    logger.info(f"Saved index to {args.out}")

    # Summary stats
    logger.info("\n=== Ingestion Summary ===")
    logger.info(f"Total entries: {len(df)}")
    logger.info(f"Tiers: {df['tier'].value_counts().to_dict()}")
    logger.info(f"Labels: {df['label'].value_counts().to_dict()}")
    logger.info(f"Unique policy fingerprints: {df['policy_fingerprint'].nunique()}")


if __name__ == '__main__':
    main()
