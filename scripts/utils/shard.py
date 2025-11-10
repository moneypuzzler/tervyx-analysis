"""Memory-efficient sharding for large datasets."""

import logging
from pathlib import Path
from typing import List, Iterator, Callable, Any

logger = logging.getLogger(__name__)


class ShardedProcessor:
    """
    Process large file lists in shards to limit memory usage.

    Usage:
        processor = ShardedProcessor(all_files, shard_index=0, shard_count=4)
        for file_path in processor.iter_files():
            process(file_path)
    """

    def __init__(
        self,
        files: List[Path],
        shard_index: int = 0,
        shard_count: int = 1
    ):
        """
        Initialize sharded processor.

        Args:
            files: Complete list of files to process
            shard_index: Current shard (0-indexed)
            shard_count: Total number of shards
        """
        if shard_count < 1:
            raise ValueError("shard_count must be >= 1")
        if not (0 <= shard_index < shard_count):
            raise ValueError(f"shard_index must be in range [0, {shard_count-1}]")

        self.all_files = sorted(files)
        self.shard_index = shard_index
        self.shard_count = shard_count

        # Assign files to this shard
        self.shard_files = [
            f for i, f in enumerate(self.all_files)
            if i % shard_count == shard_index
        ]

        logger.info(
            f"Shard {shard_index}/{shard_count}: "
            f"{len(self.shard_files)}/{len(self.all_files)} files"
        )

    def iter_files(self) -> Iterator[Path]:
        """Iterate over files in this shard."""
        return iter(self.shard_files)

    def process_batch(
        self,
        process_fn: Callable[[Path], Any],
        batch_size: int = 100
    ) -> Iterator[Any]:
        """
        Process files in batches with progress logging.

        Args:
            process_fn: Function to apply to each file
            batch_size: Number of files per batch

        Yields:
            Results from process_fn (non-None values)
        """
        batch = []
        for i, file_path in enumerate(self.shard_files, 1):
            try:
                result = process_fn(file_path)
                if result is not None:
                    batch.append(result)

                if i % batch_size == 0:
                    logger.info(f"Processed {i}/{len(self.shard_files)} files")
                    yield from batch
                    batch = []

            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")

        # Yield remaining
        if batch:
            yield from batch
            logger.info(f"Processed {len(self.shard_files)}/{len(self.shard_files)} files (complete)")


def merge_sharded_results(
    shard_outputs: List[Path],
    output_path: Path,
    format: str = 'parquet'
) -> None:
    """
    Merge multiple shard output files into single file.

    Args:
        shard_outputs: List of shard parquet/csv files
        output_path: Destination for merged file
        format: 'parquet' or 'csv'
    """
    import pandas as pd

    logger.info(f"Merging {len(shard_outputs)} shards into {output_path}")

    dfs = []
    for shard_path in shard_outputs:
        if format == 'parquet':
            df = pd.read_parquet(shard_path)
        elif format == 'csv':
            df = pd.read_csv(shard_path)
        else:
            raise ValueError(f"Unsupported format: {format}")
        dfs.append(df)

    merged = pd.concat(dfs, ignore_index=True)

    if format == 'parquet':
        merged.to_parquet(output_path, index=False)
    else:
        merged.to_csv(output_path, index=False)

    logger.info(f"Merged {len(merged)} total rows")
