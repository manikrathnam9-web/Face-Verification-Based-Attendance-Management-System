import os
import sys
import numpy as np

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# ==================================================
# ACTUAL EXPERIMENTAL SCORES
# ==================================================

# Genuine = same person as DS001
genuine_scores = np.array([
    0.5809,
    0.6248,
    0.6419,
    0.6143
])

# Impostor = different person
impostor_scores = np.array([
    0.1459
])


# ==================================================
# FAR / FRR
# ==================================================

def calculate_far(scores, threshold):
    """
    False Acceptance Rate:
    percentage of impostor attempts accepted.
    """
    false_accepts = np.sum(scores >= threshold)
    return float(false_accepts / len(scores))


def calculate_frr(scores, threshold):
    """
    False Rejection Rate:
    percentage of genuine attempts rejected.
    """
    false_rejects = np.sum(scores < threshold)
    return float(false_rejects / len(scores))


def run_threshold_evaluation():
    thresholds = np.arange(0.10, 0.71, 0.01)
    results = []

    for threshold in thresholds:
        far = calculate_far(impostor_scores, threshold)
        frr = calculate_frr(genuine_scores, threshold)
        results.append({
            "threshold": round(float(threshold), 2),
            "far": far,
            "frr": frr
        })

    print("\n========================================")
    print("FAR / FRR THRESHOLD EVALUATION")
    print("========================================")
    print(f"{'Threshold':<12}{'FAR':<12}{'FRR':<12}")
    print("----------------------------------------")

    sample_thresholds = {
        0.20, 0.30, 0.40, 0.50, 0.55, 0.58,
        0.59, 0.60, 0.61, 0.62, 0.63, 0.64, 0.65, 0.70
    }

    for result in results:
        threshold = result["threshold"]
        if threshold in sample_thresholds:
            print(f"{threshold:<12.2f}{result['far']:<12.2%}{result['frr']:<12.2%}")

    zero_far_results = [r for r in results if r["far"] == 0]

    print("\n========================================")
    print("ZERO-FAR THRESHOLDS")
    print("========================================")
    if zero_far_results:
        for result in zero_far_results:
            print(f"Threshold {result['threshold']:.2f} -> FAR {result['far']:.2%}, FRR {result['frr']:.2%}")
    else:
        print("No zero-FAR threshold found.")
    print("========================================")

    return results


if __name__ == "__main__":
    run_threshold_evaluation()
