"""
risk_engine.py — EU ProcureLens ML Risk Scoring Module
"""

import os
import joblib
import numpy as np
import pandas as pd

MODEL_PATH = os.path.join(os.path.dirname(__file__), "models", "rf_model.pkl")

HIGH_RISK_THRESHOLD   = 0.5
MEDIUM_RISK_THRESHOLD = 0.2

CRITICAL_FIELDS = ["contract_value_eur"]

EU_COLUMNS = {
    "contract_id":        ["transaction_id", "id", "contract_id", "notice_id"],
    "country":            ["company", "country", "iso_country_code", "buyer_country"],
    "cpv_sector":         ["item_category", "cpv", "sector", "cpv_code"],
    "contract_value_eur": ["total_cost", "unit_price", "value", "award_value", "actual_value_eur", "actual_value"],
    "award_date":         ["purchase_date", "date", "award_date"],
    "number_offers":      ["quantity", "nb_tenders", "offers", "number_offers"],
    "lot_number":         ["lot_number", "lot", "lots"],
    "procedure_type":     ["item_name", "procedure", "procedure_type"],
}

MODEL_FEATURES = ['year', 'month', 'number_offers', 'lot_number',
    'country_AT', 'country_BE', 'country_BG', 'country_CH', 'country_CY',
    'country_CZ', 'country_DE', 'country_DK', 'country_EE', 'country_ES',
    'country_FI', 'country_FR', 'country_GR', 'country_HR', 'country_HU',
    'country_IE', 'country_IS', 'country_IT', 'country_LI', 'country_LT',
    'country_LU', 'country_LV', 'country_MK', 'country_MT', 'country_NL',
    'country_NO', 'country_PL', 'country_PT', 'country_RO', 'country_SE',
    'country_SI', 'country_SK', 'country_UK',
    'procedure_type_S', 'procedure_type_U', 'procedure_type_W',
    'sector_Construction', 'sector_Culture', 'sector_Education',
    'sector_Electrical Machinery', 'sector_Environment', 'sector_Healthcare',
    'sector_IT & Computers', 'sector_IT & Software Services',
    'sector_Maintenance', 'sector_Medical Equipment', 'sector_Miscellaneous',
    'sector_Public Services', 'sector_R&D', 'sector_Real Estate',
    'sector_Transport', 'sector_Unknown', 'sector_Vehicles', 'sector_Water Supply',
    'cpv_group_10', 'cpv_group_11', 'cpv_group_12', 'cpv_group_13',
    'cpv_group_14', 'cpv_group_15', 'cpv_group_16', 'cpv_group_17',
    'cpv_group_18', 'cpv_group_19', 'cpv_group_20', 'cpv_group_21',
    'cpv_group_22', 'cpv_group_23', 'cpv_group_24', 'cpv_group_25',
    'cpv_group_26', 'cpv_group_27', 'cpv_group_28', 'cpv_group_29',
    'cpv_group_30', 'cpv_group_31', 'cpv_group_32', 'cpv_group_33',
    'cpv_group_34', 'cpv_group_35', 'cpv_group_36', 'cpv_group_37',
    'cpv_group_38', 'cpv_group_39', 'cpv_group_40', 'cpv_group_41',
    'cpv_group_42', 'cpv_group_43', 'cpv_group_44', 'cpv_group_45',
    'cpv_group_48', 'cpv_group_50', 'cpv_group_51', 'cpv_group_52',
    'cpv_group_53', 'cpv_group_55', 'cpv_group_60', 'cpv_group_61',
    'cpv_group_62', 'cpv_group_63', 'cpv_group_64', 'cpv_group_65',
    'cpv_group_66', 'cpv_group_67', 'cpv_group_70', 'cpv_group_71',
    'cpv_group_72', 'cpv_group_73', 'cpv_group_74', 'cpv_group_75',
    'cpv_group_76', 'cpv_group_77', 'cpv_group_78', 'cpv_group_79',
    'cpv_group_80', 'cpv_group_85', 'cpv_group_90', 'cpv_group_91',
    'cpv_group_92', 'cpv_group_93', 'cpv_group_95', 'cpv_group_98', 'cpv_group_99'
]

COUNTRY_BASELINES = {
    "DE": 9.36, "IT": 13.85, "FR": 13.20, "PL": 12.45, "ES": 13.10,
    "UK": 13.50, "GB": 13.50, "NL": 12.80, "BE": 13.00, "SE": 13.60,
    "FI": 13.10, "DK": 13.30, "AT": 12.90, "GR": 12.57, "BG": 11.20,
    "RO": 11.80, "CZ": 12.10, "HU": 12.30, "PT": 12.60, "HR": 11.90,
    "SK": 11.70, "LT": 11.40, "LV": 11.50, "EE": 11.60, "SI": 11.80,
    "LU": 13.50, "IE": 13.20, "CY": 12.00, "MT": 11.30, "NO": 13.40,
    "IS": 12.50, "LI": 12.80, "MK": 11.10,
}

_model = None

def load_model():
    global _model
    if _model is not None:
        return _model
    if os.path.exists(MODEL_PATH):
        try:
            _model = joblib.load(MODEL_PATH)
            print(f"RF model loaded from {MODEL_PATH}")
            return _model
        except Exception as e:
            print(f"Could not load model: {e}")
            return None
    print(f"Model not found, using DEMO MODE")
    return None


def detect_column(df, field):
    candidates = EU_COLUMNS.get(field, [field])
    df_cols_lower = {c.lower().replace(" ", "_"): c for c in df.columns}
    for candidate in candidates:
        c = candidate.lower().replace(" ", "_")
        if c in df_cols_lower:
            return df_cols_lower[c]
    return None


def build_feature_row(row, col_map):
    r = {f: 0.0 for f in MODEL_FEATURES}

    # year
    date_col = col_map.get("award_date")
    if date_col and pd.notna(row.get(date_col)):
        try:
            yr = pd.to_datetime(row[date_col], dayfirst=True, errors="coerce")
            r["year"] = float(yr.year) if yr else 2024.0
        except Exception:
            r["year"] = 2024.0
    else:
        r["year"] = float(row.get("year", 2024))

    r["month"] = float(row.get("month", 6))

    offers_col = col_map.get("number_offers")
    r["number_offers"] = float(row.get(offers_col, row.get("number_offers", 3)) or 3)

    lot_col = col_map.get("lot_number")
    r["lot_number"] = float(row.get(lot_col, row.get("lot_number", 1)) or 1)

    # country
    country_col = col_map.get("country")
    country_val = str(row.get(country_col, row.get("country", ""))).upper().strip()[:2]
    if f"country_{country_val}" in r:
        r[f"country_{country_val}"] = 1.0

    # sector
    sector_col = col_map.get("cpv_sector")
    sector_val = str(row.get(sector_col, row.get("sector", ""))).strip()
    if f"sector_{sector_val}" in r:
        r[f"sector_{sector_val}"] = 1.0

    # procedure
    proc_col = col_map.get("procedure_type")
    proc_val = str(row.get(proc_col, row.get("procedure_type", "S"))).strip().upper()[:1]
    if f"procedure_type_{proc_val}" in r:
        r[f"procedure_type_{proc_val}"] = 1.0

    return pd.DataFrame([r])[MODEL_FEATURES]


def baseline_predict(row, col_map):
    country_col = col_map.get("country")
    country_val = str(row.get(country_col, row.get("country", ""))).upper()[:2]
    log_baseline = COUNTRY_BASELINES.get(country_val, 12.5)
    sector_col = col_map.get("cpv_sector")
    sector_val = str(row.get(sector_col, row.get("sector", ""))).lower()
    adjustments = {"infrastructure": 1.5, "construction": 1.2, "defence": 1.8,
                   "medical": 0.8, "it": -0.3, "consultancy": -0.5, "maintenance": -0.8}
    for kw, adj in adjustments.items():
        if kw in sector_val:
            log_baseline += adj
            break
    return float(np.expm1(log_baseline))


def calculate_risk_score(actual, predicted):
    if predicted <= 0 or actual < 0:
        return 1.0
    return abs(actual - predicted) / predicted


def get_risk_flag(risk_score, missing_critical):
    if missing_critical >= 2:
        return "🔴 HIGH"
    if risk_score > HIGH_RISK_THRESHOLD:
        return "🔴 HIGH"
    if risk_score > MEDIUM_RISK_THRESHOLD:
        return "🟡 MEDIUM"
    return "🟢 LOW"


def count_missing_critical(row, col_map):
    count = 0
    for field in CRITICAL_FIELDS:
        col = col_map.get(field)
        if col is None or pd.isna(row.get(col)) or str(row.get(col)).strip() == "":
            count += 1
    return count


def analyse_contracts(df):
    if df is None or df.empty:
        return pd.DataFrame()

    model = load_model()

    col_map = {}
    for field in EU_COLUMNS.keys():
        col = detect_column(df, field)
        if col:
            col_map[field] = col

    results = []

    for idx, row in df.iterrows():
        missing = count_missing_critical(row, col_map)

        val_col = col_map.get("contract_value_eur")
        try:
            actual = float(str(row.get(val_col, 0)).replace(",", "").replace("€", "").replace("£", "").strip()) if val_col and pd.notna(row.get(val_col)) else 0.0
        except Exception:
            actual = 0.0

        if model is not None:
            try:
                feat_df = build_feature_row(row, col_map)
                log_pred = model.predict(feat_df)[0]
                predicted = float(np.expm1(log_pred))
            except Exception as e:
                print(f"Model predict error: {e}")
                predicted = baseline_predict(row, col_map)
        else:
            predicted = baseline_predict(row, col_map)

        if actual > 0:
            score = calculate_risk_score(actual, predicted)
        else:
            score = 0.6 if missing >= 1 else 0.3

        flag = get_risk_flag(score, missing)

        results.append({
            "predicted_value_eur":     round(predicted, 2),
            "risk_score":              round(score, 4),
            "risk_flag":               flag,
            "missing_critical_fields": missing,
        })

    result_df = pd.DataFrame(results, index=df.index)
    return pd.concat([df, result_df], axis=1)


def risk_summary(results_df):
    if "risk_flag" not in results_df.columns:
        return {}
    flags = results_df["risk_flag"]
    total = len(flags)
    return {
        "total":          total,
        "high_risk":      int((flags.str.contains("HIGH")).sum()),
        "medium_risk":    int((flags.str.contains("MEDIUM")).sum()),
        "low_risk":       int((flags.str.contains("LOW")).sum()),
        "high_pct":       round((flags.str.contains("HIGH")).sum() / max(total, 1) * 100, 1),
        "medium_pct":     round((flags.str.contains("MEDIUM")).sum() / max(total, 1) * 100, 1),
        "low_pct":        round((flags.str.contains("LOW")).sum() / max(total, 1) * 100, 1),
        "avg_risk_score": round(results_df["risk_score"].mean(), 4) if "risk_score" in results_df.columns else 0,
    }
