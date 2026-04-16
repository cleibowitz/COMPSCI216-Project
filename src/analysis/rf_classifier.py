"""
Random Forest Classifier for Mean-Reversion Prediction
======================================================

Binary target: does the 5Y OIS-Treasury spread mean-revert by ≥3bps
within 10 business days of a |z|>2 signal event?

Train: 2019-01-01 → 2023-12-31 (falls back to 2023-06-30 if test
fold is too small). Test: remainder of sample.

Compares:
  - RandomForestClassifier (primary)
  - LogisticRegression baseline
  - Majority-class naive baseline

Also tests whether hmm_state adds predictive value beyond
rate_regime alone.
"""

from pathlib import Path
from typing import Dict

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, classification_report, confusion_matrix,
    f1_score, precision_score, recall_score, roc_auc_score,
    roc_curve,
)
from sklearn.preprocessing import StandardScaler

from src.analysis.stats_utils import (
    compute_z_scores, extract_signal_events,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIGURES_DIR = PROJECT_ROOT / "outputs" / "figures"
ML_DIR = PROJECT_ROOT / "outputs" / "ml"

WINDOW = 60
THRESHOLD = 2.0
HORIZON = 10
MIN_GAP = 5
REVERSION_BPS = 3.0  # minimum move-toward-zero (in bps) to count as reversion

TRAIN_END_PRIMARY = pd.Timestamp("2023-12-31")
TRAIN_END_FALLBACK = pd.Timestamp("2023-06-30")

FEATURE_COLS = [
    "zscore_5y", "zscore_10y", "move_level", "move_zscore",
    "effr_change_60d", "rate_regime", "hmm_state",
    "spread_5y_lag5", "spread_5y_lag10", "signal_direction",
]


# ---------------------------------------------------------------------------
# Dataset construction
# ---------------------------------------------------------------------------

def _build_event_dataset(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the (events × features + target) table.

    Signal events are |z_5y| > 2, non-overlapping with min_gap=5.
    """
    df_z = compute_z_scores(df, window=WINDOW)

    # Rolling 60-day z-score for MOVE
    move = df_z["MOVE"]
    move_mu = move.rolling(60, min_periods=60).mean()
    move_sd = move.rolling(60, min_periods=60).std()
    df_z["move_zscore"] = (move - move_mu) / move_sd

    # 60-day EFFR change
    df_z["effr_change_60d"] = df_z["EFFR"].diff(60)

    # Lagged spread changes (backward-looking)
    df_z["spread_5y_lag5"] = df_z["spread_5y"] - df_z["spread_5y"].shift(5)
    df_z["spread_5y_lag10"] = df_z["spread_5y"] - df_z["spread_5y"].shift(10)

    events: list[dict] = []
    spread = df_z["spread_5y"].values
    n = len(spread)

    for direction, sign in [("positive", +1), ("negative", -1)]:
        _, positions = extract_signal_events(
            df_z, "spread_5y", "z_5y", THRESHOLD, direction,
            HORIZON, min_gap=MIN_GAP,
        )
        for p in positions:
            if p + HORIZON >= n:
                continue
            v0 = spread[p]
            window = spread[p:p + HORIZON + 1]
            if not np.all(np.isfinite(window)):
                continue

            # Reversion = movement toward zero by ≥ REVERSION_BPS (in pp = 0.03)
            # For z>+2 (spread high): look for any value_h where v0 - v_h >= 0.03
            # For z<-2 (spread low):  look for any value_h where v_h - v0 >= 0.03
            if sign > 0:
                reverts = bool(np.any(v0 - window[1:] >= REVERSION_BPS / 100.0))
            else:
                reverts = bool(np.any(window[1:] - v0 >= REVERSION_BPS / 100.0))

            date = df_z.index[p]
            row = {
                "date": date,
                "position": p,
                "signal_direction": sign,
                "target_5y_10d": int(reverts),
                "zscore_5y": df_z["z_5y"].iat[p],
                "zscore_10y": df_z["z_10y"].iat[p],
                "move_level": df_z["MOVE"].iat[p],
                "move_zscore": df_z["move_zscore"].iat[p],
                "effr_change_60d": df_z["effr_change_60d"].iat[p],
                "rate_regime": df_z["rate_regime"].iat[p],
                "hmm_state": df_z["hmm_state"].iat[p],
                "spread_5y_lag5": df_z["spread_5y_lag5"].iat[p],
                "spread_5y_lag10": df_z["spread_5y_lag10"].iat[p],
            }
            events.append(row)

    out = pd.DataFrame(events).dropna(subset=FEATURE_COLS + ["target_5y_10d"])
    out = out.sort_values("date").reset_index(drop=True)
    return out


# ---------------------------------------------------------------------------
# Train/test split with fallback
# ---------------------------------------------------------------------------

def _time_split(events: pd.DataFrame):
    train = events[events["date"] <= TRAIN_END_PRIMARY]
    test = events[events["date"] > TRAIN_END_PRIMARY]
    cutoff = TRAIN_END_PRIMARY
    if len(test) < 15:
        print(f"  Primary test set has only {len(test)} events — "
              f"widening training cutoff to {TRAIN_END_FALLBACK.date()}")
        train = events[events["date"] <= TRAIN_END_FALLBACK]
        test = events[events["date"] > TRAIN_END_FALLBACK]
        cutoff = TRAIN_END_FALLBACK
    return train, test, cutoff


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def _report_metrics(name: str, y_true, y_pred, y_prob=None) -> dict:
    metrics = {
        "model": name,
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "roc_auc": (roc_auc_score(y_true, y_prob)
                    if y_prob is not None and len(np.unique(y_true)) > 1
                    else np.nan),
    }
    print(f"  {name:20s}  acc={metrics['accuracy']:.3f}  "
          f"prec={metrics['precision']:.3f}  rec={metrics['recall']:.3f}  "
          f"f1={metrics['f1']:.3f}  auc={metrics['roc_auc']:.3f}")
    return metrics


def _plot_roc(results: Dict[str, tuple]) -> None:
    fig, ax = plt.subplots(figsize=(6.5, 6))
    for name, (y_true, y_prob) in results.items():
        if y_prob is None or len(np.unique(y_true)) < 2:
            continue
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        auc = roc_auc_score(y_true, y_prob)
        ax.plot(fpr, tpr, linewidth=1.7, label=f"{name} (AUC={auc:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="gray", linewidth=0.8,
            label="Chance")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC curves — test set")
    ax.legend(loc="lower right")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = FIGURES_DIR / "rf_roc.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def _plot_confusion(y_true, y_pred, title: str, fname: str) -> None:
    cm = confusion_matrix(y_true, y_pred, labels=[0, 1])
    fig, ax = plt.subplots(figsize=(4.5, 4))
    im = ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["no reversion", "reversion"])
    ax.set_yticklabels(["no reversion", "reversion"])
    ax.set_xlabel("Predicted"); ax.set_ylabel("Actual")
    ax.set_title(title)
    for i in range(2):
        for j in range(2):
            ax.text(j, i, str(cm[i, j]), ha="center", va="center",
                    fontsize=13,
                    color="white" if cm[i, j] > cm.max() / 2 else "black")
    fig.colorbar(im, ax=ax)
    fig.tight_layout()
    out = FIGURES_DIR / fname
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def _plot_feature_importance(model: RandomForestClassifier,
                             feature_names) -> None:
    importances = pd.Series(model.feature_importances_,
                            index=feature_names).sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(importances.index, importances.values, color="steelblue",
            edgecolor="black")
    ax.set_xlabel("Mean decrease in impurity")
    ax.set_title("Random Forest feature importance")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    out = FIGURES_DIR / "rf_importance.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out.name}")


def _plot_shap(model: RandomForestClassifier, X_test: pd.DataFrame) -> None:
    try:
        import shap
    except ImportError:
        print("  shap not available — skipping SHAP plot.")
        return
    try:
        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_test)
        # For binary classifiers, pick class-1 SHAP values
        if isinstance(shap_values, list):
            sv = shap_values[1]
        elif shap_values.ndim == 3:
            sv = shap_values[:, :, 1]
        else:
            sv = shap_values

        fig = plt.figure(figsize=(8, 5))
        shap.summary_plot(sv, X_test, show=False, plot_size=None)
        out = FIGURES_DIR / "rf_shap.png"
        plt.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved {out.name}")
    except Exception as e:
        print(f"  SHAP failed: {e}")


# ---------------------------------------------------------------------------
# HMM ablation
# ---------------------------------------------------------------------------

def _hmm_ablation(X_train, y_train, X_test, y_test) -> None:
    """
    Compare test AUC with vs without hmm_state in the feature set,
    keeping rate_regime in both — directly tests whether HMM adds value.
    """
    print("\n--- HMM ablation test (does hmm_state add value?) ---")
    feats_with = FEATURE_COLS
    feats_without = [c for c in FEATURE_COLS if c != "hmm_state"]

    def _auc(feats):
        rf = RandomForestClassifier(
            n_estimators=500, max_depth=4, min_samples_leaf=5,
            random_state=42, n_jobs=-1,
        )
        rf.fit(X_train[feats], y_train)
        prob = rf.predict_proba(X_test[feats])[:, 1]
        return (roc_auc_score(y_test, prob)
                if len(np.unique(y_test)) > 1 else np.nan)

    auc_with = _auc(feats_with)
    auc_without = _auc(feats_without)
    print(f"  RF test AUC with hmm_state   : {auc_with:.3f}")
    print(f"  RF test AUC without hmm_state: {auc_without:.3f}")
    diff = auc_with - auc_without
    if diff > 0.02:
        print(f"  → hmm_state adds predictive value (ΔAUC = +{diff:.3f})")
    elif diff < -0.02:
        print(f"  → hmm_state HURTS performance (ΔAUC = {diff:.3f})")
    else:
        print(f"  → hmm_state is effectively redundant (ΔAUC = {diff:+.3f})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run_rf(df: pd.DataFrame) -> Dict[str, object]:
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    ML_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("Random Forest: mean-reversion classification at 5Y, h=10d")
    print("=" * 60)

    events = _build_event_dataset(df)
    print(f"  Total signal events with full features: {len(events)}")
    base_rate = events["target_5y_10d"].mean()
    print(f"  Overall reversion rate: {100 * base_rate:.1f}%")

    train, test, cutoff = _time_split(events)
    print(f"  Train: {len(train)} events (≤ {cutoff.date()})  "
          f"| Test: {len(test)} events")
    print(f"  Train reversion rate: {100 * train['target_5y_10d'].mean():.1f}%  "
          f"| Test reversion rate: {100 * test['target_5y_10d'].mean():.1f}%")

    X_train, y_train = train[FEATURE_COLS], train["target_5y_10d"].values
    X_test, y_test = test[FEATURE_COLS], test["target_5y_10d"].values

    # --- Random Forest ---
    rf = RandomForestClassifier(
        n_estimators=500, max_depth=4, min_samples_leaf=5,
        random_state=42, n_jobs=-1,
    )
    rf.fit(X_train, y_train)
    rf_pred = rf.predict(X_test)
    rf_prob = rf.predict_proba(X_test)[:, 1]

    # --- Logistic Regression baseline (standardized features) ---
    scaler = StandardScaler()
    Xs_train = scaler.fit_transform(X_train)
    Xs_test = scaler.transform(X_test)
    logit = LogisticRegression(max_iter=1000, random_state=42)
    logit.fit(Xs_train, y_train)
    logit_pred = logit.predict(Xs_test)
    logit_prob = logit.predict_proba(Xs_test)[:, 1]

    # --- Naive baseline: majority class from train ---
    majority = int(round(train["target_5y_10d"].mean()))
    naive_pred = np.full(len(y_test), majority)
    naive_prob = np.full(len(y_test), train["target_5y_10d"].mean())

    print("\n--- Test-set metrics ---")
    all_metrics = []
    all_metrics.append(_report_metrics("RandomForest", y_test, rf_pred, rf_prob))
    all_metrics.append(_report_metrics("LogisticRegression", y_test, logit_pred, logit_prob))
    all_metrics.append(_report_metrics("Naive (majority)", y_test, naive_pred, naive_prob))

    metrics_df = pd.DataFrame(all_metrics)
    metrics_df.to_csv(ML_DIR / "rf_metrics.csv", index=False)

    # --- Plots ---
    _plot_roc({
        "RandomForest": (y_test, rf_prob),
        "LogisticRegression": (y_test, logit_prob),
    })
    _plot_confusion(y_test, rf_pred,
                    "Confusion matrix — RandomForest (test)",
                    "rf_confusion.png")
    _plot_feature_importance(rf, FEATURE_COLS)
    _plot_shap(rf, X_test)

    # --- HMM ablation ---
    _hmm_ablation(X_train, y_train, X_test, y_test)

    # --- Save model + events ---
    joblib.dump(rf, ML_DIR / "rf_model.pkl")
    print(f"\n  Saved fitted RF to outputs/ml/rf_model.pkl")
    events.to_csv(ML_DIR / "rf_events.csv", index=False)
    print(f"  Saved event table to outputs/ml/rf_events.csv ({len(events)} rows)")

    # --- Summary ---
    print("\nPlain-English summary:")
    rf_auc = all_metrics[0]["roc_auc"]
    logit_auc = all_metrics[1]["roc_auc"]
    naive_acc = all_metrics[2]["accuracy"]
    rf_acc = all_metrics[0]["accuracy"]
    if rf_auc > logit_auc + 0.02 and rf_acc > naive_acc:
        verdict = ("RF outperforms both the logistic and naive baselines on "
                   "AUC and accuracy")
    elif rf_acc > naive_acc:
        verdict = ("RF beats the naive baseline but is roughly on par with "
                   "logistic regression")
    else:
        verdict = ("RF does not clearly beat the naive baseline — signals "
                   "alone (z-scores, MOVE) carry most of the predictive content")
    print(f"  - {verdict}.")

    top3 = pd.Series(rf.feature_importances_,
                     index=FEATURE_COLS).sort_values(ascending=False).head(3)
    print(f"  - Top-3 features by importance: "
          f"{', '.join(f'{n} ({v:.3f})' for n, v in top3.items())}")

    print(f"  - Base reversion rate in test window: {100 * y_test.mean():.1f}% "
          f"→ a model predicting 'always revert' would hit that accuracy.")

    return {
        "events": events,
        "metrics": metrics_df,
        "rf_model": rf,
    }
