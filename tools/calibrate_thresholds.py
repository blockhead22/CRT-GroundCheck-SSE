#!/usr/bin/env python3
"""
Threshold Calibration Script for CRT System.

Computes optimal similarity thresholds by analyzing the distribution of
cosine similarities across different categories (exact matches, paraphrases,
near misses, contradictions).

Instead of hard-coded thresholds like 0.75 or 0.85, this script learns
thresholds that minimize false positives while maintaining recall.

Usage:
    python tools/calibrate_thresholds.py --output artifacts/thresholds.json
    
    # With custom embedding model
    python tools/calibrate_thresholds.py --model all-mpnet-base-v2

Output:
    JSON file with calibrated thresholds and distribution statistics
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

from calibration_dataset import (
    GOLDEN_PAIRS,
    CalibrationPair,
    get_pairs_by_category,
    get_category_counts,
)

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


@dataclass
class DistributionStats:
    """Statistics for similarity distribution within a category."""
    mean: float
    std: float
    min: float
    max: float
    p5: float    # 5th percentile
    p25: float   # 25th percentile (Q1)
    p50: float   # 50th percentile (median)
    p75: float   # 75th percentile (Q3)
    p95: float   # 95th percentile
    count: int


@dataclass
class CalibratedThresholds:
    """Calibrated thresholds for CRT system."""
    
    # Primary thresholds
    green_zone: float     # Above this = definite match (high confidence)
    yellow_zone: float    # Between yellow and green = needs review
    red_zone: float       # Below this = definite non-match
    
    # Category-specific thresholds
    exact_match_min: float     # Minimum similarity for exact matches
    paraphrase_typical: float  # Typical similarity for paraphrases
    near_miss_max: float       # Maximum similarity for near misses
    contradiction_typical: float  # Typical similarity for contradictions
    
    # Distribution stats per category
    distributions: Dict[str, DistributionStats]
    
    # Metadata
    model_name: str
    dataset_size: int
    calibration_date: str


class ThresholdCalibrator:
    """
    Calibrates similarity thresholds using labeled data.
    
    The calibrator computes similarity scores for all pairs in the golden
    dataset and determines optimal thresholds based on the distributions.
    
    Strategy:
    1. Compute similarities for all pairs
    2. Build distribution per category
    3. Set green_zone to be above 95% of paraphrases (high recall)
    4. Set red_zone to be above 95% of near misses (low false positives)
    5. Yellow zone is between red and green
    """
    
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
    ):
        """
        Initialize calibrator with embedding model.
        
        Args:
            model_name: Sentence transformer model name
            device: Device to run on (None for auto-detect)
        """
        self.model_name = model_name
        self.model = None
        self.device = device
        
    def _load_model(self):
        """Load embedding model lazily."""
        if self.model is not None:
            return
        
        try:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name, device=self.device)
        except ImportError:
            raise ImportError(
                "sentence-transformers is required. Install with: "
                "pip install sentence-transformers"
            )
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        self._load_model()
        
        emb1 = self.model.encode(text1, convert_to_numpy=True)
        emb2 = self.model.encode(text2, convert_to_numpy=True)
        
        # Cosine similarity
        similarity = float(
            np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        )
        return similarity
    
    def _compute_distribution_stats(
        self,
        similarities: List[float],
    ) -> DistributionStats:
        """Compute distribution statistics for a list of similarities."""
        arr = np.array(similarities)
        
        return DistributionStats(
            mean=float(np.mean(arr)),
            std=float(np.std(arr)),
            min=float(np.min(arr)),
            max=float(np.max(arr)),
            p5=float(np.percentile(arr, 5)),
            p25=float(np.percentile(arr, 25)),
            p50=float(np.percentile(arr, 50)),
            p75=float(np.percentile(arr, 75)),
            p95=float(np.percentile(arr, 95)),
            count=len(arr),
        )
    
    def calibrate(
        self,
        pairs: Optional[List[CalibrationPair]] = None,
    ) -> CalibratedThresholds:
        """
        Calibrate thresholds using the golden dataset.
        
        Args:
            pairs: Optional list of pairs (uses GOLDEN_PAIRS if not provided)
            
        Returns:
            CalibratedThresholds with optimal thresholds
        """
        pairs = pairs or GOLDEN_PAIRS
        
        # Compute similarities per category
        distributions: Dict[str, List[float]] = {
            "exact_match": [],
            "paraphrase": [],
            "near_miss": [],
            "contradiction": [],
        }
        
        logger.info(f"Computing similarities for {len(pairs)} pairs...")
        
        for pair in pairs:
            sim = self._compute_similarity(pair.text1, pair.text2)
            if pair.category in distributions:
                distributions[pair.category].append(sim)
        
        # Compute stats per category
        stats: Dict[str, DistributionStats] = {}
        for category, sims in distributions.items():
            if sims:
                stats[category] = self._compute_distribution_stats(sims)
                logger.info(
                    f"{category}: mean={stats[category].mean:.3f}, "
                    f"std={stats[category].std:.3f}, "
                    f"[{stats[category].min:.3f}, {stats[category].max:.3f}]"
                )
        
        # Determine thresholds
        # Green zone: Should be above 95% of paraphrases (capture most true matches)
        paraphrase_stats = stats.get("paraphrase")
        green_zone = paraphrase_stats.p5 if paraphrase_stats else 0.85
        
        # Red zone: Should be above 95% of near misses (reject most false positives)
        near_miss_stats = stats.get("near_miss")
        red_zone = near_miss_stats.p95 if near_miss_stats else 0.75
        
        # Ensure green > red
        if green_zone <= red_zone:
            # Adjust by averaging
            mid = (green_zone + red_zone) / 2
            green_zone = mid + 0.05
            red_zone = mid - 0.05
        
        # Yellow zone is implicitly between red and green
        yellow_zone = (green_zone + red_zone) / 2
        
        from datetime import datetime
        
        def default_stats(default_value: float) -> DistributionStats:
            """Create default DistributionStats with a uniform value."""
            return DistributionStats(
                mean=default_value, std=0, min=default_value, max=default_value,
                p5=default_value, p25=default_value, p50=default_value,
                p75=default_value, p95=default_value, count=0
            )
        
        return CalibratedThresholds(
            green_zone=float(round(green_zone, 3)),
            yellow_zone=float(round(yellow_zone, 3)),
            red_zone=float(round(red_zone, 3)),
            exact_match_min=float(round(
                stats.get("exact_match", default_stats(1.0)).p5, 3
            )),
            paraphrase_typical=float(round(
                stats.get("paraphrase", default_stats(0.8)).p50, 3
            )),
            near_miss_max=float(round(
                stats.get("near_miss", default_stats(0.7)).p95, 3
            )),
            contradiction_typical=float(round(
                stats.get("contradiction", default_stats(0.6)).p50, 3
            )),
            distributions={k: asdict(v) for k, v in stats.items()},
            model_name=self.model_name,
            dataset_size=len(pairs),
            calibration_date=datetime.utcnow().isoformat() + "Z",
        )
    
    def validate_thresholds(
        self,
        thresholds: CalibratedThresholds,
        pairs: Optional[List[CalibrationPair]] = None,
    ) -> Dict[str, Any]:
        """
        Validate thresholds against the dataset.
        
        Computes precision/recall/F1 for each category using the thresholds.
        
        Args:
            thresholds: Thresholds to validate
            pairs: Optional list of pairs (uses GOLDEN_PAIRS if not provided)
            
        Returns:
            Dictionary with validation metrics
        """
        pairs = pairs or GOLDEN_PAIRS
        
        # Count predictions using green zone as match threshold
        tp = 0  # True positives (paraphrase/exact correctly classified)
        fp = 0  # False positives (near_miss/contradiction wrongly classified as match)
        tn = 0  # True negatives (near_miss/contradiction correctly rejected)
        fn = 0  # False negatives (paraphrase/exact wrongly rejected)
        
        for pair in pairs:
            sim = self._compute_similarity(pair.text1, pair.text2)
            is_match_category = pair.category in ("exact_match", "paraphrase")
            is_predicted_match = sim >= thresholds.green_zone
            
            if is_match_category and is_predicted_match:
                tp += 1
            elif not is_match_category and is_predicted_match:
                fp += 1
            elif not is_match_category and not is_predicted_match:
                tn += 1
            else:
                fn += 1
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
            "total_pairs": len(pairs),
        }


def save_thresholds(
    thresholds: CalibratedThresholds,
    output_path: str,
) -> None:
    """Save thresholds to JSON file."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # Convert to serializable dict
    data = {
        "green_zone": thresholds.green_zone,
        "yellow_zone": thresholds.yellow_zone,
        "red_zone": thresholds.red_zone,
        "exact_match_min": thresholds.exact_match_min,
        "paraphrase_typical": thresholds.paraphrase_typical,
        "near_miss_max": thresholds.near_miss_max,
        "contradiction_typical": thresholds.contradiction_typical,
        "distributions": thresholds.distributions,
        "model_name": thresholds.model_name,
        "dataset_size": thresholds.dataset_size,
        "calibration_date": thresholds.calibration_date,
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    logger.info(f"Saved thresholds to {path}")


def load_thresholds(path: str) -> Optional[CalibratedThresholds]:
    """Load thresholds from JSON file."""
    try:
        with open(path) as f:
            data = json.load(f)
        
        distributions = {}
        for k, v in data.get("distributions", {}).items():
            distributions[k] = DistributionStats(**v)
        
        return CalibratedThresholds(
            green_zone=data["green_zone"],
            yellow_zone=data["yellow_zone"],
            red_zone=data["red_zone"],
            exact_match_min=data["exact_match_min"],
            paraphrase_typical=data["paraphrase_typical"],
            near_miss_max=data["near_miss_max"],
            contradiction_typical=data["contradiction_typical"],
            distributions=distributions,
            model_name=data["model_name"],
            dataset_size=data["dataset_size"],
            calibration_date=data["calibration_date"],
        )
    except Exception as e:
        logger.warning(f"Failed to load thresholds from {path}: {e}")
        return None


def main(argv: Optional[List[str]] = None) -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Calibrate CRT similarity thresholds"
    )
    parser.add_argument(
        "--model",
        default="all-MiniLM-L6-v2",
        help="Sentence transformer model name",
    )
    parser.add_argument(
        "--output",
        default="artifacts/calibrated_thresholds.json",
        help="Output JSON path",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Run validation after calibration",
    )
    
    args = parser.parse_args(argv)
    
    # Print dataset info
    counts = get_category_counts()
    logger.info(f"Dataset categories: {counts}")
    
    # Calibrate
    calibrator = ThresholdCalibrator(model_name=args.model)
    thresholds = calibrator.calibrate()
    
    # Print results
    logger.info(f"\nCalibrated thresholds:")
    logger.info(f"  Green zone (definite match): >= {thresholds.green_zone}")
    logger.info(f"  Yellow zone (uncertain): {thresholds.red_zone} - {thresholds.green_zone}")
    logger.info(f"  Red zone (definite non-match): < {thresholds.red_zone}")
    
    # Save
    save_thresholds(thresholds, args.output)
    
    # Validate
    if args.validate:
        logger.info("\nValidating thresholds...")
        metrics = calibrator.validate_thresholds(thresholds)
        logger.info(f"Validation metrics:")
        for k, v in metrics.items():
            logger.info(f"  {k}: {v}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
