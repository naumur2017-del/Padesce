"""
Script complet : extraction des données PADESCE, entraînement de 5 modèles,
optimisation des hyperparamètres, évaluation et génération de toutes les figures.
"""

import sqlite3
import hashlib
import hmac
import secrets
import json
import warnings
from pathlib import Path
from collections import Counter

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
from scipy import stats

from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.impute import SimpleImputer
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import Ridge
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.svm import SVR
from sklearn.model_selection import GroupKFold, GridSearchCV
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score
)

warnings.filterwarnings("ignore")

SEED = 20260811
np.random.seed(SEED)

DB_PATH = Path(__file__).resolve().parent.parent / "backup.sqlite3"
OUTPUT_DIR = Path(__file__).resolve().parent / "results"
FIG_DIR = Path(__file__).resolve().parent / "figures" / "generated"
DATA_DIR = Path(__file__).resolve().parent / "data" / "processed"

for d in [OUTPUT_DIR, FIG_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)

NUMERIC_FEATURES = [
    "nombre_classes", "nombre_lieux", "nombre_apprenants",
    "taille_moyenne_classe", "lieux_par_classe", "proportion_femmes",
]
CATEGORICAL_FEATURES = ["region", "fenetre"]
FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TARGET = "score_performance_pomp"
GROUP = "prestataire_groupe"
WEIGHT = "nombre_reponses"


# ── 1. EXTRACTION ──────────────────────────────────────────────────────────────

def extract_dataset():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    q = """
    SELECT
        aa.appel_id,
        aa.q1_clarte_exposes, aa.q2_interaction_formateur,
        aa.q3_maitrise_contenu, aa.q4_salle_adequate,
        aa.q5_materiel_disponible, aa.q6_organisation_temps,
        aa.q7_utilite_formation, aa.q8_adequation_besoins,
        aa.q9_satisfaction_globale,
        a.classe_id, a.status, a.is_active,
        a.flag_faux_nom, a.flag_numero_double, a.flag_pas_forme,
        a.fenetre,
        c.prestation_id, c.lieu_id,
        p.prestataire_id, p.effectif_a_former, p.femmes,
        pr.code AS prestataire_code,
        l.region
    FROM appels_appelanswers aa
    JOIN appels_appel a ON aa.appel_id = a.id
    JOIN formations_classe c ON a.classe_id = c.id
    JOIN formations_prestation p ON c.prestation_id = p.id
    JOIN formations_prestataire pr ON p.prestataire_id = pr.id
    LEFT JOIN formations_lieu l ON c.lieu_id = l.id
    """
    df = pd.read_sql_query(q, conn)
    conn.close()

    q_cols = [f"q{i}" for i in range(1, 10)]
    rename = {
        "q1_clarte_exposes": "q1", "q2_interaction_formateur": "q2",
        "q3_maitrise_contenu": "q3", "q4_salle_adequate": "q4",
        "q5_materiel_disponible": "q5", "q6_organisation_temps": "q6",
        "q7_utilite_formation": "q7", "q8_adequation_besoins": "q8",
        "q9_satisfaction_globale": "q9",
    }
    df.rename(columns=rename, inplace=True)

    for c in q_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    complete = df.dropna(subset=q_cols).copy()
    active = complete[complete["is_active"] == 1].copy()
    linked = active[active["prestation_id"].notna()].copy()

    valid_status = ~(
        (linked["flag_faux_nom"].isin([1, "1", True])) |
        (linked["flag_numero_double"].isin([1, "1", True])) |
        (linked["flag_pas_forme"].isin([1, "1", True]))
    )
    eligible = linked[valid_status].copy()

    for c in q_cols:
        eligible[c] = eligible[c].clip(1, 5)

    eligible["mean_q"] = eligible[q_cols].mean(axis=1)

    agg = eligible.groupby("prestation_id").agg(
        nombre_reponses=("mean_q", "size"),
        score_mean_q=("mean_q", "mean"),
        prestataire_id=("prestataire_id", "first"),
        prestataire_code=("prestataire_code", "first"),
        effectif_a_former=("effectif_a_former", "first"),
        femmes=("femmes", "first"),
        fenetre=("fenetre", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else np.nan),
        region=("region", lambda x: x.mode().iloc[0] if len(x.mode()) > 0 else np.nan),
    ).reset_index()

    classes = eligible.groupby("prestation_id")["classe_id"].nunique().reset_index()
    classes.columns = ["prestation_id", "nombre_classes"]
    lieux = eligible.groupby("prestation_id")["lieu_id"].nunique().reset_index()
    lieux.columns = ["prestation_id", "nombre_lieux"]

    agg = agg.merge(classes, on="prestation_id").merge(lieux, on="prestation_id")

    agg["score_performance_pomp"] = 25 * (agg["score_mean_q"] - 1)
    agg["nombre_apprenants"] = agg["effectif_a_former"]
    agg["taille_moyenne_classe"] = np.where(
        agg["nombre_classes"] > 0,
        agg["nombre_apprenants"] / agg["nombre_classes"],
        np.nan
    )
    agg["lieux_par_classe"] = np.where(
        agg["nombre_classes"] > 0,
        agg["nombre_lieux"] / agg["nombre_classes"],
        np.nan
    )
    agg["proportion_femmes"] = np.where(
        agg["nombre_apprenants"] > 0,
        agg["femmes"] / agg["nombre_apprenants"],
        np.nan
    )

    key = secrets.token_bytes(32)
    agg["prestataire_groupe"] = agg["prestataire_code"].apply(
        lambda x: hmac.new(key, f"prest|{x}".encode(), hashlib.sha256).hexdigest()[:16].upper()
    )

    MIN_RESPONSES = 10
    final = agg[agg["nombre_reponses"] >= MIN_RESPONSES].copy()

    cols_keep = ["prestation_id"] + FEATURES + [TARGET, GROUP, WEIGHT]
    dataset = final[cols_keep].copy()
    dataset.to_csv(DATA_DIR / "prestations_model.csv", index=False)

    cascade = {
        "total_appels": len(df),
        "q1q9_complets": len(complete),
        "actifs_rattaches": len(linked),
        "eligibles": len(eligible),
        "apres_qualite": len(eligible),
        "prestations_total": len(agg),
        "prestations_n10": len(final),
    }

    print(f"Dataset: {len(dataset)} prestations, {dataset[WEIGHT].sum():.0f} réponses")
    return dataset, cascade


# ── 2. PREPROCESSING ───────────────────────────────────────────────────────────

def make_preprocessor():
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)),
        ("scaler", StandardScaler()),
    ])
    categorical = Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=2, sparse_output=False)),
    ])
    return ColumnTransformer([
        ("numeric", numeric, NUMERIC_FEATURES),
        ("categorical", categorical, CATEGORICAL_FEATURES),
    ], verbose_feature_names_out=False)


def build_pipeline(estimator):
    return Pipeline([("preprocessor", make_preprocessor()), ("model", estimator)])


# ── 3. MODEL DEFINITIONS ──────────────────────────────────────────────────────

def model_specs():
    try:
        from xgboost import XGBRegressor
        xgb_available = True
    except ImportError:
        xgb_available = False

    specs = {
        "Moyenne naive": {
            "estimator": DummyRegressor(strategy="mean"),
            "grid": {},
        },
        "Ridge": {
            "estimator": Ridge(),
            "grid": {"model__alpha": [0.01, 0.1, 1.0, 10.0, 100.0]},
        },
        "Foret aleatoire": {
            "estimator": RandomForestRegressor(n_estimators=200, random_state=SEED, n_jobs=1),
            "grid": {
                "model__max_depth": [3, 5, None],
                "model__min_samples_leaf": [2, 4, 8],
                "model__max_features": [0.5, 0.7, 1.0],
            },
        },
        "Gradient Boosting": {
            "estimator": GradientBoostingRegressor(random_state=SEED),
            "grid": {
                "model__n_estimators": [100, 200],
                "model__max_depth": [2, 3],
                "model__learning_rate": [0.05, 0.1],
                "model__min_samples_leaf": [2, 4],
            },
        },
        "SVR": {
            "estimator": SVR(),
            "grid": {
                "model__C": [0.1, 1.0, 10.0],
                "model__epsilon": [0.1, 0.5, 1.0],
                "model__kernel": ["rbf", "linear"],
            },
        },
    }

    if xgb_available:
        specs["XGBoost"] = {
            "estimator": XGBRegressor(
                random_state=SEED, n_jobs=1, verbosity=0,
                objective="reg:squarederror",
            ),
            "grid": {
                "model__n_estimators": [100, 200],
                "model__max_depth": [2, 3],
                "model__learning_rate": [0.05, 0.1],
                "model__min_child_weight": [1, 3],
                "model__subsample": [0.8],
                "model__colsample_bytree": [0.7],
            },
        }

    return specs


# ── 4. TRAINING WITH NESTED GROUPED CV ─────────────────────────────────────────

def metric_values(y_true, y_pred):
    return {
        "MAE": mean_absolute_error(y_true, y_pred),
        "RMSE": np.sqrt(mean_squared_error(y_true, y_pred)),
        "R2": r2_score(y_true, y_pred),
        "Spearman": stats.spearmanr(y_true, y_pred).statistic,
    }


def train_all_models(dataset, repeats=3):
    X = dataset[FEATURES].copy()
    y = dataset[TARGET].values
    groups = dataset[GROUP].values
    weights = np.sqrt(dataset[WEIGHT].values)
    weights = weights / weights.mean()

    specs = model_specs()
    all_results = {}
    all_predictions = {}
    all_best_params = {}

    for name, spec in specs.items():
        print(f"\n{'='*60}")
        print(f"  Entraînement: {name}")
        print(f"{'='*60}")

        n_samples = len(X)
        repeated_preds = np.full((repeats, n_samples), np.nan, dtype=float)
        fold_records = []
        param_counts = Counter()

        for repeat in range(repeats):
            outer = GroupKFold(n_splits=5)
            for fold, (train_idx, test_idx) in enumerate(
                outer.split(X, y, groups=groups), start=1
            ):
                pipeline = build_pipeline(spec["estimator"])

                if spec["grid"]:
                    train_groups = groups[train_idx]
                    n_unique = len(np.unique(train_groups))
                    inner_splits = min(4, n_unique)
                    if inner_splits < 2:
                        inner_splits = 2
                    inner = GroupKFold(n_splits=inner_splits)
                    fitted = GridSearchCV(
                        pipeline, spec["grid"],
                        scoring="neg_mean_absolute_error",
                        cv=inner, n_jobs=1, refit=True, error_score="raise",
                    )
                    fitted.fit(
                        X.iloc[train_idx], y[train_idx],
                        groups=train_groups,
                        model__sample_weight=weights[train_idx],
                    )
                    best_params = fitted.best_params_
                    predictor = fitted.best_estimator_
                else:
                    pipeline.fit(
                        X.iloc[train_idx], y[train_idx],
                        model__sample_weight=weights[train_idx],
                    )
                    best_params = {}
                    predictor = pipeline

                predicted = predictor.predict(X.iloc[test_idx])
                repeated_preds[repeat, test_idx] = predicted
                param_counts[json.dumps(best_params, sort_keys=True)] += 1

                metrics = metric_values(y[test_idx], predicted)
                fold_records.append({
                    "repeat": repeat + 1, "fold": fold,
                    "n_train": len(train_idx), "n_test": len(test_idx),
                    "best_params": best_params, **metrics,
                })

        mean_preds = np.nanmean(repeated_preds, axis=0)
        overall_metrics = metric_values(y, mean_preds)

        bootstrap_maes = []
        unique_groups = np.unique(groups)
        rng = np.random.RandomState(SEED)
        for _ in range(1000):
            sampled = rng.choice(unique_groups, size=len(unique_groups), replace=True)
            mask = np.isin(groups, sampled)
            if mask.sum() > 0:
                bootstrap_maes.append(mean_absolute_error(y[mask], mean_preds[mask]))

        ci_low, ci_high = np.percentile(bootstrap_maes, [2.5, 97.5])

        most_common_params = json.loads(param_counts.most_common(1)[0][0]) if param_counts else {}

        all_results[name] = {
            "metrics": overall_metrics,
            "ci_mae": [ci_low, ci_high],
            "fold_records": fold_records,
            "best_params": most_common_params,
            "bootstrap_maes": bootstrap_maes,
        }
        all_predictions[name] = mean_preds
        all_best_params[name] = most_common_params

        print(f"  MAE = {overall_metrics['MAE']:.3f} [{ci_low:.3f}, {ci_high:.3f}]")
        print(f"  RMSE = {overall_metrics['RMSE']:.3f}")
        print(f"  R² = {overall_metrics['R2']:.4f}")
        print(f"  Spearman = {overall_metrics['Spearman']:.4f}")
        print(f"  Best params: {most_common_params}")

    return all_results, all_predictions, all_best_params


# ── 5. FIGURES ─────────────────────────────────────────────────────────────────

COLORS = {
    "Moyenne naive": "#95a5a6",
    "Ridge": "#3498db",
    "Foret aleatoire": "#2ecc71",
    "Gradient Boosting": "#e67e22",
    "SVR": "#9b59b6",
    "XGBoost": "#e74c3c",
}

def fig_comparison_mae(results):
    fig, ax = plt.subplots(figsize=(10, 5))
    names = sorted(results.keys(), key=lambda n: results[n]["metrics"]["MAE"])
    maes = [results[n]["metrics"]["MAE"] for n in names]
    ci_lows = [results[n]["ci_mae"][0] for n in names]
    ci_highs = [results[n]["ci_mae"][1] for n in names]
    colors = [COLORS.get(n, "#333") for n in names]

    bars = ax.barh(range(len(names)), maes, color=colors, edgecolor="white", height=0.6)
    for i, (m, lo, hi) in enumerate(zip(maes, ci_lows, ci_highs)):
        ax.errorbar(m, i, xerr=[[m - lo], [hi - m]], fmt="none", color="black", capsize=4)
        ax.text(m + 0.05, i, f"{m:.2f}", va="center", fontsize=10, fontweight="bold")

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=11)
    ax.set_xlabel("MAE hors pli (points POMP, plus faible = meilleur)", fontsize=11)
    ax.set_title("Comparaison des modeles par prestataire inedit", fontsize=13, fontweight="bold")
    ax.invert_yaxis()
    ax.set_xlim(0, max(ci_highs) + 1)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "comparaison_modeles.png", dpi=300)
    fig.savefig(FIG_DIR / "comparaison_modeles.pdf")
    plt.close(fig)


def fig_observed_predicted(y, predictions, best_model_name):
    preds = predictions[best_model_name]
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(preds, y, alpha=0.7, s=50, color=COLORS.get(best_model_name, "#e74c3c"), edgecolors="white", linewidth=0.5)
    lims = [min(y.min(), preds.min()) - 2, max(y.max(), preds.max()) + 2]
    ax.plot(lims, lims, "--", color="gray", label="Accord parfait")
    ax.axvline(y.mean(), color="orange", linestyle=":", alpha=0.7, label=f"Reference moyenne ({y.mean():.1f})")
    ax.set_xlabel("Score predit hors pli (POMP)", fontsize=11)
    ax.set_ylabel("Score observe (POMP)", fontsize=11)
    ax.set_title(f"Observe vs Predit — {best_model_name}", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "observe_predit.png", dpi=300)
    fig.savefig(FIG_DIR / "observe_predit.pdf")
    plt.close(fig)


def fig_residuals(y, predictions, best_model_name):
    preds = predictions[best_model_name]
    residuals = y - preds
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(preds, residuals, alpha=0.7, s=50, color=COLORS.get(best_model_name, "#e74c3c"), edgecolors="white", linewidth=0.5)
    ax.axhline(0, color="black", linestyle="-", linewidth=0.8)
    ax.set_xlabel("Score predit hors pli (POMP)", fontsize=11)
    ax.set_ylabel("Residu (observe - predit)", fontsize=11)
    ax.set_title(f"Residus — {best_model_name}", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "residus.png", dpi=300)
    fig.savefig(FIG_DIR / "residus.pdf")
    plt.close(fig)


def fig_distribution_cible(y):
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(y, bins=15, color="#3498db", edgecolor="white", alpha=0.8)
    ax.axvline(y.mean(), color="red", linestyle="--", label=f"Moyenne : {y.mean():.1f}")
    ax.axvline(np.median(y), color="orange", linestyle=":", label=f"Mediane : {np.median(y):.1f}")
    ax.set_xlabel("Score de performance percue (POMP, 0-100)", fontsize=11)
    ax.set_ylabel("Nombre de prestations", fontsize=11)
    ax.set_title(f"Distribution de la cible (n = {len(y)})", fontsize=13, fontweight="bold")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "distribution_cible.png", dpi=300)
    fig.savefig(FIG_DIR / "distribution_cible.pdf")
    plt.close(fig)


def fig_cascade(cascade):
    labels_left = ["Questionnaires", "Q1-Q9 complets", "Actifs et rattaches", "Eligibles"]
    values_left = [cascade["total_appels"], cascade["q1q9_complets"],
                   cascade["actifs_rattaches"], cascade["apres_qualite"]]
    labels_right = ["Apres qualite", "n >= 10"]
    values_right = [cascade["prestations_total"], cascade["prestations_n10"]]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.barh(range(len(labels_left)), values_left, color="#3498db", edgecolor="white")
    for i, v in enumerate(values_left):
        ax1.text(v + 50, i, str(v), va="center", fontsize=10)
    ax1.set_yticks(range(len(labels_left)))
    ax1.set_yticklabels(labels_left, fontsize=10)
    ax1.invert_yaxis()
    ax1.set_title("Reponses", fontsize=12, fontweight="bold")
    ax1.set_xlabel("Nombre de questionnaires")

    ax2.barh(range(len(labels_right)), values_right, color="#2ecc71", edgecolor="white")
    for i, v in enumerate(values_right):
        ax2.text(v + 1, i, str(v), va="center", fontsize=10)
    ax2.set_yticks(range(len(labels_right)))
    ax2.set_yticklabels(labels_right, fontsize=10)
    ax2.invert_yaxis()
    ax2.set_title("Unites d'analyse", fontsize=12, fontweight="bold")
    ax2.set_xlabel("Nombre de prestations")

    fig.suptitle("Constitution de l'echantillon analytique", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "cascade_echantillon.png", dpi=300)
    fig.savefig(FIG_DIR / "cascade_echantillon.pdf")
    plt.close(fig)


def fig_completude(dataset):
    cols = NUMERIC_FEATURES + CATEGORICAL_FEATURES
    completude = [(c, (1 - dataset[c].isna().mean()) * 100) for c in cols]
    completude.sort(key=lambda x: x[1])
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh([c[0] for c in completude], [c[1] for c in completude], color="#3498db", edgecolor="white")
    for i, (_, v) in enumerate(completude):
        ax.text(v + 0.5, i, f"{v:.0f} %", va="center", fontsize=10)
    ax.set_xlabel("Completude (%)")
    ax.set_title(f"Completude des predicteurs agreges (n = {len(dataset)})", fontsize=13, fontweight="bold")
    ax.set_xlim(0, 110)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "completude_variables.png", dpi=300)
    fig.savefig(FIG_DIR / "completude_variables.pdf")
    plt.close(fig)


def fig_region(dataset):
    region_counts = dataset["region"].value_counts()
    small = region_counts[region_counts < 5]
    if len(small) > 0:
        region_counts["Autres (< 5)"] = small.sum()
        region_counts = region_counts.drop(small.index)
    region_counts = region_counts.sort_values()

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(region_counts.index, region_counts.values, color="#3498db", edgecolor="white")
    for i, v in enumerate(region_counts.values):
        ax.text(v + 0.3, i, str(v), va="center", fontsize=10)
    ax.set_xlabel("Prestations")
    ax.set_title("Repartition regionale des prestations retenues", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "repartition_regionale.png", dpi=300)
    fig.savefig(FIG_DIR / "repartition_regionale.pdf")
    plt.close(fig)


def fig_feature_importance(dataset, best_model_name, best_params):
    if best_model_name == "Moyenne naive":
        return

    specs = model_specs()
    spec = specs[best_model_name]
    pipeline = build_pipeline(spec["estimator"])

    if best_params:
        for k, v in best_params.items():
            key = k.replace("model__", "")
            try:
                pipeline.named_steps["model"].set_params(**{key: v})
            except Exception:
                pass

    X = dataset[FEATURES].copy()
    y = dataset[TARGET].values
    weights = np.sqrt(dataset[WEIGHT].values)
    weights = weights / weights.mean()
    pipeline.fit(X, y, model__sample_weight=weights)

    model = pipeline.named_steps["model"]
    preprocessor = pipeline.named_steps["preprocessor"]

    try:
        feature_names = preprocessor.get_feature_names_out()
    except Exception:
        feature_names = [f"f{i}" for i in range(20)]

    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    elif hasattr(model, "coef_"):
        importances = np.abs(model.coef_)
    else:
        return

    if len(importances) != len(feature_names):
        feature_names = [f"Feature {i}" for i in range(len(importances))]

    idx = np.argsort(importances)[-15:]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(range(len(idx)), importances[idx], color=COLORS.get(best_model_name, "#e74c3c"), edgecolor="white")
    ax.set_yticks(range(len(idx)))
    ax.set_yticklabels([feature_names[i] for i in idx], fontsize=9)
    ax.set_xlabel("Importance", fontsize=11)
    ax.set_title(f"Importance des variables — {best_model_name}", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "importance_variables.png", dpi=300)
    fig.savefig(FIG_DIR / "importance_variables.pdf")
    plt.close(fig)


def fig_metrics_table(results):
    fig, ax = plt.subplots(figsize=(10, 3))
    ax.axis("off")

    names = sorted(results.keys(), key=lambda n: results[n]["metrics"]["MAE"])
    cell_data = []
    for n in names:
        m = results[n]["metrics"]
        ci = results[n]["ci_mae"]
        cell_data.append([
            n,
            f"{m['MAE']:.2f}",
            f"[{ci[0]:.2f}, {ci[1]:.2f}]",
            f"{m['RMSE']:.2f}",
            f"{m['R2']:.4f}",
            f"{m['Spearman']:.4f}",
        ])

    table = ax.table(
        cellText=cell_data,
        colLabels=["Modele", "MAE", "IC 95%", "RMSE", "R²", "Spearman"],
        loc="center", cellLoc="center",
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.5)

    for j in range(6):
        table[0, j].set_facecolor("#3498db")
        table[0, j].set_text_props(color="white", fontweight="bold")

    best_idx = 0
    for i in range(len(names)):
        if names[i] != "Moyenne naive":
            for j in range(6):
                if i == best_idx:
                    table[i + 1, j].set_facecolor("#eafaf1")

    fig.suptitle("Resultats de validation interne groupee", fontsize=13, fontweight="bold", y=0.95)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "tableau_resultats.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "tableau_resultats.pdf", bbox_inches="tight")
    plt.close(fig)


# ── 6. MAIN ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  MEMOIRE PADESCE — Construction des modeles")
    print("=" * 60)

    print("\n[1/4] Extraction des donnees...")
    dataset, cascade = extract_dataset()

    print(f"\n[2/4] Entrainement des modeles...")
    results, predictions, best_params = train_all_models(dataset)

    best_name = min(
        [n for n in results if n != "Moyenne naive"],
        key=lambda n: results[n]["metrics"]["MAE"]
    )
    print(f"\n>>> Meilleur modele: {best_name} (MAE = {results[best_name]['metrics']['MAE']:.3f})")

    print(f"\n[3/4] Generation des figures...")
    y = dataset[TARGET].values

    fig_distribution_cible(y)
    fig_cascade(cascade)
    fig_completude(dataset)
    fig_region(dataset)
    fig_comparison_mae(results)
    fig_observed_predicted(y, predictions, best_name)
    fig_residuals(y, predictions, best_name)
    fig_feature_importance(dataset, best_name, best_params.get(best_name, {}))
    fig_metrics_table(results)

    print(f"\n[4/4] Sauvegarde des resultats...")
    summary = {}
    for name, res in results.items():
        summary[name] = {
            "metrics": res["metrics"],
            "ci_mae_95": res["ci_mae"],
            "best_params": res["best_params"],
        }

    with open(OUTPUT_DIR / "model_results.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    dataset.to_csv(DATA_DIR / "prestations_model.csv", index=False)

    print(f"\n{'='*60}")
    print(f"  TERMINE")
    print(f"  Figures: {FIG_DIR}")
    print(f"  Resultats: {OUTPUT_DIR / 'model_results.json'}")
    print(f"  Dataset: {DATA_DIR / 'prestations_model.csv'}")
    print(f"{'='*60}")

    return results, predictions, best_params, dataset, cascade


if __name__ == "__main__":
    main()
