"""Policy fingerprint validation and anchor checking."""

import hashlib
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import yaml

logger = logging.getLogger(__name__)


def load_policy_config(policy_path: Path) -> Optional[Dict[str, Any]]:
    """
    Load policy.yaml configuration.

    Expected structure:
    tel5_levels:
      version: "1.2.0"
      thresholds:
        gold: 0.80
        silver: 0.60
        bronze: 0.40
        red: 0.20

    monte_carlo:
      version: "1.0.1-reml-grid"
      n_draws: 10000
      seed: null

    journal_trust:
      snapshot_date: "2025-10-05"
      sources:
        - bealls_list
        - retraction_watch
      weights:
        ...
    """
    try:
        with open(policy_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load policy.yaml: {e}")
        return None


def compute_policy_fingerprint(policy_config: Dict[str, Any]) -> str:
    """
    Compute SHA256 fingerprint of policy configuration.

    This should match the computation in TERVYX engine.
    Canonical serialization: sorted keys, compact JSON.
    """
    try:
        import json
        # Canonical JSON: sorted keys, no whitespace
        canonical = json.dumps(policy_config, sort_keys=True, separators=(',', ':'))
        digest = hashlib.sha256(canonical.encode('utf-8')).hexdigest()
        return f"sha256:{digest}"
    except Exception as e:
        logger.error(f"Failed to compute fingerprint: {e}")
        return ""


def validate_policy_fingerprint(
    entry_fingerprint: str,
    policy_config: Dict[str, Any]
) -> bool:
    """
    Validate that entry's policy_fingerprint matches computed fingerprint.

    Returns:
        True if fingerprints match, False otherwise.
    """
    if not entry_fingerprint or not policy_config:
        return False

    expected = compute_policy_fingerprint(policy_config)
    if entry_fingerprint != expected:
        logger.warning(
            f"Policy fingerprint mismatch!\n"
            f"  Entry:    {entry_fingerprint}\n"
            f"  Expected: {expected}"
        )
        return False

    return True


def extract_policy_metadata(policy_config: Dict[str, Any]) -> Dict[str, str]:
    """
    Extract version/snapshot metadata from policy config.

    Returns:
        {
          'tel5_version': '1.2.0',
          'mc_version': '1.0.1-reml-grid',
          'journal_snapshot': '2025-10-05'
        }
    """
    return {
        'tel5_version': policy_config.get('tel5_levels', {}).get('version', ''),
        'mc_version': policy_config.get('monte_carlo', {}).get('version', ''),
        'journal_snapshot': policy_config.get('journal_trust', {}).get('snapshot_date', ''),
    }
