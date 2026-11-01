"""Offline experiment: train linear SVM, tune on validation, evaluate on test.

Run from project root: .venv/Scripts/python.exe trainning/train_classifier.py
No backend import, database writes, or web integration.
"""
from pathlib import Path
import csv
import hashlib
import json
import time

import joblib
import numpy as np
import sklearn
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parent / "artifacts"
UNKNOWN = "unknown"


def load(split):
    with np.load(ROOT / f"{split}_embeddings.npz", allow_pickle=False) as data:
        X, y, paths = data["X"], data["y"], data["paths"]
    if X.ndim != 2 or X.shape[1] != 512 or len(X) == 0:
        raise ValueError(f"{split}: expected nonempty Nx512 embeddings")
    if y.shape != (len(X),) or paths.shape != y.shape:
        raise ValueError(f"{split}: inconsistent labels/paths")
    if not np.isfinite(X).all():
        raise ValueError(f"{split}: non-finite embeddings")
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise ValueError(f"{split}: zero embedding")
    return X / norms, y.astype(str), paths.astype(str)


def metrics(y, predicted):
    known = y != UNKNOWN
    stranger = ~known
    if not known.any() or not stranger.any():
        raise ValueError("Evaluation needs both known and unknown identities")
    known_correct = float(np.mean(predicted[known] == y[known]))
    unknown_recall = float(np.mean(predicted[stranger] == UNKNOWN))
    return {
        "total": len(y), "known_count": int(known.sum()),
        "unknown_count": int(stranger.sum()),
        "correct_count": int(np.sum(predicted == y)),
        "accuracy": float(np.mean(predicted == y)),
        "known_correct_rate": known_correct,
        "known_rejection_rate": float(np.mean(predicted[known] == UNKNOWN)),
        "unknown_false_accept_rate": 1 - unknown_recall,
        "unknown_recall": unknown_recall,
        "balanced_objective": (known_correct + unknown_recall) / 2,
    }


def reject(labels, scores, threshold):
    return np.where(scores >= threshold, labels, UNKNOWN)


def choose_threshold(y, labels, scores):
    # Try every decision boundary on validation, including reject-all.
    thresholds = np.r_[np.unique(scores), np.nextafter(scores.max(), np.inf)]
    choices = []
    for threshold in thresholds:
        result = metrics(y, reject(labels, scores, threshold))
        # Tie: prefer fewer unknown false accepts, then larger threshold.
        key = (result["balanced_objective"], -result["unknown_false_accept_rate"],
               float(threshold))
        choices.append((key, float(threshold), result))
    _, threshold, result = max(choices, key=lambda item: item[0])
    return threshold, result


def svm_scores(model, X):
    scores = model.decision_function(X)
    if scores.ndim == 1:
        scores = np.column_stack([-scores, scores])
    indices = np.argmax(scores, axis=1)
    return model.classes_[indices], scores[np.arange(len(X)), indices]


def cosine_scores(X, classes, centroids):
    scores = X @ centroids.T
    indices = np.argmax(scores, axis=1)
    return classes[indices], scores[np.arange(len(X)), indices]


def main():
    train_X, train_y, _ = load("train")
    val_X, val_y, _ = load("validation")
    classes = np.unique(train_y)
    if UNKNOWN in classes or len(classes) < 2:
        raise ValueError("Train requires at least two known identities, no unknown")
    if not set(val_y) <= set(classes) | {UNKNOWN}:
        raise ValueError("Validation contains an unrecognized label")

    candidates = []
    best = None
    for C in [0.01, 0.1, 1.0, 10.0]:
        model = LinearSVC(C=C, class_weight="balanced", dual=False,
                          max_iter=20000, random_state=42)
        model.fit(train_X, train_y)
        if np.max(model.n_iter_) >= model.max_iter:
            raise RuntimeError("SVM did not converge")
        labels, scores = svm_scores(model, val_X)
        threshold, result = choose_threshold(val_y, labels, scores)
        candidates.append({"C": C, "threshold": threshold, "validation": result})
        key = (result["balanced_objective"], -result["unknown_false_accept_rate"], -C)
        if best is None or key > best[0]:
            best = (key, model, threshold, result, C)
    _, model, svm_threshold, svm_validation, C = best

    # Reference vectors use only train, exactly like the classifier's inputs.
    centroids = np.stack([train_X[train_y == label].mean(axis=0) for label in classes])
    norms = np.linalg.norm(centroids, axis=1, keepdims=True)
    if np.any(norms <= 0):
        raise ValueError("Invalid zero centroid")
    centroids /= norms
    labels, scores = cosine_scores(val_X, classes, centroids)
    cosine_threshold, cosine_validation = choose_threshold(val_y, labels, scores)

    # Freeze both methods BEFORE loading test; no retraining on validation.
    joblib.dump({"model": model, "threshold": svm_threshold, "C": C,
                 "normalized": True, "sklearn_version": sklearn.__version__,
                 "score_type": "max_linear_svm_margin_not_probability"},
                ROOT / "svm_classifier.joblib")
    np.savez_compressed(ROOT / "cosine_reference.npz", classes=classes,
                        centroids=centroids, threshold=cosine_threshold)
    test_X, test_y, paths = load("test")
    if not set(test_y) <= set(classes) | {UNKNOWN}:
        raise ValueError("Test contains an unrecognized label")
    report = {
        "train_count": len(train_y), "sklearn_version": sklearn.__version__,
        "selection": "Maximize mean(known correct rate, unknown rejection rate) on validation; ties favor unknown rejection, then smaller C.",
        "candidates": candidates,
        "input_sha256": {s: hashlib.sha256((ROOT / f"{s}_embeddings.npz").read_bytes()).hexdigest()
                         for s in ["train", "validation", "test"]},
        "limitations": ["Metrics cover successfully extracted faces only.",
                        "Small LFW sample; not an independent classroom evaluation.",
                        "Potential overlap with pretrained model data is not ruled out.",
                        "Timing excludes image loading, detection and embedding extraction.",
                        "SVM margins are not probabilities."],
        "methods": {},
    }
    for name, scorer, threshold, validation in [
        ("svm", lambda X: svm_scores(model, X), svm_threshold, svm_validation),
        ("cosine", lambda X: cosine_scores(X, classes, centroids), cosine_threshold, cosine_validation),
    ]:
        labels, scores = scorer(test_X)
        predicted = reject(labels, scores, threshold)
        # Batch throughput measurement, not full camera latency.
        start = time.perf_counter()
        for _ in range(100):
            scorer(test_X)
        ms = (time.perf_counter() - start) * 1000 / (100 * len(test_X))
        result = metrics(test_y, predicted)
        report["methods"][name] = {"threshold": threshold, "validation": validation,
                                    "test": result, "batch_scoring_ms_per_embedding": ms}
        with (ROOT / f"{name}_test_predictions.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["path", "actual", "predicted", "top_label", "score", "correct"])
            writer.writerows(zip(paths, test_y, predicted, labels, scores, predicted == test_y))
        print(f"{name}: {result['correct_count']}/{len(test_y)} correct; "
              f"unknown false accept={result['unknown_false_accept_rate']:.1%}; threshold={threshold:.4f}")
    report["selected_C"] = C
    (ROOT / "classifier_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved offline experiment to {ROOT}")


if __name__ == "__main__":
    main()
