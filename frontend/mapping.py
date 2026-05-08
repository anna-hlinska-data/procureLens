import os
import pandas as pd
import json
import re
import difflib
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# expanded master mapping with comprehensive variations to handle diverse invoice formats

master = {
    "transaction_id": [
        # standard variations
        "purchaseordernumber","productid","ordernumber","itemcode","invoiceno","ponumber",
        "purchaseid","poid","invoice","invoicenumber","invoiceid","billnumber","billno",
        "referencenumber","refno","documentnumber","docno","transactionid","orderid",
        # common abbreviations
        "po","inv","bill","ref","doc","txn","txnid","invoicenum","orderno","purchaseno",
        # with separators
        "invoice_no","invoice_number","order_no","order_number","po_no","po_number",
        "bill_no","bill_number","reference_no","ref_number","transaction_no",
        # international
        "numeryfaktury","nrfaktury","facturanumero","rechnungsnummer","factuurnummer",
        # chinese
        "发票号","发票编号","订单号","采购单号","单据号","交易号","凭证号"
    ],

    "item_name": [
        # standard variations
        "productname","item","item1","itemdescription","product","itemname","description",
        "productdescription","goods","article","merchandise","service","services",
        # detailed descriptions
        "itemdetails","productdetails","goodsdescription","articlename","itemtext",
        "descriptionofgoods","descriptionofservices","particulars","servicedetails",
        # with separators
        "item_name","item_description","product_name","product_description",
        "goods_description","article_name","service_name","service_description",
        # short forms
        "desc","prod","itm","itemdesc","proddesc",
        # international
        "produktname","productnaam","nombreproducto","nomeprodotto",
        # chinese
        "产品名称","商品名称","物品","货物","项目","品名","物料名称","服务名称"
    ],

    "item_category": [
        # standard variations
        "service","accountname","kraljiccategory","category","classification","catagory",
        "itemcategory","productcategory","type","itemtype","producttype","class","group",
        # detailed classifications
        "categoryname","classificationcode","categorycode","groupname","typename",
        "servicetype","productclass","itemclass","businessunit","segment","division",
        # with separators
        "item_category","product_category","item_type","product_type","service_type",
        "category_name","class_name","group_name",
        # short forms
        "cat","categ","typ","grp","cls",
        # international
        "categoria","categorie","kategorie","kategorija",
        # chinese
        "类别","分类","种类","类型","品类","产品类别","物料类别"
    ],

    "company": [
        # standard variations
        "organisationname","supplierregion","warehousecode","region","department","country",
        "warehouselocation","organization","companyname","company","firm","enterprise",
        # organizational details
        "organizationname","businessname","corporatename","legalname","tradename",
        "branchname","location","site","facility","division","unit","office",
        # geographic
        "regionname","territory","area","zone","district","sector","branch",
        # with separators
        "company_name","organization_name","business_name","branch_name","office_name",
        "warehouse_code","warehouse_location","region_name",
        # short forms
        "org","co","corp","ent","loc","dept",
        # international
        "empresa","entreprise","unternehmen","bedrijf","azienda",
        # chinese
        "公司","企业","组织","单位","部门","机构","公司名称","企业名称"
    ],

    "quantity": [
        # standard variations
        "ordervolumeunits","orderquantity","units","unitspurchased","quantity","volume",
        "stockquantity","reorderquantity","qty","amount","count","number","pieces",
        # detailed quantities
        "quantityordered","quantitydelivered","quantityinvoiced","totalpurchased",
        "numberofunits","numberofitems","volumeordered","ordervolume","orderamount",
        # with separators
        "order_quantity","units_purchased","stock_quantity","reorder_quantity",
        "quantity_ordered","quantity_delivered","number_of_units","order_volume",
        # short forms
        "qnty","qnt","amt","vol","pcs","nos","nbr","num",
        # international
        "quantite","menge","cantidad","quantita","hoeveelheid","ilosc",
        # chinese
        "数量","数额","件数","个数","总量","订单数量","采购数量"
    ],

    "supplier": [
        # standard variations
        "suppliername","vendor","supplier","vendorname","supplierid","vendorid",
        # detailed supplier info
        "sellername","seller","providername","provider","merchantname","merchant",
        "contractorname","contractor","dealername","dealer","distributorname","distributor",
        # with separators
        "supplier_name","vendor_name","seller_name","provider_name","merchant_name",
        "contractor_name","dealer_name","distributor_name","supplier_id","vendor_id",
        # regional variations
        "supplierregion","vendorregion","suppliercompany","vendorcompany",
        # short forms
        "supp","vend","sell","prov","distr",
        # international
        "fournisseur","lieferant","proveedor","fornitore","leverancier","dostawca",
        # chinese
        "供应商","供货商","卖方","销售商","提供商","厂商","供应商名称"
    ],

    "buyer": [
        # standard variations
        "buyer","invoicedby","customername","customerid","department","customer",
        "clientname","client","purchasername","purchaser","consumername","consumer",
        # detailed buyer info
        "buyername","buyercompany","customercompany","clientcompany","billto",
        "billedto","soldto","shiptocustomer","enduser","recipient","consignee",
        # with separators
        "buyer_name","customer_name","client_name","purchaser_name","consumer_name",
        "customer_id","client_id","buyer_id","invoiced_by","billed_to","sold_to",
        # short forms
        "cust","cli","purch","cons","recip",
        # international
        "acheteur","kaufer","comprador","acquirente","koper","kupujacy","cliente",
        # chinese
        "买方","客户","采购方","购买方","客户名称","收货人","收货单位"
    ],

    "unit_price": [
        # standard variations
        "costperunit","unitprice","unit_price","priceperunit","price","rate","unitcost",
        "unitrate","priceperitem","costperitem","itemcost","itemprice","productprice",
        # detailed pricing
        "unitpriceamount","priceperpiece","costperpiece","rateperunit","unitamount",
        "singleprice","individualprice","eachprice","perprice","unitvalue",
        # with separators
        "cost_per_unit","price_per_unit","price_per_item","cost_per_item","unit_rate",
        "item_price","product_price","unit_amount","price_each",
        # short forms
        "uprice","ucost","urate","ppu","cpu","priceea","rateper",
        # international
        "preciounitario","prixunitaire","einzelpreis","prezzounitario","eenheidsprijs","cenazasztuke",
        # chinese
        "单价","单位价格","件价","个价","每件价格","产品单价","物料单价"
    ],

    "total_cost": [
        # standard variations
        "totalvalue","totalamount","extendedprice","totalspend","linetotal","subtotal",
        "total_cost","negotiatedprice","total","amount","grandtotal","finaltotal","sum",
        # detailed totals
        "totalcost","totalcharge","totalexpense","totalexpenditure","totaloutlay",
        "invoicetotal","invoiceamount","billtotal","billamount","ordertotal","orderamount",
        "grosstotal","nettotal","amountdue","amountpayable","totalprice","totalvalue",
        # with separators
        "total_amount","total_value","grand_total","final_total","line_total",
        "invoice_total","invoice_amount","bill_total","order_total","amount_due",
        # short forms
        "tot","ttl","amt","val","gross","net","due",
        # international
        "montanttotal","gesamtbetrag","totalimporte","totalecosto","totaalbedrag","sumacalkowita",
        # chinese
        "总额","总价","总计","合计","金额","总金额","总成本","应付金额"
    ],

    "purchase_date": [
        # standard variations
        "orderdate","purchasedate","dateofpurchase","invoicedate","datereceived","date",
        "transactiondate","billingdate","billdate","issuedate","creationdate","documentdate",
        # detailed dates
        "dateordered","dateinvoiced","datebilled","dateissued","datecreated","dateprocessed",
        "orderplaced","invoicecreated","purchasemade","transactioncreated",
        # with separators
        "order_date","purchase_date","invoice_date","date_received","transaction_date",
        "billing_date","bill_date","issue_date","creation_date","document_date",
        "date_ordered","date_invoiced","date_created","date_issued",
        # short forms
        "dt","dte","orderdt","invoicedt","purchasedt","billdt","transdt",
        # international
        "fecha","datum","data","date","fechafactura","datumfactuur","datafattura",
        # chinese
        "日期","订单日期","采购日期","发票日期","交易日期","开票日期","下单日期"
    ]
}

# field type expectations for context-aware matching
FIELD_TYPES = {
    "transaction_id": "id",
    "item_name": "text",
    "item_category": "text",
    "company": "text",
    "quantity": "quantity",
    "supplier": "text",
    "buyer": "text",
    "unit_price": "price",
    "total_cost": "price",
    "purchase_date": "date"
}

# words that mean the same thing across different invoice formats
SYNONYMS = {
    "supplier": ["vendor", "seller", "provider", "merchant", "contractor", "dealer"],
    "buyer": ["customer", "client", "purchaser", "consumer"],
    "quantity": ["qty", "amount", "count", "number", "volume"],
    "price": ["cost", "rate", "value", "charge"],
    "date": ["dt", "dte"],
    "total": ["sum", "amount", "grand", "final"],
    "invoice": ["bill", "receipt", "document"],
    "order": ["purchase", "po", "transaction"]
}


# utility functions for text processing

def normalize(col):
    """Normalize column names by removing special characters and lowercasing."""
    # handle chinese characters by keeping them intact
    normalized = re.sub(r'[^a-z0-9\u4e00-\u9fff]', '', str(col).lower())
    return normalized


def expand_with_synonyms(variations: List[str]) -> List[str]:
    """Expand variations with synonyms to increase match probability."""
    expanded = set(variations)
    
    for var in variations:
        var_lower = var.lower()
        for key, synonyms in SYNONYMS.items():
            if key in var_lower:
                for syn in synonyms:
                    new_var = var_lower.replace(key, syn)
                    expanded.add(new_var)
    
    return list(expanded)


def prepare_headers(df: pd.DataFrame, max_check_rows: int = 5) -> pd.DataFrame:
    """
    Intelligently detect and fix header rows in CSV files.
    Handles cases where headers are not in the first row.
    """
    df = df.copy()

    # drop completely empty leading rows
    while len(df) > 0 and df.iloc[0].isna().all():
        df = df.iloc[1:].reset_index(drop=True)

    if df.empty:
        return df
    
    # check if the current header looks obviously wrong
    col_strs = [str(c) for c in df.columns]
    
    def looks_unnamed(c: str) -> bool:
        c_low = c.lower()
        return (
            c_low.startswith("unnamed")
            or c_low.startswith("column")
            or re.match(r"^x\d+$", c_low) is not None
            or c_low.strip() == ""
        )
    
    num_bad = sum(1 for c in col_strs if looks_unnamed(c))
    header_bad = num_bad >= len(col_strs) / 2

    if not header_bad:
        return df

    # try to find a better header row among the first few rows
    for i in range(min(max_check_rows, len(df))):
        row = df.iloc[i]
        if row.isna().all():
            continue

        str_vals = row.astype(str)
        has_letters = str_vals.str.contains(r"[A-Za-z]", regex=True, na=False).sum()

        # if at least half of the columns have letters, treat this row as header
        if has_letters >= len(df.columns) / 2:
            new_cols = [str(v).strip() if pd.notna(v) else "" for v in row]
            df2 = df.iloc[i + 1:].reset_index(drop=True)
            df2.columns = new_cols
            return df2
            
    return df


# ==================== TYPE INFERENCE ====================

def infer_column_type(df: pd.DataFrame, col: str, sample_size: int = 100) -> str:
    """
    Infer the data type of a column by analyzing its contents.
    Returns: 'date', 'price', 'quantity', 'id', or 'text'
    """
    if col not in df.columns:
        return "text"
    
    sample = df[col].dropna().head(sample_size)
    
    if len(sample) == 0:
        return "text"
    
    sample_str = sample.astype(str)
    
    # check for dates
    date_patterns = [
        r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}',   # DD/MM/YYYY or MM/DD/YYYY
        r'\d{4}[/-]\d{1,2}[/-]\d{1,2}',     # YYYY-MM-DD
        r'\d{1,2}[.]\d{1,2}[.]\d{2,4}',     # DD.MM.YYYY
        r'\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
    ]
    date_matches = sample_str.str.contains("|".join(date_patterns), regex=True, case=False).sum()
    if date_matches > len(sample) * 0.6:
        return "date"
    
    # check for prices
    price_patterns = r'[\$£€¥₽]?\s*\d+[,.]?\d*[.,]?\d*'
    price_matches = sample_str.str.match(price_patterns).sum()
    if price_matches > len(sample) * 0.7:
        has_decimals = sample_str.str.contains(r"[.,]\d+").sum()
        if has_decimals > len(sample) * 0.3:
            return "price"
    
    # check for quantities (mostly integers)
    try:
        numeric_vals = pd.to_numeric(sample, errors="coerce")
        if numeric_vals.notna().sum() > len(sample) * 0.8:
            if (numeric_vals.dropna() % 1 == 0).sum() > len(numeric_vals.dropna()) * 0.8:
                return "quantity"
            else:
                return "price"
    except Exception:
        pass
    
    # check for ID-like fields
    id_patterns = r"^[A-Z0-9\-_#]+$"
    id_matches = sample_str.str.upper().str.match(id_patterns).sum()
    if id_matches > len(sample) * 0.7:
        return "id"
    
    return "text"


# ==================== ADVANCED MATCHING ALGORITHMS ====================

def calculate_match_score(field_name: str, variations: List[str],
                          column_name: str, confidence_boost: float = 0.0) -> float:
    """
    Calculate a comprehensive match score between a field and column name.
    Returns a score between 0.0 and 1.0 + confidence_boost.
    """
    scores = []
    norm_col = normalize(column_name)
    
    # expand variations with synonyms
    expanded_vars = expand_with_synonyms(variations)
    
    # 1. exact match
    for v in expanded_vars:
        if normalize(v) == norm_col:
            return 1.0 + confidence_boost
    
    # 2. substring match
    for v in expanded_vars:
        norm_v = normalize(v)
        if len(norm_v) > 3:
            if norm_v in norm_col or norm_col in norm_v:
                match_len = min(len(norm_v), len(norm_col))
                total_len = max(len(norm_v), len(norm_col))
                scores.append(0.85 * (match_len / total_len))
    
    # 3. fuzzy (sequence matcher)
    for v in expanded_vars[:5]:
        ratio = difflib.SequenceMatcher(None, normalize(v), norm_col).ratio()
        scores.append(ratio * 0.9)
    
    # 4. token overlap
    field_tokens = set(re.findall(r"[a-z]{2,}", normalize(field_name)))
    col_tokens = set(re.findall(r"[a-z]{2,}", norm_col))
    
    if field_tokens and col_tokens:
        token_overlap = len(field_tokens & col_tokens) / len(field_tokens)
        scores.append(token_overlap * 0.8)
    
    # 5. acronym matching
    if len(field_tokens) > 1:
        acronym = "".join([t[0] for t in field_tokens if len(t) > 0])
        if len(acronym) > 1 and (acronym in norm_col or norm_col in acronym):
            scores.append(0.75)
    
    # 6. synonym-aware matching
    for syn_key, synonyms in SYNONYMS.items():
        if syn_key in normalize(field_name):
            for syn in synonyms:
                if syn in norm_col:
                    scores.append(0.80)
    
    return max(scores) if scores else 0.0


def enhanced_auto_map(df: pd.DataFrame, verbose: bool = True,
                      min_confidence: float = 0.6) -> Tuple[pd.DataFrame, Dict]:
    """
    Multi-stage column mapping algorithm with type inference and scoring.
    
    Args:
        df: Input DataFrame
        verbose: Whether to print detailed matching info
        min_confidence: Minimum confidence score to accept a match
    
    Returns:
        mapped_dataframe, mapping_report
    """
    if df is None or df.empty:
        return df, {}
    
    df_norm = {normalize(c): c for c in df.columns}
    n = len(df)
    
    # infer column types
    if verbose:
        print("\nAnalyzing column types...")
    column_types = {col: infer_column_type(df, col) for col in df.columns}
    
    if verbose:
        preview = dict(list(column_types.items())[:5])
        print(f"   Detected types (sample): {preview}\n")
    
    mapped = {}
    used_original_cols = set()
    mapping_report = {
        "successful_mappings": {},
        "failed_mappings": [],
        "confidence_scores": {},
        "column_types": column_types,
        "low_confidence_warnings": []
    }
    
    # multi-stage matching with scoring
    for field, variations in master.items():
        found = None
        best_score = 0.0
        expected_type = FIELD_TYPES.get(field, "text")
        
        # calculate scores for all columns
        candidates = []
        for norm_col, orig_col in df_norm.items():
            type_boost = 0.15 if column_types.get(orig_col) == expected_type else 0.0
            score = calculate_match_score(field, variations, orig_col, type_boost)
            
            if score > min_confidence:
                candidates.append((orig_col, score, norm_col))
        
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        for orig_col, score, norm_col in candidates:
            if orig_col not in used_original_cols:
                found = orig_col
                best_score = score
                break
        
        # fallback fuzzy match if still nothing found
        if not found:
            for v in variations[:3]:
                matches = difflib.get_close_matches(
                    v,
                    [nc for nc, oc in df_norm.items() if oc not in used_original_cols],
                    n=1,
                    cutoff=0.65
                )
                if matches:
                    found = df_norm[matches[0]]
                    best_score = 0.65
                    break
        
        if found:
            mapped[field] = df[found].reset_index(drop=True)
            used_original_cols.add(found)
            mapping_report["successful_mappings"][field] = found
            mapping_report["confidence_scores"][field] = round(best_score, 3)
            
            if best_score < 0.75:
                mapping_report["low_confidence_warnings"].append({
                    "field": field,
                    "matched_to": found,
                    "confidence": round(best_score, 3)
                })
            
            if verbose:
                if best_score > 0.85:
                    level = "HIGH"
                elif best_score > 0.7:
                    level = "MEDIUM"
                else:
                    level = "LOW"
                print(f"Mapped {field:20s} <- {found:35s} [confidence {level}] ({best_score:.3f})")
        else:
            mapped[field] = pd.Series([None] * n)
            mapping_report["failed_mappings"].append(field)
            
            if verbose:
                print(f"Could not map field {field}")
    
    # build mapped dataframe
    mapped_df = pd.DataFrame(mapped)
    
    # add unmatched original columns
    unmatched_cols = [c for c in df.columns if c not in used_original_cols]
    mapping_report["unmapped_columns"] = unmatched_cols
    
    if unmatched_cols:
        unmatched_df = df[unmatched_cols].reset_index(drop=True)
        result_df = pd.concat([mapped_df, unmatched_df], axis=1)
    else:
        result_df = mapped_df
    
    if verbose and unmatched_cols:
        preview_unmapped = ", ".join(unmatched_cols[:5])
        if len(unmatched_cols) > 5:
            print(f"\nUnmapped columns (first 5): {preview_unmapped} ... and {len(unmatched_cols) - 5} more")
        else:
            print(f"\nUnmapped columns: {preview_unmapped}")
    
    return result_df, mapping_report


# ==================== LEGACY FUNCTION ====================

def auto_map(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compatibility wrapper that returns only the mapped DataFrame.
    """
    result_df, _ = enhanced_auto_map(df, verbose=False)
    return result_df


# ==================== BATCH PROCESSING ====================

def batch_map(input_folder: str = "converted_csv",
              output_folder: str = "mapped_files",
              logs_folder: str = "logs",
              save_reports: bool = True,
              min_confidence: float = 0.6):
    """
    Batch process multiple CSV files with enhanced mapping.
    """
    os.makedirs(output_folder, exist_ok=True)
    os.makedirs(logs_folder, exist_ok=True)
    
    failed = []
    all_reports = {}

    files = [f for f in os.listdir(input_folder) if f.endswith(".csv")]
    print("\n" + "=" * 80)
    print("ULTRA-ENHANCED INVOICE MAPPER")
    print("=" * 80)
    print(f"Found {len(files)} CSV files to process")
    print(f"Minimum confidence threshold: {min_confidence}")
    print(f"Input folder:  {input_folder}")
    print(f"Output folder: {output_folder}")
    print("=" * 80 + "\n")

    for i, file in enumerate(files, 1):
        print("\n" + "-" * 80)
        print(f"[{i}/{len(files)}] Processing: {file}")
        print("-" * 80)

        path = os.path.join(input_folder, file)

        try:
            df = pd.read_csv(path)
            print(f"Original shape: {df.shape}")
            
            df = prepare_headers(df)
            print(f"After header fix: {df.shape}")
            if len(df.columns) > 5:
                print(f"Columns found (first 5): {list(df.columns[:5])}...")
            else:
                print(f"Columns found: {list(df.columns)}")
            
            mapped_df, report = enhanced_auto_map(df, verbose=True, min_confidence=min_confidence)

            if mapped_df is None or mapped_df.empty:
                failed.append({"file": file, "error": "empty mapping"})
                print("\nFailed: empty mapping")
                continue

            # save mapped CSV
            out_path = os.path.join(output_folder, f"{Path(file).stem}_mapped.csv")
            mapped_df.to_csv(out_path, index=False)
            
            # save individual report
            if save_reports:
                report_path = os.path.join(logs_folder, f"{Path(file).stem}_report.json")
                with open(report_path, "w", encoding="utf-8") as f:
                    json.dump(report, f, indent=4, ensure_ascii=False)
            
            all_reports[file] = report
            
            # summary statistics
            matched = len(report["successful_mappings"])
            total_fields = len(master)
            match_rate = matched / total_fields * 100
            avg_conf = (
                sum(report["confidence_scores"].values())
                / max(len(report["confidence_scores"]), 1)
            )
            
            print("\n" + "-" * 80)
            print(f"SUCCESS: {Path(file).stem}_mapped.csv")
            print(f"Match rate: {matched}/{total_fields} fields ({match_rate:.1f}%)")
            print(f"Average confidence: {avg_conf:.3f}")
            print(f"Unmapped original columns: {len(report['unmapped_columns'])}")
            
            if report["low_confidence_warnings"]:
                print(f"Low confidence matches: {len(report['low_confidence_warnings'])}")
                for warn in report["low_confidence_warnings"][:3]:
                    print(
                        f"  - {warn['field']} -> {warn['matched_to']} "
                        f"(confidence {warn['confidence']})"
                    )
            print("-" * 80)

        except Exception as e:
            failed.append({"file": file, "error": str(e)})
            print(f"\nFailed: {e}")
            import traceback
            traceback.print_exc()

    # combine mapped files
    print("\n" + "=" * 80)
    print("Combining all mapped files...")
    
    combined_list = []
    for file in files:
        csv_path = os.path.join(output_folder, f"{Path(file).stem}_mapped.csv")
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            df["source_file"] = file
            combined_list.append(df)

    if combined_list:
        combined_df = pd.concat(combined_list, ignore_index=True)
        combined_path = os.path.join(output_folder, "ALL_INVOICES_COMBINED.csv")
        combined_df.to_csv(combined_path, index=False)
        print(f"Combined CSV saved: {combined_df.shape[0]} rows x {combined_df.shape[1]} columns")

    # save summary report
    if save_reports:
        summary_report = {
            "total_files": len(files),
            "successful": len(files) - len(failed),
            "failed": len(failed),
            "failed_files": failed,
            "overall_statistics": {
                "avg_match_rate": (
                    sum(len(r["successful_mappings"]) for r in all_reports.values())
                    / max(len(all_reports), 1)
                    / len(master)
                    * 100
                ),
                "avg_confidence": (
                    sum(
                        sum(r["confidence_scores"].values())
                        / max(len(r["confidence_scores"]), 1)
                        for r in all_reports.values()
                    )
                    / max(len(all_reports), 1)
                ),
                "total_low_confidence_warnings": sum(
                    len(r["low_confidence_warnings"]) for r in all_reports.values()
                ),
            },
            "individual_reports": all_reports,
        }
        
        summary_path = os.path.join(logs_folder, "mapping_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary_report, f, indent=4, ensure_ascii=False)
        
        print(f"Summary report saved: {summary_path}")

    # save failure log
    if failed:
        fail_path = os.path.join(logs_folder, "failed_files.json")
        with open(fail_path, "w", encoding="utf-8") as f:
            json.dump(failed, f, indent=4, ensure_ascii=False)

    print("\n" + "=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Successful files: {len(files) - len(failed)}/{len(files)}")
    print(f"Failed files:     {len(failed)}/{len(files)}")
    if all_reports:
        avg_match = (
            sum(len(r["successful_mappings"]) for r in all_reports.values())
            / len(all_reports)
        )
        print(f"Average fields matched: {avg_match:.1f}/{len(master)}")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    batch_map()