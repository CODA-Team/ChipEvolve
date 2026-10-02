"""
Bayesian optimization utilities for DRP-Agent.

Provides GPR model creation, acquisition functions, and parameter sampling.
Also includes the ORFO surrogate-modeling helpers (merged from the former
modelfuncs2.py): create_model, create_kernel/preprocessor/acquisition,
predict_with_model, evaluate_*_model, handle_surrogate_data, etc.
"""

import hashlib
import random
import numpy as np
from typing import Any, Callable, Dict, List, Optional, Tuple


def seed_everything(base, *context) -> Optional[int]:
    """Deterministically seed numpy + Python `random` from a base seed and a context
    tuple (e.g. iteration, platform, design, stage). Same (base, context) always maps
    to the same seed, so a whole campaign is reproducible, while different iterations /
    stages / roles still get different streams. Returns the derived int seed.

    base None / "" / "none" -> no-op (nondeterministic), returns None. This is what
    makes the scattered `np.random.randint(0, 10000)` seeds reproducible: once the
    global RNG is seeded here at process start, those draws become deterministic.
    """
    if base in (None, "", "none", "None"):
        return None
    key = "|".join(str(c) for c in ((base,) + context))
    seed = int(hashlib.md5(key.encode()).hexdigest(), 16) % (2 ** 31 - 1)
    np.random.seed(seed)
    random.seed(seed)
    return seed

try:
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import (
        RBF, Matern, WhiteKernel, ConstantKernel, RationalQuadratic, ExpSineSquared,
    )
    from sklearn.preprocessing import StandardScaler, RobustScaler, MinMaxScaler
    from sklearn.cluster import KMeans
    from scipy.stats import norm, qmc
    from scipy.spatial.distance import cdist
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False



def create_gpr_model(kernel_type: str = "rbf") -> Optional["GaussianProcessRegressor"]:
    """Create a Gaussian Process Regressor with specified kernel."""
    if not HAS_SKLEARN:
        return None

    length_scale = 1.0
    length_scale_bounds = (1e-2, 1e2)

    if kernel_type == "rbf":
        base_kernel = RBF(
            length_scale=length_scale,
            length_scale_bounds=length_scale_bounds,
        )
    elif kernel_type == "matern":
        base_kernel = Matern(
            length_scale=length_scale,
            length_scale_bounds=length_scale_bounds,
            nu=2.5,
        )
    else:
        base_kernel = RBF(
            length_scale=length_scale,
            length_scale_bounds=length_scale_bounds,
        )

    kernel = ConstantKernel(1.0, (1e-3, 1e3)) * base_kernel + WhiteKernel(
        noise_level=1e-3, noise_level_bounds=(1e-5, 1e1)
    )

    return GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=5,
        alpha=1e-6,
        normalize_y=True,
    )


def expected_improvement(X_candidate: np.ndarray,
                         gpr: "GaussianProcessRegressor",
                         y_best: float,
                         xi: float = 0.01) -> np.ndarray:
    """
    Compute Expected Improvement acquisition function.

    Args:
        X_candidate: Candidate points, shape (n, d).
        gpr: Fitted GPR model.
        y_best: Best observed objective value (lower is better).
        xi: Exploration-exploitation trade-off parameter.

    Returns:
        EI values, shape (n,).
    """
    from scipy.stats import norm

    mu, sigma = gpr.predict(X_candidate, return_std=True)
    sigma = np.maximum(sigma, 1e-8)

    z = (y_best - mu - xi) / sigma
    ei = (y_best - mu - xi) * norm.cdf(z) + sigma * norm.pdf(z)
    return np.maximum(ei, 0.0)


def upper_confidence_bound(X_candidate: np.ndarray,
                           gpr: "GaussianProcessRegressor",
                           kappa: float = 2.0) -> np.ndarray:
    """Compute UCB acquisition function (lower is better → negate)."""
    mu, sigma = gpr.predict(X_candidate, return_std=True)
    return -(mu - kappa * sigma)


def latin_hypercube_sample(n_samples: int,
                           param_ranges: Dict[str, dict],
                           seed: Optional[int] = None) -> List[Dict[str, float]]:
    """
    Generate Latin Hypercube samples within parameter ranges.

    Args:
        n_samples: Number of samples to generate.
        param_ranges: Dict of param_name -> {"type": ..., "range": [min, max]}.
        seed: Random seed.

    Returns:
        List of dicts, each mapping param_name -> sampled value.
    """
    rng = np.random.RandomState(seed)
    param_names = list(param_ranges.keys())
    n_dims = len(param_names)

    # Latin Hypercube: divide each dimension into n_samples equal intervals
    samples = np.zeros((n_samples, n_dims))
    for dim in range(n_dims):
        perm = rng.permutation(n_samples)
        for i in range(n_samples):
            samples[perm[i], dim] = (i + rng.uniform()) / n_samples

    # Scale to parameter ranges
    result = []
    for i in range(n_samples):
        params = {}
        for j, name in enumerate(param_names):
            info = param_ranges[name]
            lo, hi = info["range"]
            val = lo + samples[i, j] * (hi - lo)
            if info["type"] == "int":
                val = int(round(val))
                val = max(lo, min(hi, val))
            else:
                val = round(val, 4)
            params[name] = val
        result.append(params)

    return result


def perturb_params(base_params: Dict[str, float],
                   param_ranges: Dict[str, dict],
                   perturbation_factor: float = 0.1,
                   seed: Optional[int] = None) -> Dict[str, float]:
    """
    Perturb parameters by a small factor around base values.

    Args:
        base_params: Base parameter values.
        param_ranges: Parameter constraints with ranges.
        perturbation_factor: Fraction of range to perturb (e.g., 0.1 = ±10%).
        seed: Random seed.

    Returns:
        Perturbed parameter dict.
    """
    rng = np.random.RandomState(seed)
    result = {}

    for name, info in param_ranges.items():
        lo, hi = info["range"]
        base_val = base_params.get(name, (lo + hi) / 2)
        range_span = hi - lo
        delta = rng.uniform(-perturbation_factor, perturbation_factor) * range_span
        new_val = base_val + delta

        if info["type"] == "int":
            new_val = int(round(new_val))
        else:
            new_val = round(new_val, 4)

        new_val = max(lo, min(hi, new_val))
        result[name] = new_val

    return result


def bayesian_suggest(X_observed: np.ndarray,
                     y_observed: np.ndarray,
                     param_ranges: Dict[str, dict],
                     n_suggestions: int,
                     n_candidates: int = 1000,
                     kernel_type: str = "rbf",
                     seed: Optional[int] = None,
                     acquisition: str = "ei") -> List[Dict[str, float]]:
    """
    Use Bayesian optimization (GPR + a configurable acquisition) to suggest next
    parameter sets.

    Args:
        X_observed: Observed parameter values, shape (n_obs, n_params).
        y_observed: Observed objective values, shape (n_obs,).
        param_ranges: Parameter constraints.
        n_suggestions: Number of suggestions to return.
        n_candidates: Number of random candidates to evaluate.
        kernel_type: GPR kernel type.
        seed: Random seed.
        acquisition: 'ei' | 'ucb' | 'pi' — ranks the candidates (was hard-coded EI,
            which made the agentic acquisition choice a no-op).

    Returns:
        List of suggested parameter dicts.
    """
    if not HAS_SKLEARN:
        # Fallback: Latin Hypercube sampling
        return latin_hypercube_sample(n_suggestions, param_ranges, seed)

    rng = np.random.RandomState(seed)

    # Fit GPR
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_observed)

    gpr = create_gpr_model(kernel_type)
    try:
        gpr.fit(X_scaled, y_observed)
    except Exception:
        return latin_hypercube_sample(n_suggestions, param_ranges, seed)

    # Generate random candidates
    candidates = latin_hypercube_sample(n_candidates, param_ranges, seed)
    param_names = list(param_ranges.keys())
    X_candidates = np.array([[c[p] for p in param_names] for c in candidates])
    X_candidates_scaled = scaler.transform(X_candidates)

    # Compute the configured acquisition (higher = better) over the candidates.
    y_best = np.min(y_observed)
    mu, std = gpr.predict(X_candidates_scaled, return_std=True)
    acq_fn = create_acquisition_function(acquisition)
    acq_values = np.asarray(acq_fn(np.asarray(mu, dtype=float),
                                   np.asarray(std, dtype=float),
                                   float(y_best)), dtype=float)

    # Select top suggestions
    top_indices = np.argsort(acq_values)[::-1][:n_suggestions]
    return [candidates[i] for i in top_indices]


def params_to_array(params_list: List[Dict], param_names: List[str]) -> np.ndarray:
    """Convert list of param dicts to numpy array."""
    return np.array([[p.get(n, 0) for n in param_names] for p in params_list])


def clip_params(params: Dict[str, float], param_ranges: Dict[str, dict]) -> Dict[str, float]:
    """Clip parameter values while preserving candidate provenance metadata."""
    result = {}
    for name, info in param_ranges.items():
        lo, hi = info["range"]
        val = params.get(name, (lo + hi) / 2)
        if info["type"] == "int":
            val = int(round(val))
        val = max(lo, min(hi, val))
        result[name] = val
    for name in ("_candidate_id", "_candidate_origin", "_candidate_parent"):
        if name in params:
            result[name] = params[name]
    return result


# ===========================================================================
# Merged from the former modelfuncs2.py (ORFO surrogate-modeling helpers).
# NOTE: ORFO's mu/std expected_improvement was renamed -> expected_improvement_mu_std
# to avoid clashing with the DRP expected_improvement(X_candidate, gpr, y_best) above.
# ===========================================================================

def latin_hypercube(n_points, n_dims):
    """Generate Latin Hypercube samples"""
    sampler = qmc.LatinHypercube(d=n_dims)
    return sampler.random(n=n_points)

def parse_llm_response(llm_response: str) -> Dict[str, Any]:
    """Parse the LLM's response into structured recommendations"""
    # This would need to be adapted based on your actual LLM's output format
    # For now, assuming a structured response that can be parsed
    try:
        # Example parsing - adapt based on actual LLM response format
        recommendations = {
            "kernel": llm_response.split("Kernel choice:")[1].split("\n")[0].strip(),
            "preprocessing": llm_response.split("Preprocessing:")[1].split("\n")[0].strip(),
            "acquisition": llm_response.split("Acquisition:")[1].split("\n")[0].strip(),
            "missing_values": llm_response.split("Missing values:")[1].split("\n")[0].strip(),
            "surrogate": llm_response.split("Surrogate:")[1].split("\n")[0].strip()
        }
        return recommendations
    except:
        # Fallback to default recommendations
        return {
            "kernel": "matern",
            "preprocessing": "standard",
            "acquisition": "ei",
            "missing_values": "surrogate_fill",
            "surrogate": "weighted_combination"
        }

def create_kernel(kernel_spec: str, input_dim: int) -> Any:
    """Create a kernel based on recommendations"""
    # Define length scale bounds
    ls_bounds = (1e-2, 1e2)  # More conservative bounds
    
    base_kernels = {
        "rbf": RBF(length_scale=[1.0] * input_dim, length_scale_bounds=[ls_bounds] * input_dim),
        "matern": Matern(length_scale=[1.0] * input_dim, length_scale_bounds=[ls_bounds] * input_dim, nu=2.5),
        "rational": RationalQuadratic(length_scale=[1.0] * input_dim, length_scale_bounds=[ls_bounds] * input_dim, alpha=1.0),
        "composite": Matern(length_scale=[1.0] * input_dim, length_scale_bounds=[ls_bounds] * input_dim, nu=2.5)
    }
    
    # Default to Matern kernel if specification not recognized
    base_kernel = base_kernels.get(kernel_spec.lower(), base_kernels["matern"])
    
    # Add noise term with adaptive scaling
    noise_kernel = WhiteKernel(noise_level=1e-5, noise_level_bounds=(1e-10, 1e1))
    kernel = ConstantKernel(1.0, constant_value_bounds=(1e-5, 1e5)) * base_kernel + noise_kernel
    
    return kernel

def create_preprocessor(preprocess_spec: str) -> Any:
    """Create a preprocessor based on recommendations"""
    preprocessors = {
        "standard": StandardScaler(),
        "robust": RobustScaler(),
        "minmax": MinMaxScaler(),   # was missing: 'minmax' silently fell back to standard
        "none": None
    }
    return preprocessors.get(preprocess_spec.lower(), preprocessors["standard"])

def create_acquisition_function(acq_spec: str) -> Callable:
    """Create an acquisition function based on recommendations"""
    def expected_improvement(mean, std, best_f):
        with np.errstate(divide='warn'):
            # Add small epsilon to std to prevent division by zero
            std = np.maximum(std, 1e-9)
            z = (best_f - mean) / std
            return std * (z * norm.cdf(z) + norm.pdf(z))
    
    def upper_confidence_bound(mean, std, best_f, beta=2.0):
        # Lower confidence bound for minimization, negated so higher = better
        return -(mean - beta * std)
    
    def probability_improvement(mean, std, best_f, xi=0.01):
        # Add exploration bonus xi
        std = np.maximum(std, 1e-9)
        z = (best_f - mean - xi) / std
        return norm.cdf(z)
    
    def augmented_ei(mean, std, best_f, xi=0.01, alpha=0.5):
        # Combine EI with PI for better exploration
        ei = expected_improvement(mean, std, best_f)
        pi = probability_improvement(mean, std, best_f, xi)
        return alpha * ei + (1 - alpha) * pi
    
    acquisitions = {
        "ei": expected_improvement,
        "ucb": upper_confidence_bound,
        "pi": probability_improvement,
        "augmented_ei": augmented_ei
    }
    return acquisitions.get(acq_spec.lower(), acquisitions["augmented_ei"])

def create_model(X, y, noise_level=1e-6, kernel_type="matern", preprocessing="standard", feature_weights=None):
    """Create and configure a Gaussian Process model with improved features"""
    n_features = X.shape[1]

    # Handle case with no or insufficient data points
    if len(X) < 2:
        print("Warning: Insufficient data points for modeling. Creating dummy model.")
        # Return a simple model that will encourage exploration
        kernel = 1.0 * RBF(length_scale=[1.0] * n_features)
        model = GaussianProcessRegressor(
            kernel=kernel,
            normalize_y=True,
            random_state=42
        )
        # Fit with dummy data to enable predictions
        X_dummy = np.vstack([X, X + 0.1])  # Add slightly offset point
        y_dummy = np.array([y[0], y[0]])   # Duplicate the single y value
        model.fit(X_dummy, y_dummy)
        model.scaler_ = create_preprocessor(preprocessing) or StandardScaler()
        model.scaler_.fit(X_dummy)
        return model

    # Scale the input features using the configured preprocessor
    scaler = create_preprocessor(preprocessing)
    if scaler is not None:
        X_scaled = scaler.fit_transform(X)
    else:
        # preprocessing="none": no scaling, but store an identity-like scaler for predict_with_model
        scaler = StandardScaler(with_mean=False, with_std=False)
        X_scaled = scaler.fit_transform(X)
    
    # Use provided feature weights if available, otherwise compute from data
    if feature_weights is not None and len(feature_weights) == n_features:
        correlations = np.array(feature_weights, dtype=float)
    else:
        correlations = np.zeros(n_features)
        if len(y) > 1:  # Only compute correlations if we have enough points
            correlations = np.array([np.abs(np.corrcoef(X[:, i], y)[0, 1]) for i in range(n_features)])
    important_features = correlations > np.mean(correlations)

    # Create adaptive length scales based on feature importance
    length_scales = np.ones(n_features)
    length_scales[important_features] = 0.5  # Shorter length scales for important features
    
    # Create adaptive bounds based on data scale
    ls_bounds = (1e-2, 1e2)  # More conservative bounds
    
    # Create base kernel
    if kernel_type == "matern":
        kernel = Matern(length_scale=length_scales, length_scale_bounds=[ls_bounds] * n_features, nu=2.5)
    elif kernel_type == "rbf":
        kernel = RBF(length_scale=length_scales, length_scale_bounds=[ls_bounds] * n_features)
    elif kernel_type == "rational":
        kernel = RationalQuadratic(length_scale=length_scales, length_scale_bounds=[ls_bounds] * n_features, alpha=1.0)
    else:
        # For composite, use Matern with optimized parameters
        kernel = Matern(length_scale=length_scales, length_scale_bounds=[ls_bounds] * n_features, nu=2.5)
    
    # Add noise term with adaptive scaling
    y_std = np.std(y) if len(y) > 1 else 1.0
    noise_level = max(noise_level, 1e-6 * y_std)
    kernel = kernel + WhiteKernel(noise_level=noise_level, noise_level_bounds=(1e-10 * y_std, 1e-2 * y_std))
    
    # Create GP model with increased optimization
    model = GaussianProcessRegressor(
        kernel=kernel,
        n_restarts_optimizer=10,  # Increased from 5
        normalize_y=True,
        random_state=42
    )
    
    # Fit the model
    try:
        model.fit(X_scaled, y)
    except Exception as e:
        print(f"Warning: Error fitting model: {str(e)}. Creating simpler model.")
        # Fall back to simpler kernel if fitting fails
        simple_kernel = 1.0 * RBF(length_scale=[1.0] * n_features)
        model = GaussianProcessRegressor(
            kernel=simple_kernel,
            normalize_y=True,
            random_state=42
        )
        model.fit(X_scaled, y)
    
    # Store scaler for future predictions
    model.scaler_ = scaler
    
    return model

def handle_surrogate_data(X, y, surrogate_values):
    """Process and combine true and surrogate data with improved uncertainty handling"""
    if surrogate_values is None:
        return X, y
    
    # Identify valid and missing data points
    valid_mask = ~np.isnan(y)
    missing_mask = ~valid_mask
    
    # Calculate uncertainty in surrogate values based on data range
    if np.any(valid_mask):
        y_range = np.max(y[valid_mask]) - np.min(y[valid_mask])
        surrogate_uncertainty = 0.1 * y_range  # 10% of range
    else:
        surrogate_uncertainty = 1.0
    
    # Create weighted combination
    y_combined = y.copy()
    y_combined[missing_mask] = surrogate_values[missing_mask]
    
    # Add uncertainty information
    uncertainty = np.zeros_like(y)
    uncertainty[missing_mask] = surrogate_uncertainty
    
    return X, y_combined, uncertainty

def expected_improvement_mu_std(mu, std, y_best, xi=0.01):
    """Calculate expected improvement acquisition function with improved numerical stability"""
    mu = mu.reshape(-1, 1)
    sigma = std.reshape(-1, 1)
    
    # Add small epsilon to prevent division by zero
    sigma = np.maximum(sigma, 1e-9)
    
    # Calculate improvement
    imp = y_best - mu - xi
    
    # Calculate Z-score
    Z = imp / sigma
    
    # Calculate expected improvement
    ei = imp * norm.cdf(Z) + sigma * norm.pdf(Z)
    ei[sigma < 1e-10] = 0
    
    return ei.ravel()

def evaluate_timing_model(context: dict) -> dict:
    """Evaluate timing model performance with improved analysis"""
    model_results = {
        'performance': {},
        'suggestions': []
    }
    
    # Extract data
    log_data = context.get('log_data', {})
    metrics = context.get('metrics', {})
    model_recommendations = context.get('model_recommendations', {})
    
    # Check data availability
    if not metrics.get('objectives'):
        model_results['suggestions'].append(
            "No timing data available yet. Using default model configuration.")
        return model_results
        
    # Analyze timing correlations with improved metrics
    correlations = metrics.get('correlations', {})
    if correlations.get('real_vs_surrogate'):
        real = np.asarray([x['real'] for x in correlations['real_vs_surrogate']], dtype=float)
        surrogate = np.asarray([x['surrogate'] for x in correlations['real_vs_surrogate']], dtype=float)
        if len(real) > 1 and np.std(real) > 0 and np.std(surrogate) > 0:
            surrogate_correlation = float(np.corrcoef(real, surrogate)[0, 1])
            model_results['performance']['surrogate_correlation'] = surrogate_correlation

            abs_gap = float(np.mean(np.abs(real - surrogate)))
            model_results['performance']['surrogate_abs_gap'] = abs_gap
            
            if surrogate_correlation > 0.8:
                model_results['suggestions'].append(
                    "Strong surrogate correlation - increase surrogate weight")
            elif surrogate_correlation < 0.5:
                model_results['suggestions'].append(
                    "Weak surrogate correlation - reduce surrogate weight")

            if abs_gap > max(0.05, 0.5 * np.std(real)):
                model_results['suggestions'].append(
                    "Timing surrogate gap is large; validate more runs with final timing metrics.")
    
    # Add model recommendations from structure analysis
    if model_recommendations:
        model_results['recommendations'] = model_recommendations
        rec_kernel = model_recommendations.get('kernel_type', '')
        if rec_kernel and rec_kernel != 'matern':
            model_results['suggestions'].append(
                f"Data analysis suggests '{rec_kernel}' kernel may fit better than default Matern.")
        if model_recommendations.get('needs_local_models', False):
            model_results['suggestions'].append(
                "Cluster differences detected; consider local surrogate models.")
        if model_recommendations.get('use_feature_weights', False):
            model_results['suggestions'].append(
                "Feature importance varies significantly; weighted length scales recommended.")

    return model_results

def evaluate_wirelength_model(context: dict) -> dict:
    """Evaluate wirelength model performance with improved analysis"""
    model_results = {
        'performance': {},
        'suggestions': []
    }
    
    # Extract data
    log_data = context.get('log_data', {})
    metrics = context.get('metrics', {})
    model_recommendations = context.get('model_recommendations', {})
    
    # Check data availability
    if not metrics.get('objectives'):
        model_results['suggestions'].append(
            "No wirelength data available yet. Using default model configuration.")
        return model_results
        
    # Analyze wirelength progression with improved metrics
    wl_progression = metrics.get('wirelength_progression', [])
    if wl_progression:
        # Calculate average ratio between final and CTS wirelength
        ratios = [p['final'] / p['cts'] for p in wl_progression if p['cts'] > 0]
        if ratios:
            avg_ratio = sum(ratios) / len(ratios)
            model_results['performance']['cts_to_final_ratio'] = avg_ratio
            
            if avg_ratio > 1.5:
                model_results['suggestions'].append(
                    "Large increase in wirelength after CTS - reduce surrogate weight")
            elif avg_ratio < 1.2:
                model_results['suggestions'].append(
                    "CTS wirelength is good predictor - increase surrogate weight")
    
    # Add model recommendations from structure analysis
    if model_recommendations:
        model_results['recommendations'] = model_recommendations
        rec_kernel = model_recommendations.get('kernel_type', '')
        if rec_kernel and rec_kernel != 'matern':
            model_results['suggestions'].append(
                f"Data analysis suggests '{rec_kernel}' kernel may fit better than default Matern.")
        if model_recommendations.get('needs_local_models', False):
            model_results['suggestions'].append(
                "Cluster differences detected; consider local surrogate models.")
        if model_recommendations.get('use_feature_weights', False):
            model_results['suggestions'].append(
                "Feature importance varies significantly; weighted length scales recommended.")

    return model_results

def evaluate_combo_model(context: dict) -> dict:
    """Evaluate combined ECP/WL objective behavior using normalized combo labels."""
    model_results = {
        'performance': {},
        'suggestions': []
    }

    metrics = context.get('metrics', {})
    model_recommendations = context.get('model_recommendations', {})

    objectives = metrics.get('objectives', [])
    surrogates = metrics.get('surrogates', [])
    if not objectives:
        model_results['suggestions'].append(
            "No COMBO objective data available yet. Using default model configuration.")
        return model_results

    valid_objectives = np.asarray(objectives, dtype=float)
    model_results['performance']['combo_mean'] = float(np.mean(valid_objectives))
    model_results['performance']['combo_std'] = float(np.std(valid_objectives))
    model_results['performance']['combo_best'] = float(np.min(valid_objectives))
    model_results['performance']['n_objective_samples'] = int(len(valid_objectives))

    # Since the COMBO label is a baseline-normalized minimization objective,
    # negative values indicate improvement relative to baseline.
    improved_ratio = float(np.mean(valid_objectives < 0))
    model_results['performance']['improved_ratio'] = improved_ratio
    if improved_ratio > 0.5:
        model_results['suggestions'].append(
            "More than half of COMBO samples beat baseline; tighten local search around strong regions.")
    elif improved_ratio < 0.1:
        model_results['suggestions'].append(
            "Few COMBO samples beat baseline; increase exploration and revisit parameter ranges.")

    if surrogates:
        valid_surrogates = np.asarray(surrogates, dtype=float)
        model_results['performance']['combo_surrogate_mean'] = float(np.mean(valid_surrogates))
        model_results['performance']['combo_surrogate_std'] = float(np.std(valid_surrogates))

    correlations = metrics.get('correlations', {})
    if correlations.get('real_vs_surrogate'):
        real = np.asarray([x['real'] for x in correlations['real_vs_surrogate']], dtype=float)
        surrogate = np.asarray([x['surrogate'] for x in correlations['real_vs_surrogate']], dtype=float)
        if len(real) > 1 and np.std(real) > 0 and np.std(surrogate) > 0:
            surrogate_corr = float(np.corrcoef(real, surrogate)[0, 1])
            model_results['performance']['surrogate_correlation'] = surrogate_corr

            abs_gap = float(np.mean(np.abs(real - surrogate)))
            model_results['performance']['surrogate_abs_gap'] = abs_gap

            if surrogate_corr > 0.8:
                model_results['suggestions'].append(
                    "COMBO surrogate tracks final objective well; trust proxy-guided exploitation more.")
            elif surrogate_corr < 0.5:
                model_results['suggestions'].append(
                    "COMBO surrogate is weakly aligned with final objective; emphasize exploration and final-metric validation.")

            if abs_gap > max(0.05, 0.5 * np.std(real)):
                model_results['suggestions'].append(
                    "The COMBO surrogate gap is large; avoid over-committing to CTS-driven signals.")

    distribution = metrics.get('distribution_analysis', {})
    y_missing_ratio = distribution.get('y_missing_ratio')
    if y_missing_ratio is not None:
        model_results['performance']['y_missing_ratio'] = float(y_missing_ratio)
        if y_missing_ratio > 0.3:
            model_results['suggestions'].append(
                "Many final COMBO labels are missing; surrogate fallback is active often, so diversify candidates.")

    if model_recommendations:
        model_results['recommendations'] = model_recommendations
        rec_kernel = model_recommendations.get('kernel_type', '')
        if rec_kernel and rec_kernel != 'matern':
            model_results['suggestions'].append(
                f"Data analysis suggests '{rec_kernel}' kernel may fit better than default Matern.")
        if model_recommendations.get('needs_local_models', False):
            model_results['suggestions'].append(
                "Cluster differences detected; consider local surrogate models.")
        if model_recommendations.get('use_feature_weights', False):
            model_results['suggestions'].append(
                "Feature importance varies significantly; weighted length scales recommended.")

    return model_results

def predict_with_model(model, X_new):
    """Make predictions with proper scaling"""
    X_scaled = model.scaler_.transform(X_new)
    return model.predict(X_scaled, return_std=True)
