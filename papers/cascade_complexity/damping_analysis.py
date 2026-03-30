"""Cascade Damping Analysis based on Theorem 4.3 and Corollary 4.3.1

Implements analysis of per-node cascade damping bounds:
- Per-path impact bounds
- Graph-wide total impact bounds
- Convergence conditions
"""

import math
from typing import Dict, List, Any


def cascade_damping_analysis(
    delta_0: float,
    rho: float,
    tau: float,
    max_degree: int,
    max_depth: int
) -> Dict[str, Any]:
    """
    Analyze cascade damping properties per Theorem 4.3.
    
    Args:
        delta_0: Initial impact at source node
        rho: Damping factor (L * w_max), must be < 1 for convergence
        tau: Threshold below which impact is considered negligible
        max_degree: Maximum node degree (d) in the graph
        max_depth: Maximum depth to compute damping curve
    
    Returns:
        Dict containing:
        - predicted_depth: Theoretical max cascade steps (ceil(log(delta_0/tau) / log(1/rho)))
        - per_path_bound: Total impact bound along any single path (delta_0 / (1-rho))
        - graph_wide_bound: Graph-wide total impact bound (delta_0 / (1 - d*rho)) if converged
        - damping_curve: List of impact values at each depth [0..max_depth]
        - converged: Boolean indicating if d*rho < 1 (graph-wide convergence condition)
    """
    
    # Validate rho for per-path convergence
    if rho >= 1:
        raise ValueError(f"rho must be < 1 for cascade damping, got {rho}")
    
    # Predicted termination depth from Theorem 4.3
    # ceil(log(delta_0/tau) / log(1/rho))
    if delta_0 > 0 and tau > 0:
        predicted_depth = math.ceil(math.log(delta_0 / tau) / math.log(1 / rho))
    else:
        predicted_depth = max_depth
    
    # Per-path bound: delta_0 / (1 - rho)
    per_path_bound = delta_0 / (1 - rho)
    
    # Graph-wide convergence condition from Corollary 4.3.1
    d_rho = max_degree * rho
    converged = d_rho < 1
    
    # Graph-wide bound: delta_0 / (1 - d*rho) when d*rho < 1
    if converged:
        graph_wide_bound = delta_0 / (1 - d_rho)
    else:
        # If not converged, bound is infinite (use None or compute partial sum)
        graph_wide_bound = float('inf')
    
    # Damping curve: impact at each depth j is rho^j * delta_0
    damping_curve = [delta_0 * (rho ** j) for j in range(max_depth + 1)]
    
    return {
        "predicted_depth": predicted_depth,
        "per_path_bound": per_path_bound,
        "graph_wide_bound": graph_wide_bound,
        "damping_curve": damping_curve,
        "converged": converged,
        # Additional useful metrics
        "d_rho": d_rho,
        "rho": rho,
        "tau": tau,
        "delta_0": delta_0
    }


if __name__ == "__main__":
    import json
    
    # Test with specified parameters
    result = cascade_damping_analysis(
        delta_0=1.0,
        rho=0.57,
        tau=0.01,
        max_degree=8,
        max_depth=30
    )
    
    print("=" * 60)
    print("CASCADE DAMPING ANALYSIS (Theorem 4.3 + Corollary 4.3.1)")
    print("=" * 60)
    print(f"\nInput Parameters:")
    print(f"  delta_0 (initial impact): {result['delta_0']}")
    print(f"  rho (damping factor):     {result['rho']}")
    print(f"  tau (threshold):          {result['tau']}")
    print(f"  max_degree (d):           8")
    print(f"  d * rho:                  {result['d_rho']:.3f}")
    
    print(f"\nTheoretical Bounds:")
    print(f"  Predicted cascade depth:  {result['predicted_depth']} steps")
    print(f"  Per-path total bound:     {result['per_path_bound']:.4f}")
    print(f"  Graph-wide bound:         {result['graph_wide_bound']}")
    print(f"  Converged (d*rho < 1):    {result['converged']}")
    
    print(f"\nDamping Curve (first 15 depths):")
    for j, impact in enumerate(result['damping_curve'][:15]):
        bar = "#" * int(impact * 40)
        print(f"  depth {j:2d}: {impact:.6f} {bar}")
    
    print(f"\n  ... (showing {len(result['damping_curve'])} total depths)")
    print(f"  depth {len(result['damping_curve'])-1}: {result['damping_curve'][-1]:.10f}")
