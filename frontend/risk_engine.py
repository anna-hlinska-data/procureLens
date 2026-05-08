"""
risk_engine.py — EU ProcureLens ML Risk Scoring Module
=======================================================
Loads the trained Random Forest model and calculates
risk scores for EU procurement contracts.

Usage:
    from risk_engine import analyse_contracts
    results_df = analyse_contracts(cleaned_df)
"""

import os
import pickle
import numpy as np
import pandas as pd
from pathlib import Path

# =============================================================================
# CONFIGURATION
# =============================================================================

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "rf_model.pkl")

# Risk thresholds (from DAS5000 research)
HIGH_RISK_THRESHOLD   = 0.5
MEDIUM_RISK_THRESHOLD = 0.2

# Critical fields — if missing, auto-flag as high risk
CRITICAL_FIELDS = ["contract_value_eur", "country", "cpv_sector"]

# EU TED standard column names (after mapping.py)
EU_COLUMNS = {
    "contract_id":       ["transaction_id", "id", "contract_id", "notice_id"],
    "country":           ["company", "country", "iso_country_code", "buyer_country"],
    "cpv_sector":        ["item_category", "cpv", "sector", "cpv_code"],
    "contract_value_eur":["total_cost", "unit_price", "value", "award_value"],
    "award_date":        ["purchase_date", "date", "award_date"],
    "number_offers":     ["quantity", "nb_tenders", "offers", "number_offers"],
    "lot_number":        ["lot_number", "lot", "lots"],
    "procedure_type":    ["item_name", "procedure", "procedure_type"],
    "buyer_name":        ["buyer", "authority", "buyer_name"],
    "supplier_name":     ["supplier", "vendor", "winner", "supplier_name"],
}

# Known EU country average log values from DAS5000 research (baseline)
COUNTRY_BASELINES = {
    "DE": 9.36,   # Germany — fragmented (federal structure)
    "IT": 13.85,  # Italy — high value
    "FR": 13.20,  # France
    "PL": 12.45,  # Poland
    "ES": 13.10,  # Spain
    "UK": 13.50,  # United Kingdom
    "GB": 13.50,
    "NL": 12.80,  # Netherlands
    "BE": 13.00,  # Belgium
    "SE": 13.60,  # Sweden
    "FI": 13.10,  # Finland
    "DK": 13.30,  # Denmark
    "AT": 12.90,  # Austria
    "GR": 12.57,  # Greece
    "BG": 11.20,  # Bulgaria
    "RO": 11.80,  # Romania
    "CZ": 12.10,  # Czech Republic
    "HU": 12.30,  # Hungary
    "PT": 12.60,  # Portugal
    "HR": 11.90,  # Croatia
    "SK": 11.70,  # Slovakia
    "LT": 11.40,  # Lithuania
    "LV": 11.50,  # Latvia
    "EE": 11.60,  # Estonia
    "SI": 11.80,  # Slovenia
    "LU": 13.50,  # Luxembourg
    "IE": 13.20,  # Ireland
    "CY": 12.00,  # Cyprus
    "MT": 11.30,  # Malta
    "NO": 13.40,  # Norway
    "IS": 12.50,  # Iceland
    "LI": 12.80,  # Liechtenstein
    "MK": 11.10,  # North Macedonia
}

# =============================================================================
# MODEL LOADING
# =============================================================================

_model = None

def load_model():
    """
    Load the trained Random Forest model from disk.
    Returns None if model file not found (demo mode).
    """
    global _model

    if _model is not None:
        return _model

    if os.path.exists(MODEL_PATH):
        try:
            with open(MODEL_PATH, "rb") as f:
                _model = pickle.load(f)
            print(f"✅ RF model loaded from {MODEL_PATH}")
            return _model
        except Exception as e:
            print(f"⚠️  Could not load model: {e}")
            return None
    else:
        print(f"⚠️  Model not found at {MODEL_PATH}")
        print("   Running in DEMO MODE — using country baselines only")
        return None


# =============================================================================
# COLUMN DETECTION
# =============================================================================

def detect_column(df: pd.DataFrame, field: str) -> str | None:
    """
    Find the actual column name in df that matches a standard EU field.
    Returns the column name or None.
    """
    candidates = EU_COLUMNS.get(field, [field])
    df_cols_lower = {c.lower().replace(" ", "_"): c for c in df.columns}

    for candidate in candidates:
        c = candidate.lower().replace(" ", "_")
        if c in df_cols_lower:
            return df_cols_lower[c]

    # fuzzy fallback
    import difflib
    for candidate in candidates:
        matches = difflib.get_close_matches(
            candidate.lower(),
            list(df_cols_lower.keys()),
            n=1, cutoff=0.75
        )
        if matches:
            return df_cols_lower[matches[0]]

    return None


# =============================================================================
# FEATURE ENGINEERING
# =============================================================================

def extract_features(row: pd.Series, col_map: dict) -> np.ndarray | None:
    """
    Convert a contract row into the 127-feature vector expected by the RF model.
    Returns None if critical features are missing.
    """
    features = {}

    # --- Numeric features ---
    # contract value (log transformed)
    val_col = col_map.get("contract_value_eur")
    if val_col and pd.notna(row.get(val_col)):
        try:
            val = float(str(row[val_col]).replace(",", "").replace("€", "").replace("£", "").strip())
            features["log_value"] = np.log1p(max(val, 0))
        except (ValueError, TypeError):
            features["log_value"] = 0.0
    else:
        features["log_value"] = 0.0

    # year
    date_col = col_map.get("award_date")
    if date_col and pd.notna(row.get(date_col)):
        try:
            year = pd.to_datetime(row[date_col], dayfirst=True, errors="coerce")
            features["year"] = year.year if year else 2020
        except (ValueError, AttributeError):
            features["year"] = 2020
    else:
        features["year"] = 2020

    # lot number
    lot_col = col_map.get("lot_number")
    if lot_col and pd.notna(row.get(lot_col)):
        try:
            features["lot_number"] = float(row[lot_col])
        except (ValueError, TypeError):
            features["lot_number"] = 1.0
    else:
        features["lot_number"] = 1.0

    # number of offers
    offers_col = col_map.get("number_offers")
    if offers_col and pd.notna(row.get(offers_col)):
        try:
            features["number_offers"] = float(row[offers_col])
        except (ValueError, TypeError):
            features["number_offers"] = 3.0
    else:
        features["number_offers"] = 3.0  # EU median

    # --- One-hot: country (33 EU countries) ---
    country_col = col_map.get("country")
    country_val = str(row.get(country_col, "")).upper()[:2] if country_col else ""

    for code in COUNTRY_BASELINES.keys():
        features[f"country_{code}"] = 1.0 if country_val == code else 0.0

    # --- One-hot: top sectors (simplified) ---
    sector_col = col_map.get("cpv_sector")
    sector_val = str(row.get(sector_col, "")).lower() if sector_col else ""

    top_sectors = [
        "medical", "construction", "it", "infrastructure",
        "transport", "energy", "education", "defence",
        "consultancy", "maintenance"
    ]
    for s in top_sectors:
        features[f"sector_{s}"] = 1.0 if s in sector_val else 0.0

    # build array in consistent order
    feature_names = (
        ["log_value", "year", "lot_number", "number_offers"]
        + [f"country_{c}" for c in COUNTRY_BASELINES.keys()]
        + [f"sector_{s}" for s in top_sectors]
    )

    return np.array([features.get(f, 0.0) for f in feature_names])


# =============================================================================
# RISK SCORING
# =============================================================================

def predict_value(features: np.ndarray, model) -> float:
    """
    Use RF model to predict expected log contract value.
    Returns predicted EUR value.
    """
    log_pred = model.predict(features.reshape(1, -1))[0]
    return float(np.expm1(log_pred))  # reverse log1p


def baseline_predict(row: pd.Series, col_map: dict) -> float:
    """
    Fallback prediction using country baselines from DAS5000 research.
    Used when RF model is not available (demo mode).
    """
    country_col = col_map.get("country")
    country_val = str(row.get(country_col, "")).upper()[:2] if country_col else ""
    log_baseline = COUNTRY_BASELINES.get(country_val, 12.5)  # EU average

    # sector adjustments
    sector_col = col_map.get("cpv_sector")
    sector_val = str(row.get(sector_col, "")).lower() if sector_col else ""

    adjustments = {
        "infrastructure": +1.5,
        "construction":   +1.2,
        "defence":        +1.8,
        "medical":        +0.8,
        "it":             -0.3,
        "consultancy":    -0.5,
        "maintenance":    -0.8,
    }

    for keyword, adj in adjustments.items():
        if keyword in sector_val:
            log_baseline += adj
            break

    return float(np.expm1(log_baseline))


def calculate_risk_score(actual: float, predicted: float) -> float:
    """
    Calculate normalised risk score.
    Formula: |actual - predicted| / predicted
    """
    if predicted <= 0 or actual < 0:
        return 1.0
    return abs(actual - predicted) / predicted


def get_risk_flag(risk_score: float, missing_critical: int) -> str:
    """
    Assign risk flag based on score and missing critical fields.
    """
    if missing_critical >= 2:
        return "🔴 HIGH"
    if risk_score > HIGH_RISK_THRESHOLD:
        return "🔴 HIGH"
    if risk_score > MEDIUM_RISK_THRESHOLD:
        return "🟡 MEDIUM"
    return "🟢 LOW"


def count_missing_critical(row: pd.Series, col_map: dict) -> int:
    """
    Count how many critical fields are missing in a contract row.
    """
    count = 0
    for field in CRITICAL_FIELDS:
        col = col_map.get(field)
        if col is None or pd.isna(row.get(col)) or str(row.get(col)).strip() == "":
            count += 1
    return count


# =============================================================================
# MAIN ANALYSIS FUNCTION
# =============================================================================

def analyse_contracts(df: pd.DataFrame) -> pd.DataFrame:
    """
    Main function — analyses all contracts in a DataFrame.

    Args:
        df: Cleaned procurement DataFrame (output of cleaning.py)

    Returns:
        DataFrame with added columns:
            predicted_value_eur, risk_score, risk_flag, missing_critical_fields
    """
    if df is None or df.empty:
        return pd.DataFrame()

    model = load_model()

    # build column map once
    col_map = {}
    for field in EU_COLUMNS.keys():
        col = detect_column(df, field)
        if col:
            col_map[field] = col

    results = []

    for idx, row in df.iterrows():
        # count missing critical fields
        missing = count_missing_critical(row, col_map)

        # get actual contract value
        val_col = col_map.get("contract_value_eur")
        try:
            actual = float(
                str(row.get(val_col, 0))
                .replace(",", "")
                .replace("€", "")
                .replace("£", "")
                .strip()
            ) if val_col and pd.notna(row.get(val_col)) else 0.0
        except (ValueError, TypeError):
            actual = 0.0

        # predict expected value
        if model is not None:
            try:
                features = extract_features(row, col_map)
                predicted = predict_value(features, model)
            except Exception:
                predicted = baseline_predict(row, col_map)
        else:
            predicted = baseline_predict(row, col_map)

        # calculate risk
        if actual > 0:
            score = calculate_risk_score(actual, predicted)
        else:
            # missing value is itself a risk indicator
            score = 0.6 if missing >= 1 else 0.3

        flag = get_risk_flag(score, missing)

        results.append({
            "predicted_value_eur":    round(predicted, 2),
            "risk_score":             round(score, 4),
            "risk_flag":              flag,
            "missing_critical_fields": missing,
        })

    result_df = pd.DataFrame(results, index=df.index)
    return pd.concat([df, result_df], axis=1)


# =============================================================================
# SUMMARY STATS
# =============================================================================

def risk_summary(results_df: pd.DataFrame) -> dict:
    """
    Generate summary statistics from risk analysis results.
    """
    if "risk_flag" not in results_df.columns:
        return {}

    flags = results_df["risk_flag"]
    total = len(flags)

    return {
        "total":       total,
        "high_risk":   int((flags == "🔴 HIGH").sum()),
        "medium_risk": int((flags == "🟡 MEDIUM").sum()),
        "low_risk":    int((flags == "🟢 LOW").sum()),
        "high_pct":    round((flags == "🔴 HIGH").sum() / max(total, 1) * 100, 1),
        "medium_pct":  round((flags == "🟡 MEDIUM").sum() / max(total, 1) * 100, 1),
        "low_pct":     round((flags == "🟢 LOW").sum() / max(total, 1) * 100, 1),
        "avg_risk_score": round(results_df["risk_score"].mean(), 4) if "risk_score" in results_df.columns else 0,
    }
