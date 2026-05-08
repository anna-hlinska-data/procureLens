import pandas as pd
import numpy as np
import re

# =============================================================================
# DATE CLEANING
# =============================================================================

def clean_dates(df, date_columns=None):
    """
    Detect and normalize date columns to DD-MM-YYYY
    """

    df = df.copy()

    # Auto-detect date columns if not specified
    if date_columns is None:
        date_columns = []
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    parsed = pd.to_datetime(df[col], errors='coerce')
                    if (
                        parsed.notna().any()
                        and df[col].astype(str)
                        .str.contains(r'\d{1,4}[-/\.]\d{1,2}[-/\.]\d{1,4}', na=False)
                        .any()
                    ):
                        date_columns.append(col)
                except Exception:
                    pass

    if not date_columns:
        return df

    print(f"Cleaning date columns: {date_columns}\n")

    for col in date_columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
            df[col] = df[col].dt.strftime('%d-%m-%Y')
            print(f"{col} formatted to DD-MM-YYYY")

    return df


# =============================================================================
# MAIN DATA CLEANING
# =============================================================================

def clean_data(df, missing_threshold=0.5, fill_method='median', date_columns=None):
    """
    General data cleaning + date normalization
    """

    df = df.copy()

    print(f"Original shape: {df.shape}")
    print(f"Missing values: {df.isnull().sum().sum()}")
    print(f"Duplicates: {df.duplicated().sum()}\n")

    # -------------------------------------------------------------------------
    # 1. Drop columns with too many missing values
    # -------------------------------------------------------------------------
    missing_pct = df.isnull().sum() / len(df)
    cols_to_drop = missing_pct[missing_pct > missing_threshold].index.tolist()

    if cols_to_drop:
        print(f"Dropping columns: {cols_to_drop}")
        df = df.drop(columns=cols_to_drop)

    # -------------------------------------------------------------------------
    # 2. Clean dates FIRST (before filling categoricals)
    # -------------------------------------------------------------------------
    df = clean_dates(df, date_columns)

    # -------------------------------------------------------------------------
    # 3. Handle remaining missing values
    # -------------------------------------------------------------------------
    if fill_method == 'drop':
        df = df.dropna()
        print("Dropped rows with missing values")

    else:
        # Numeric columns
        num_cols = df.select_dtypes(include=[np.number]).columns
        if len(num_cols) > 0:
            if fill_method == 'mean':
                df[num_cols] = df[num_cols].fillna(df[num_cols].mean())
            else:
                df[num_cols] = df[num_cols].fillna(df[num_cols].median())

        # Categorical columns
        cat_cols = df.select_dtypes(include=['object', 'category']).columns
        for col in cat_cols:
            if df[col].isna().any():
                mode = df[col].mode()
                df[col] = df[col].fillna(mode[0] if not mode.empty else 'Unknown')

        print(f"Filled missing values using {fill_method}")

    # -------------------------------------------------------------------------
    # 4. Remove duplicates
    # -------------------------------------------------------------------------
    before = len(df)
    df = df.drop_duplicates()
    print(f"Removed {before - len(df)} duplicates\n")

    print(f"Final shape: {df.shape}")
    print(f"Remaining missing values: {df.isnull().sum().sum()}")

    return df


# =============================================================================
# OCR TEXT CLEANING (UNCHANGED, SAFE)
# =============================================================================

def clean_ocr_text(text_lines):
    """
    Parse OCR-extracted text into structured invoice line items
    """

    if not text_lines:
        return pd.DataFrame()

    if isinstance(text_lines, str):
        text = text_lines
        text_lines = text.split('\n')
    else:
        text = '\n'.join(text_lines)

    invoice_data = {}

    inv_match = re.search(r'invoice\s*no[:\s]*([A-Z0-9]+)', text, re.IGNORECASE)
    if inv_match:
        invoice_data['invoice_number'] = inv_match.group(1)

    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', text)
    if date_match:
        invoice_data['invoice_date'] = date_match.group(1)

    to_match = re.search(r'(?:to|client)[:\s]*([A-Za-z][A-Za-z\s]+?)(?:\n|\d)', text, re.IGNORECASE)
    if to_match:
        invoice_data['to'] = to_match.group(1).strip()

    line_items = []

    price_pattern_with_currency = r"[£$€]\s*[\d,.]+"
    price_pattern_no_currency = r"\d{1,3}[,\.]\d{2}"

    in_items_section = False
    i = 0

    while i < len(text_lines):
        line = text_lines[i].strip()

        if re.match(r'^ITEMS?\s*$', line, re.IGNORECASE):
            in_items_section = True
            i += 1
            continue

        if re.match(r'^SUMMARY\s*$', line, re.IGNORECASE):
            break

        if not in_items_section:
            i += 1
            continue

        if re.match(r'^(no\.|description|qty|um|net|price|vat|gross)', line, re.IGNORECASE):
            i += 1
            continue

        item_pattern = r'^(\d{1,2}[\.)]?)?\s*([A-Za-z].{10,}?)\s+(\d{1,2}[,\.]\d{2})$'
        match = re.match(item_pattern, line)

        if match:
            description = match.group(2).strip()
            quantity = match.group(3)

            price_match = re.search(price_pattern_with_currency, line) or \
                          re.search(price_pattern_no_currency, line)

            price = price_match.group(0) if price_match else quantity

            j = i + 1
            while j < len(text_lines) and j < i + 3:
                next_line = text_lines[j].strip()
                if next_line and not re.search(r'\d+[,\.]\d{2}', next_line):
                    description += ' ' + next_line
                    j += 1
                else:
                    break

            if len(description) > 5:
                line_items.append({
                    "description": description,
                    "quantity": quantity,
                    "price": price,
                    **invoice_data
                })

            i = j
            continue

        i += 1

    return pd.DataFrame(line_items)
