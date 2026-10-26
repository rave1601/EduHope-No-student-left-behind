# ============================================================
# EduHope — Training Script (3-class + binary + eval artifacts)
# ============================================================
import pandas as pd
import numpy as np
import json
import joblib

from sklearn.model_selection import (
    StratifiedKFold, cross_val_score, RandomizedSearchCV, cross_val_predict,
    train_test_split
)
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (
    classification_report, confusion_matrix, roc_auc_score, accuracy_score,
    f1_score
)
from xgboost import XGBClassifier
from scipy.stats import randint, uniform

# ------------------------------------------------------------
# 1. Load
# ------------------------------------------------------------
df = pd.read_csv("dataset.csv")
print("Raw shape:", df.shape)

# ------------------------------------------------------------
# 2. Feature engineering (full set)
# ------------------------------------------------------------
eps = 1e-6
for sem in ["1st", "2nd"]:
    ap = df[f"Curricular units {sem} sem (approved)"]
    en = df[f"Curricular units {sem} sem (enrolled)"]
    ev = df[f"Curricular units {sem} sem (evaluations)"]
    gr = df[f"Curricular units {sem} sem (grade)"]
    df[f"pass_rate_{sem}"]     = ap / (en + eps)
    df[f"eval_per_unit_{sem}"] = ev / (en + eps)
    df[f"grade_x_pass_{sem}"]  = gr * ap / (en + eps)

df["pass_rate_delta"]   = df["pass_rate_2nd"] - df["pass_rate_1st"]
df["grade_delta"]       = df["Curricular units 2nd sem (grade)"] - df["Curricular units 1st sem (grade)"]
df["total_approved"]    = df["Curricular units 1st sem (approved)"] + df["Curricular units 2nd sem (approved)"]
df["total_enrolled"]    = df["Curricular units 1st sem (enrolled)"] + df["Curricular units 2nd sem (enrolled)"]
df["overall_pass_rate"] = df["total_approved"] / (df["total_enrolled"] + eps)

df["evaluations_both"]         = df["Curricular units 1st sem (evaluations)"] + df["Curricular units 2nd sem (evaluations)"]
df["evaluations_per_approved"] = df["evaluations_both"] / (df["total_approved"] + 1)
df["failed_sem1"]              = (df["Curricular units 1st sem (approved)"] == 0).astype(int)
df["failed_sem2"]              = (df["Curricular units 2nd sem (approved)"] == 0).astype(int)
df["failed_both"]              = ((df["failed_sem1"] == 1) & (df["failed_sem2"] == 1)).astype(int)
df["financial_risk"]           = df["Debtor"] * (1 - df["Tuition fees up to date"])
df["age_bucket"]               = pd.cut(
    df["Age at enrollment"], bins=[0, 20, 25, 30, 100], labels=[0, 1, 2, 3]
).astype(int)

print("After FE shape:", df.shape)

# ------------------------------------------------------------
# 3. Drop noise columns
# ------------------------------------------------------------
drop_cols = ["Unemployment rate", "Inflation rate", "GDP",
             "Application order", "International", "Nacionality"]
df = df.drop(columns=[c for c in drop_cols if c in df.columns])

X = df.drop("Target", axis=1)
y = df["Target"]
le = LabelEncoder()
y_enc = le.fit_transform(y)

print("Final X shape:", X.shape)
print("Classes:", le.classes_.tolist())

# ------------------------------------------------------------
# 4. CV setup
# ------------------------------------------------------------
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(
    X, y_enc, test_size=0.2, random_state=42, stratify=y_enc
)

# ------------------------------------------------------------
# 5. Baseline after FE + drop
# ------------------------------------------------------------
base_xgb = XGBClassifier(
    n_estimators=600, max_depth=6, learning_rate=0.05,
    subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0,
    objective="multi:softprob", num_class=3,
    tree_method="hist", random_state=42, n_jobs=-1,
    eval_metric="mlogloss",
)
s = cross_val_score(base_xgb, X, y_enc, cv=cv, scoring="accuracy", n_jobs=-1)
print(f"\n[5] XGBoost + FE + drop-noise: {s.mean()*100:.2f}% ± {s.std()*100:.2f}%")

# ------------------------------------------------------------
# 6. Tuned XGBoost (3-class) — this is what gets saved for the app
# ------------------------------------------------------------
param_dist = {
    "n_estimators":     randint(400, 1200),
    "max_depth":        randint(4, 10),
    "learning_rate":    uniform(0.01, 0.15),
    "subsample":        uniform(0.6, 0.4),
    "colsample_bytree": uniform(0.6, 0.4),
    "reg_lambda":       uniform(0, 5),
    "min_child_weight": randint(1, 10),
    "gamma":            uniform(0, 1),
}

search = RandomizedSearchCV(
    XGBClassifier(
        objective="multi:softprob", num_class=3,
        tree_method="hist", random_state=42, n_jobs=-1,
        eval_metric="mlogloss",
    ),
    param_dist, n_iter=60, cv=cv, scoring="f1_macro",
    n_jobs=-1, random_state=42, verbose=1,
)
search.fit(X_train, y_train)
print("\nBest params:", search.best_params_)
print(f"Best macro F1 (training CV; tuning only): {search.best_score_:.4f}")

tuned = search.best_estimator_
test_pred = tuned.predict(X_test)
test_accuracy = accuracy_score(y_test, test_pred)
test_macro_f1 = f1_score(y_test, test_pred, average="macro")
print(f"[6] Tuned XGBoost held-out accuracy: {test_accuracy*100:.2f}%")
print(f"    Tuned XGBoost held-out macro F1: {test_macro_f1:.4f}")

# Fit the champion on all data and save the 3-class artifact
tuned.fit(X, y_enc)
joblib.dump({
    "model":         tuned,
    "label_encoder": le,
    "feature_names": X.columns.tolist(),
    "classes":       le.inverse_transform(tuned.classes_).tolist(),
}, "eduhope_model.joblib")

with open("model_metadata.json", "w") as f:
    json.dump({
        "model":           "XGBoost (tuned, 3-class)",
      "test_accuracy":   round(test_accuracy * 100, 2),
      "test_macro_f1":   round(test_macro_f1, 4),
      "evaluation":      "stratified 20% held-out test split; hyperparameters selected on training split",
        "classes":         le.classes_.tolist(),
        "n_features":      len(X.columns),
        "features":        X.columns.tolist(),
    }, f, indent=2)

print("\nSaved eduhope_model.joblib and model_metadata.json")

# ------------------------------------------------------------
# 7. Binary reframing: Dropout vs Not-Dropout
# ------------------------------------------------------------
print("\n" + "=" * 60)
print("  Binary task: Dropout vs Not-Dropout")
print("=" * 60)

df_bin = df.copy()
df_bin["Target_bin"] = (df_bin["Target"] == "Dropout").astype(int)
X_bin = df_bin.drop(["Target", "Target_bin"], axis=1)
y_bin = df_bin["Target_bin"]
X_bin_train, X_bin_test, y_bin_train, y_bin_test = train_test_split(
    X_bin, y_bin, test_size=0.2, random_state=42, stratify=y_bin
)

bin_params = {k: v for k, v in search.best_params_.items()}

clf_bin = XGBClassifier(
    **bin_params,
    objective="binary:logistic",
    tree_method="hist",
    random_state=42, n_jobs=-1,
    eval_metric="logloss",
)

s_bin = cross_val_score(clf_bin, X_bin, y_bin, cv=cv, scoring="accuracy", n_jobs=-1)
print(f"\n[7] Binary accuracy: {s_bin.mean()*100:.2f}% ± {s_bin.std()*100:.2f}%")

y_pred_bin = cross_val_predict(clf_bin, X_bin, y_bin, cv=cv, n_jobs=-1)
print("\nPer-class report (binary, CV predictions):")
print(classification_report(
    pd.Series(y_bin).map({0: "NotDropout", 1: "Dropout"}),
    pd.Series(y_pred_bin).map({0: "NotDropout", 1: "Dropout"}),
    digits=3, zero_division=0,
))

# ------------------------------------------------------------
# 7b. Retune binary + ROC-AUC + optional ensemble
# ------------------------------------------------------------
print("\n" + "=" * 60)
print("  Binary retune + ensemble")
print("=" * 60)

bin_param_dist = {
    "n_estimators":     randint(400, 1000),
    "max_depth":        randint(3, 8),
    "learning_rate":    uniform(0.02, 0.12),
    "subsample":        uniform(0.7, 0.3),
    "colsample_bytree": uniform(0.7, 0.3),
    "reg_lambda":       uniform(0, 3),
    "min_child_weight": randint(1, 6),
    "gamma":            uniform(0, 0.5),
}

bin_search = RandomizedSearchCV(
    XGBClassifier(
        objective="binary:logistic",
        tree_method="hist",
        random_state=42, n_jobs=-1,
        eval_metric="logloss",
    ),
    bin_param_dist, n_iter=40, cv=cv, scoring="accuracy",
    n_jobs=-1, random_state=42, verbose=1,
)
bin_search.fit(X_bin_train, y_bin_train)
print("Best binary params:", bin_search.best_params_)

print(f"[7b] Best binary training CV accuracy (tuning only): {bin_search.best_score_*100:.2f}%")

# Optional ensemble
try:
    from lightgbm import LGBMClassifier
    ensemble_estimators = [
        ("xgb", bin_search.best_estimator_),
        ("lgb", LGBMClassifier(
            n_estimators=500, learning_rate=0.05, num_leaves=31,
            class_weight="balanced", random_state=42,
            n_jobs=-1, verbose=-1,
        )),
        ("rf", RandomForestClassifier(
            n_estimators=300, class_weight="balanced",
            random_state=42, n_jobs=-1,
        )),
    ]
except ImportError:
    print("lightgbm not installed — using XGB + RF only")
    ensemble_estimators = [
        ("xgb", bin_search.best_estimator_),
        ("rf", RandomForestClassifier(
            n_estimators=300, class_weight="balanced",
            random_state=42, n_jobs=-1,
        )),
    ]

ensemble = VotingClassifier(estimators=ensemble_estimators, voting="soft", n_jobs=-1)
s_ens = cross_val_score(ensemble, X_bin_train, y_bin_train, cv=cv, scoring="accuracy", n_jobs=-1)
print(f"[7c] Ensemble binary training CV accuracy: {s_ens.mean()*100:.2f}% ± {s_ens.std()*100:.2f}%")

# Save whichever binary model won
if s_ens.mean() > bin_search.best_score_:
    final_bin = ensemble
    final_bin_label = "Soft-vote ensemble"
else:
    final_bin = bin_search.best_estimator_
    final_bin_label = "Tuned XGBoost (binary)"

final_bin.fit(X_bin_train, y_bin_train)
binary_test_pred = final_bin.predict(X_bin_test)
final_bin_acc = accuracy_score(y_bin_test, binary_test_pred)
binary_probabilities = final_bin.predict_proba(X_bin_test)[:, 1]
binary_test_auc = roc_auc_score(y_bin_test, binary_probabilities)
print(f"[7d] Selected binary model held-out accuracy: {final_bin_acc*100:.2f}%")
print(f"     Selected binary model held-out ROC-AUC: {binary_test_auc:.4f}")

final_bin.fit(X_bin, y_bin)
joblib.dump({
    "model":          final_bin,
    "feature_names":  X_bin.columns.tolist(),
    "task":           "binary_dropout",
    "positive_class": "Dropout",
    "test_accuracy":  round(final_bin_acc * 100, 2),
    "test_roc_auc":   round(binary_test_auc, 4),
    "evaluation":     "stratified 20% held-out test split; model selected using training data only",
}, "eduhope_model_binary.joblib")

with open("model_metadata_binary.json", "w") as f:
    json.dump({
        "model":           final_bin_label,
        "task":            "Dropout vs Not-Dropout",
        "test_accuracy":   round(final_bin_acc * 100, 2),
        "test_roc_auc":    round(binary_test_auc, 4),
        "features":        X_bin.columns.tolist(),
    }, f, indent=2)

print(f"\nSaved best binary model: {final_bin_label}")
print(f"Final binary held-out accuracy: {final_bin_acc*100:.2f}%")

# ------------------------------------------------------------
# 8. Save evaluation JSONs for RF / DT / LR (for Model Performance page)
# ------------------------------------------------------------
print("\n" + "=" * 60)
print("  Saving evaluation artifacts (RF / DT / LR)")
print("=" * 60)

eval_models = {
    "Random Forest": RandomForestClassifier(
        n_estimators=300, class_weight="balanced",
        random_state=42, n_jobs=-1,
    ),
    "Decision Tree": DecisionTreeClassifier(
        class_weight="balanced", random_state=42,
    ),
    "Logistic Regression": make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42),
    ),
}

for name, m in eval_models.items():
    pred = cross_val_predict(m, X, y_enc, cv=cv, n_jobs=-1)
    report = classification_report(y_enc, pred, output_dict=True, zero_division=0)
    payload = {
        "model":                 name,
        "accuracy":              float((pred == y_enc).mean()),
        "macro_precision":       float(report["macro avg"]["precision"]),
        "macro_recall":          float(report["macro avg"]["recall"]),
        "macro_f1":              float(report["macro avg"]["f1-score"]),
        "confusion_matrix":      confusion_matrix(y_enc, pred).tolist(),
        "classes":               le.classes_.tolist(),
        "classification_report": report,
    }
    filename = f"eval_{name.replace(' ', '_').lower()}.json"
    with open(filename, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"  {filename}: accuracy={payload['accuracy']*100:.2f}%, "
          f"macro_f1={payload['macro_f1']:.3f}")

print("\n" + "=" * 60)
print("  ALL DONE")
print("=" * 60)
print("Artifacts written to this folder:")
print("  eduhope_model.joblib          (3-class XGBoost)")
print("  eduhope_model_binary.joblib   (binary XGBoost)")
print("  model_metadata.json")
print("  model_metadata_binary.json")
print("  eval_random_forest.json")
print("  eval_decision_tree.json")
print("  eval_logistic_regression.json")
print("\nNext: launch Antigravity with the prompt from the previous message.")
