"""Safe parsers for TERVYX output files (entry.jsonld, simulation.json, citations.json)."""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

logger = logging.getLogger(__name__)


def _load_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file with fallback to standard library if orjson unavailable."""
    try:
        if HAS_ORJSON:
            with open(file_path, 'rb') as f:
                return orjson.loads(f.read())
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Failed to parse {file_path}: {e}")
        return None


def parse_entry(entry_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse entry.jsonld and extract key fields.

    Expected structure (JSON-LD format):
    {
      "@context": "https://schema.org",
      "@type": "MedicalGuideline",
      "@id": "tervyx:entry:<id>",
      "tier": "gold" | "silver" | "bronze" | "red" | "black",
      "label": "PASS" | "AMBER" | "FAIL",
      "gate_results": {
        "phi": "PASS" | "FAIL",
        "r": "PASS" | "FAIL",
        "j": 0.0-1.0 | "BLACK",
        "k": "PASS" | "FAIL",
        "l": "PASS" | "FAIL"
      },
      "policy_fingerprint": "sha256:...",
      "policy_refs": {
        "tel5_levels": {"version": "1.2.0"},
        "monte_carlo": {"version": "1.0.1-reml-grid"},
        "journal_trust": {"snapshot_date": "2025-10-05"}
      },
      ...
    }
    """
    data = _load_json(entry_path)
    if not data:
        return None

    try:
        # Extract core fields
        result = {
            'id': data.get('@id', '').replace('tervyx:entry:', ''),
            'tier': data.get('tier', '').lower(),
            'label': data.get('label', '').upper(),
            'policy_fingerprint': data.get('policy_fingerprint', ''),
        }

        # Gate results
        gates = data.get('gate_results', {})
        result.update({
            'gate_phi': gates.get('phi', ''),
            'gate_r': gates.get('r', ''),
            'gate_j': gates.get('j', ''),
            'gate_k': gates.get('k', ''),
            'gate_l': gates.get('l', ''),
        })

        # Policy refs
        policy_refs = data.get('policy_refs', {})
        result['tel5_version'] = policy_refs.get('tel5_levels', {}).get('version', '')
        result['mc_version'] = policy_refs.get('monte_carlo', {}).get('version', '')
        result['journal_snapshot'] = policy_refs.get('journal_trust', {}).get('snapshot_date', '')

        # Optional: intervention type (schema v2)
        result['intervention_type'] = data.get('intervention_type', '')

        return result

    except Exception as e:
        logger.error(f"Error extracting fields from {entry_path}: {e}")
        return None


def parse_simulation(sim_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse simulation.json and extract Monte Carlo results.

    Expected structure:
    {
      "seed": 12345,
      "n_draws": 10000,
      "P_effect_gt_delta": 0.75,
      "mu_hat": 0.35,
      "mu_CI95": [0.12, 0.58],
      "I2": 0.65,
      "tau2": 0.08,
      "policy_fingerprint": "sha256:..."
    }
    """
    data = _load_json(sim_path)
    if not data:
        return None

    try:
        return {
            'seed': data.get('seed', None),
            'n_draws': data.get('n_draws', 10000),
            'P_effect_gt_delta': data.get('P_effect_gt_delta', None),
            'mu_hat': data.get('mu_hat', None),
            'mu_CI95_lower': data.get('mu_CI95', [None, None])[0],
            'mu_CI95_upper': data.get('mu_CI95', [None, None])[1],
            'I2': data.get('I2', None),
            'tau2': data.get('tau2', None),
        }
    except Exception as e:
        logger.error(f"Error extracting fields from {sim_path}: {e}")
        return None


def parse_citations(cit_path: Path) -> Optional[Dict[str, Any]]:
    """
    Parse citations.json and extract study metadata.

    Expected structure:
    {
      "studies": [
        {
          "study_id": "...",
          "doi": "10.1234/...",
          "title": "...",
          "authors": [...],
          "year": 2023,
          "journal": "...",
          ...
        }
      ]
    }
    """
    data = _load_json(cit_path)
    if not data:
        return None

    try:
        studies = data.get('studies', [])
        return {
            'n_studies': len(studies),
            'dois': [s.get('doi', '') for s in studies if s.get('doi')],
            'years': [s.get('year', None) for s in studies if s.get('year')],
        }
    except Exception as e:
        logger.error(f"Error extracting fields from {cit_path}: {e}")
        return None
