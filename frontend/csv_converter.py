import os
import shutil
import pandas as pd
from pathlib import Path
import logging
import re

logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")

# folder paths for organizing files
SOURCE_FOLDER = "input_files"      # where we read uploaded files from
ORIGINAL_FOLDER = "original_files"  # where we backup original files
OUTPUT_FOLDER = "converted_csv"     # where we save converted csv files

# create these folders if they don't exist yet
os.makedirs(ORIGINAL_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ============================================================================
# file type detection - helps us know what kind of file we're dealing with
# this way we only run the code we actually need for each file type
# ============================================================================

class FileTypeFlags:
    """
    this class detects what type of file we're working with
    it checks the file extension and sets flags so we know how to process it
    this helps us avoid loading heavy libraries when we don't need them
    for example, csv files don't need pdf libraries at all
    """
    def __init__(self, file_path):
        self.file_path = file_path
        # get the file extension and make it lowercase for easier comparison
        self.extension = Path(file_path).suffix.lower()
        
        # set flags for each file type we support
        self.is_csv = self.extension == ".csv"
        self.is_excel = self.extension in [".xlsx", ".xls"]
        self.is_pdf = self.extension == ".pdf"
        self.is_image = self.extension in [".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"]
        
        # track whether we need to load the heavy pdf/ocr libraries
        self.needs_ocr_processing = self.is_pdf or self.is_image
        self.ocr_libs_loaded = False
    
    def __repr__(self):
        # nice string representation for debugging
        return f"FileType(csv={self.is_csv}, excel={self.is_excel}, pdf={self.is_pdf}, image={self.is_image})"


# ============================================================================
# lazy loading for pdf libraries
# we only import these heavy libraries when we actually need to process a pdf
# this saves a ton of memory and startup time for csv and excel files
# ============================================================================

class PDFLibraries:
    """
    lazy loader for pdf processing libraries
    instead of importing everything at startup, we only import when needed
    this makes csv and excel processing much faster because we skip the heavy imports
    
    think of it like this: why load 50mb of pdf tools if you're just copying a csv file?
    with lazy loading, we only pay the cost when we actually need it
    """
    def __init__(self):
        # these will store the imported modules once we load them
        self._pdfplumber = None
        self._camelot = None
        self._tabula = None
        self._pdf2image = None
        self._pytesseract = None
        self._PIL = None
        self._paddleocr = None
        self._paddleocr_reader = None
        self._cv2 = None
        
        # flags to track which libraries are available on this system
        self.pdfplumber_available = False
        self.camelot_available = False
        self.tabula_available = False
        self.pdf2image_available = False
        self.pytesseract_available = False
        self.paddleocr_available = False
        self.cv2_available = False
    
    @property
    def pdfplumber(self):
        """
        lazy load pdfplumber only when someone tries to use it
        this is called a property decorator - it looks like a variable but runs code
        the first time you access it, it imports the library
        after that, it just returns the already-imported version
        """
        if self._pdfplumber is None:
            try:
                import pdfplumber
                self._pdfplumber = pdfplumber
                self.pdfplumber_available = True
                logging.info("loaded pdfplumber library")
            except ImportError:
                logging.warning("pdfplumber not available - install with: pip install pdfplumber")
                self.pdfplumber_available = False
        return self._pdfplumber
    
    @property
    def camelot(self):
        """lazy load camelot - good for extracting tables from pdfs"""
        if self._camelot is None:
            try:
                import camelot
                self._camelot = camelot
                self.camelot_available = True
                logging.info("loaded camelot library")
            except ImportError:
                # it's ok if this isn't available, we have other methods
                self.camelot_available = False
        return self._camelot
    
    @property
    def tabula(self):
        """lazy load tabula - another library for pdf table extraction"""
        if self._tabula is None:
            try:
                import tabula
                self._tabula = tabula
                self.tabula_available = True
                logging.info("loaded tabula library")
            except ImportError:
                self.tabula_available = False
        return self._tabula
    
    @property
    def pdf2image(self):
        """
        lazy load pdf2image - converts pdf pages to images
        this is needed when the pdf is scanned and doesn't have real text
        """
        if self._pdf2image is None:
            try:
                from pdf2image import convert_from_path
                self._pdf2image = convert_from_path
                self.pdf2image_available = True
                logging.info("loaded pdf2image library")
            except ImportError:
                self.pdf2image_available = False
        return self._pdf2image
    
    @property
    def pytesseract(self):
        """
        lazy load pytesseract - traditional ocr engine
        ocr stands for optical character recognition
        it can read text from images, useful for scanned pdfs
        """
        if self._pytesseract is None:
            try:
                import pytesseract
                import PIL
                self._pytesseract = pytesseract
                self._PIL = PIL
                self.pytesseract_available = True
                logging.info("loaded pytesseract library")
            except ImportError:
                self.pytesseract_available = False
        return self._pytesseract
    
    @property
    def paddleocr(self):
        """
        lazy load paddleocr - this is the best ocr engine for our use case
        it's ai-based, fast (0.8 seconds per page), and 94% accurate
        perfect for invoices and receipts which is what we're working with
        """
        if self._paddleocr is None:
            try:
                from paddleocr import PaddleOCR
                self._paddleocr = PaddleOCR
                # initialize the ocr reader with settings for english documents
                # use_textline_orientation helps detect rotated text
                self._paddleocr_reader = PaddleOCR(
                    use_textline_orientation=True,
                    lang='en'
                )
                self.paddleocr_available = True
                logging.info("loaded paddleocr library - ready for scanned pdfs")
            except ImportError:
                logging.warning("paddleocr not available - install with: pip install paddleocr")
                self.paddleocr_available = False
            except Exception as e:
                logging.warning(f"paddleocr failed to initialize: {e}")
                self.paddleocr_available = False
        return self._paddleocr_reader
    
    @property
    def cv2(self):
        """
        lazy load opencv - used for image preprocessing
        helps clean up images before ocr to improve accuracy
        """
        if self._cv2 is None:
            try:
                import cv2
                self._cv2 = cv2
                self.cv2_available = True
                logging.info("loaded opencv library")
            except ImportError:
                self.cv2_available = False
        return self._cv2


# global instance of pdf libraries that we'll reuse
# this gets created the first time we need pdf processing
_pdf_libs = None

def get_pdf_libraries():
    """
    get or create the pdf libraries instance
    this ensures we only create one instance and reuse it
    """
    global _pdf_libs
    if _pdf_libs is None:
        _pdf_libs = PDFLibraries()
    return _pdf_libs


# ============================================================================
# utility functions for working with dataframes
# these help us clean up and organize the data we extract from files
# ============================================================================

# safe series converter
def to_str_series(obj):
    """
    safely convert an object to a pandas series of strings
    this is useful when we're not sure if we have a dataframe or series
    """
    if isinstance(obj, pd.DataFrame):
        obj = obj.iloc[0]
    return pd.Series(obj).astype(str)

def make_columns_unique(cols):
    """
    make sure all column names are unique by adding numbers to duplicates
    for example, if we have two columns named 'amount', they become 'amount' and 'amount_1'
    """
    seen = {}
    new_cols = []

    for c in cols:
        c = str(c).strip()
        if c not in seen:
            seen[c] = 0
            new_cols.append(c)
        else:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")

    return new_cols

def align_columns(df, header):
    """
    align dataframe columns to match a header
    this is used when we have tables spanning multiple pages
    we want them all to have the same column structure
    """
    df_cols = len(df.columns)
    hdr_cols = len(header)

    header = make_columns_unique(header)

    if df_cols == hdr_cols:
        # perfect match, just assign the header
        df.columns = header
    elif df_cols > hdr_cols:
        # dataframe has more columns, add extra column names
        extra = [f"extra_col_{i}" for i in range(df_cols - hdr_cols)]
        df.columns = make_columns_unique(header + extra)
    else:
        # dataframe has fewer columns, truncate header
        df.columns = make_columns_unique(header[:df_cols])

    return df

def repair_header(df):
    """
    detect and promote header row if current columns are numeric like 0,1,2
    sometimes pdfs extract with numbered columns instead of proper headers
    we scan the first few rows to find the actual header row
    also cleans up column names by removing newlines and extra spaces
    """
    if df.empty:
        return df

    # only try to repair if columns are currently just numbers
    if all(isinstance(c, int) for c in df.columns):
        # check the first 4 rows for a header-like row
        for i in range(min(4, len(df))):
            row = to_str_series(df.iloc[i]).str.strip()
            # count how many cells contain letters vs numbers
            alpha = row.str.contains(r"[A-Za-z]").sum()
            numeric = row.str.contains(r"^\d+(?:\.\d+)?$").sum()

            # if row is mostly text (not numbers), it's probably a header
            if alpha >= len(row) * 0.5 and numeric <= len(row) * 0.3:
                # use this row as header and start data from next row
                df2 = df.iloc[i + 1:].reset_index(drop=True)
                df2.columns = row
                logging.info(f"found header at row {i}")
                # clean up column names
                df2.columns = [str(c).replace('\n', ' ').replace('\r', ' ').strip() for c in df2.columns]
                return df2
    
    # even if we didn't repair, clean up existing column names
    df.columns = [str(c).replace('\n', ' ').replace('\r', ' ').strip() for c in df.columns]

    return df


# ============================================================================
# table continuation logic
# when pdfs have tables that span multiple pages, we need to detect and merge them
# ============================================================================

def row_looks_like_header(row):
    """
    check if a row looks like a header row
    headers usually have mostly text, while data rows have more numbers
    """
    row = to_str_series(row).str.strip()
    alpha = row.str.contains(r"[A-Za-z]").sum()
    numeric = row.str.contains(r"^\d+(?:\.\d+)?$").sum()
    return alpha >= len(row) * 0.5 and numeric <= len(row) * 0.3

def table_value_signature(df, sample_rows=5):
    """
    create a signature of the table based on whether columns are numeric or text
    this helps us identify if two tables from different pages are actually the same table
    for example, an invoice table might have signature: (text, numeric, numeric, numeric)
    """
    sig = []
    for col in df.columns:
        series = df.loc[:, col]

        if isinstance(series, pd.DataFrame):
            series = series.iloc[:, 0]

        s = to_str_series(series).dropna().head(sample_rows)
        # check what percentage of values are numbers
        numeric_ratio = s.str.match(r"^\d+(?:\.\d+)?$").mean()
        sig.append("numeric" if numeric_ratio > 0.6 else "text")

    return tuple(sig)

def detect_table_continuation(t1, t2):
    """
    detect if table t2 is a continuation of table t1
    this happens when invoices or reports span multiple pages
    we check if they have similar column structure and data types
    """
    if t1.empty or t2.empty:
        return False

    # tables should have similar number of columns
    if abs(len(t1.columns) - len(t2.columns)) > 2:
        return False

    # if t2 starts with a header row, it's likely a continuation
    if row_looks_like_header(t2.iloc[0]):
        return True

    # compare the data type signatures
    sig1 = table_value_signature(t1)
    sig2 = table_value_signature(t2)

    # if at least 70% of columns match, consider it a continuation
    matches = sum(a == b for a, b in zip(sig1, sig2))
    return matches >= min(len(sig1), len(sig2)) * 0.7


# ============================================================================
# text-based table reconstruction
# sometimes pdfs don't have proper table structure, just formatted text
# we try to reconstruct tables from the text layout
# ============================================================================

def reconstruct_table_from_text(pdf_path, page_num, pdf_libs):
    """
    try to reconstruct a table from raw text when table extraction fails
    this looks for patterns in text spacing to identify columns
    """
    with pdf_libs.pdfplumber.open(pdf_path) as pdf:
        text = pdf.pages[page_num - 1].extract_text()

    if not text:
        return []

    # split into lines and remove empty ones
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if len(lines) < 3:
        # too few lines to be a table
        return []

    # split each line by multiple spaces (common column separator in text)
    rows = [re.split(r"\s{2,}", ln) for ln in lines]
    max_cols = max(len(r) for r in rows)

    # need at least 2 columns to be a table
    if max_cols < 2:
        return []

    # pad rows to have same number of columns
    padded = [r + [""] * (max_cols - len(r)) for r in rows]
    return [pd.DataFrame(padded)]


# ============================================================================
# ocr functions for scanned pdfs
# when a pdf is scanned, it's basically just images of paper
# we need ocr to read the text from these images
# ============================================================================

def preprocess_image_for_ocr(image_path, pdf_libs):
    """
    preprocess an image to improve ocr accuracy
    this includes converting to grayscale, denoising, and adjusting contrast
    these steps can improve ocr accuracy by 10-20%
    """
    if not pdf_libs.cv2_available:
        # if opencv isn't available, just use original image
        return image_path
    
    try:
        import numpy as np
        cv2 = pdf_libs.cv2
        
        # read the image
        img = cv2.imread(image_path)
        
        # convert to grayscale (simpler for ocr to process)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # apply threshold to get black text on white background
        # otsu's method automatically finds the best threshold value
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # remove noise from the image
        denoised = cv2.fastNlMeansDenoising(thresh, None, 10, 7, 21)
        
        # save preprocessed image
        preprocessed_path = image_path.replace('.', '_preprocessed.')
        cv2.imwrite(preprocessed_path, denoised)
        
        logging.info(f"preprocessed image saved: {preprocessed_path}")
        return preprocessed_path
        
    except Exception as e:
        logging.warning(f"preprocessing failed: {e}, using original image")
        return image_path

def extract_text_with_paddleocr(image_path, pdf_libs):
    """
    extract text from an image using paddleocr
    paddleocr is currently the best free ocr engine for invoices
    it's fast (0.8 seconds per page) and accurate (94%)
    """
    if not pdf_libs.paddleocr_available:
        return None
    
    try:
        ocr = pdf_libs.paddleocr
        
        # run ocr on the image
        result = ocr.ocr(image_path)
        
        if not result or len(result) == 0:
            return None
        
        # newer paddleocr returns OCRResult object
        ocr_result = result[0]
        
        # check if it's an OCRResult object (dict-like)
        if hasattr(ocr_result, 'keys') and callable(ocr_result.keys):
            # it's a dict-like OCRResult object
            try:
                text_lines = []
                
                # the text is in 'rec_texts' key
                if 'rec_texts' in ocr_result:
                    rec_texts = ocr_result['rec_texts']
                    if isinstance(rec_texts, list):
                        text_lines = [str(t) for t in rec_texts if t]
                        logging.info(f"extracted {len(text_lines)} lines from rec_texts")
                
                if text_lines:
                    text = '\n'.join(text_lines)
                    logging.info(f"paddleocr extracted {len(text)} characters from OCRResult")
                    return text
                    
            except Exception as e:
                logging.warning(f"error extracting from OCRResult: {e}")
        
        # fallback: try old list format
        if isinstance(ocr_result, (list, tuple)):
            text_lines = []
            try:
                for line in ocr_result:
                    if isinstance(line, dict):
                        if 'text' in line:
                            text = line['text']
                            confidence = line.get('score', 1.0)
                        else:
                            continue
                    elif isinstance(line, (list, tuple)) and len(line) >= 2:
                        if isinstance(line[1], (list, tuple)) and len(line[1]) >= 1:
                            text = line[1][0]
                            confidence = line[1][1] if len(line[1]) > 1 else 1.0
                        elif isinstance(line[1], str):
                            text = line[1]
                            confidence = 1.0
                        else:
                            continue
                    else:
                        continue
                    
                    if confidence > 0.5:
                        text_lines.append(str(text))
            except Exception as e:
                logging.warning(f"error parsing ocr results: {e}")
            
            if text_lines:
                text = '\n'.join(text_lines)
                logging.info(f"paddleocr extracted {len(text)} characters from old format")
                return text
        
        logging.warning("could not extract text from paddleocr result")
        return None
        
    except Exception as e:
        logging.error(f"paddleocr failed: {e}")
        return None

def extract_text_with_tesseract(image_path, pdf_libs):
    """
    extract text using tesseract as a fallback option
    tesseract is older and less accurate than paddleocr
    but it's good to have as a backup
    """
    if not pdf_libs.pytesseract_available:
        return None
    
    try:
        from PIL import Image
        pytesseract = pdf_libs.pytesseract
        
        # open image and extract text
        image = Image.open(image_path)
        # psm 6 means we assume a uniform block of text
        text = pytesseract.image_to_string(image, config='--psm 6')
        
        logging.info(f"tesseract extracted {len(text)} characters")
        return text.strip()
        
    except Exception as e:
        logging.error(f"tesseract failed: {e}")
        return None

def extract_text_from_scanned_pdf_page(image_path, pdf_libs, preprocess=True):
    """
    extract text from a single scanned pdf page (converted to image)
    tries multiple ocr engines and picks the best result
    """
    # preprocess the image first if requested
    if preprocess:
        image_path = preprocess_image_for_ocr(image_path, pdf_libs)
    
    # try paddleocr first (it's the best)
    text = extract_text_with_paddleocr(image_path, pdf_libs)
    if text and len(text) > 20:  # got decent amount of text
        return text, 'paddleocr'
    
    # try tesseract as fallback
    text = extract_text_with_tesseract(image_path, pdf_libs)
    if text and len(text) > 20:
        return text, 'tesseract'
    
    # if both failed, return empty
    return "", "none"

def process_image_with_ocr(image_path, pdf_libs):
    """
    process an image file (jpg, png, etc) using ocr
    extracts text from the image and returns as dataframe
    """
    # trigger lazy loading of ocr libraries
    paddleocr_reader = pdf_libs.paddleocr
    cv2_module = pdf_libs.cv2
    
    if not pdf_libs.paddleocr_available and not pdf_libs.pytesseract_available:
        logging.error("no ocr libraries available (paddleocr or pytesseract)")
        print("error: no ocr libraries installed")
        print("to process images, install: pip install paddleocr opencv-python pillow")
        return []
    
    try:
        logging.info(f"processing image with ocr: {image_path}")
        print("running ocr on image...")
        
        # preprocess image if opencv is available
        processed_path = preprocess_image_for_ocr(image_path, pdf_libs)
        
        # extract text using ocr
        text, model_used = extract_text_from_scanned_pdf_page(processed_path, pdf_libs)
        
        if not text:
            logging.warning("no text extracted from image")
            return []
        
        # try to parse as invoice first
        parsed_df = parse_invoice_text_to_table(text)
        
        if parsed_df is not None and not parsed_df.empty:
            logging.info(f"parsed image text into {len(parsed_df)} line items with {len(parsed_df.columns)} columns")
            return [parsed_df]
        
        # if not an invoice, return as raw text
        df = pd.DataFrame({
            'extracted_text': [text],
            'extraction_method': [model_used],
            'file_type': ['image'],
            'total_characters': [len(text)]
        })
        
        logging.info(f"extracted {len(text)} characters from image using {model_used}")
        return [df]
        
    except Exception as e:
        logging.error(f"image ocr failed: {e}")
        print(f"error processing image: {e}")
        return []


def process_scanned_pdf_with_ocr(pdf_path, pdf_libs):
    """
    process a scanned pdf using ocr
    this converts each page to an image and then runs ocr on it
    returns extracted text combined from all pages
    """
    # trigger the lazy load by accessing the property
    pdf2image_func = pdf_libs.pdf2image
    
    if not pdf_libs.pdf2image_available:
        logging.error("pdf2image not available, cannot process scanned pdf")
        print("error: pdf2image library not installed")
        print("to process scanned pdfs, install: pip install pdf2image")
        print("\non mac, you also need poppler:")
        print("  brew install poppler")
        return []
    
    # trigger paddleocr and pytesseract lazy loading
    paddleocr_reader = pdf_libs.paddleocr
    tesseract = pdf_libs.pytesseract
    
    if not pdf_libs.paddleocr_available and not pdf_libs.pytesseract_available:
        logging.error("no ocr libraries available (paddleocr or pytesseract)")
        print("error: no ocr libraries installed")
        print("to process scanned pdfs, install: pip install paddleocr")
        return []
    
    try:
        # convert pdf to images (one image per page)
        logging.info(f"converting pdf to images for ocr: {pdf_path}")
        images = pdf_libs.pdf2image(pdf_path, dpi=300)  # 300 dpi is good for ocr
        
        results = []
        temp_folder = "ocr_temp"
        os.makedirs(temp_folder, exist_ok=True)
        
        # process each page
        for i, image in enumerate(images, 1):
            logging.info(f"running ocr on page {i}/{len(images)}...")
            
            # save image temporarily
            img_path = os.path.join(temp_folder, f"page_{i}.png")
            image.save(img_path, 'PNG')
            
            # extract text using ocr
            text, model_used = extract_text_from_scanned_pdf_page(img_path, pdf_libs)
            
            if text:
                results.append({
                    'page': i,
                    'text': text,
                    'model': model_used,
                    'char_count': len(text)
                })
            
            # clean up temp image
            try:
                os.remove(img_path)
            except:
                pass
        
        # clean up temp folder
        try:
            os.rmdir(temp_folder)
        except:
            pass
        
        logging.info(f"extracted text from {len(results)} pages using ocr")
        return results
        
    except Exception as e:
        logging.error(f"ocr processing failed: {e}")
        return []


# ============================================================================
# page level fallback pipeline for regular pdfs
# tries multiple methods to extract tables from a pdf page
# ============================================================================

def extract_tables_from_page(pdf_path, page_num, pdf_libs):
    """
    try to extract tables from a single pdf page
    uses multiple methods as fallbacks in case one fails
    returns list of dataframes (one per table found)
    """
    # first try: pdfplumber (usually works for most pdfs)
    try:
        with pdf_libs.pdfplumber.open(pdf_path) as pdf:
            page = pdf.pages[page_num - 1]
            tables = page.extract_tables()
            if tables:
                return [pd.DataFrame(t) for t in tables]
            # if no tables, try extracting single table
            table = page.extract_table()
            if table:
                return [pd.DataFrame(table)]
    except Exception as e:
        logging.debug(f"pdfplumber failed on page {page_num}: {e}")

    # second try: camelot (good for complex table layouts)
    if pdf_libs.camelot_available:
        for flavor in ("lattice", "stream"):
            try:
                tables = pdf_libs.camelot.read_pdf(pdf_path, pages=str(page_num), flavor=flavor)
                if tables and len(tables) > 0:
                    return [t.df for t in tables]
            except Exception as e:
                logging.debug(f"camelot {flavor} failed on page {page_num}: {e}")
    
    # third try: tabula (another table extraction method)
    if pdf_libs.tabula_available:
        try:
            dfs = pdf_libs.tabula.read_pdf(pdf_path, pages=str(page_num), multiple_tables=True)
            if dfs:
                return dfs
        except Exception as e:
            logging.debug(f"tabula failed on page {page_num}: {e}")

    # last resort: try text reconstruction
    return reconstruct_table_from_text(pdf_path, page_num, pdf_libs)


# ============================================================================
# pdf extraction with header locking
# extracts all tables from a pdf and maintains consistent headers across pages
# ============================================================================

def extract_tables_from_pdf(pdf_path, pdf_libs):
    """
    extract all tables from a pdf file
    maintains consistent column headers across pages
    this is important for multi-page invoices or reports
    """
    all_tables = []
    locked_header = None  # we'll use the first table's header for all subsequent tables

    # get total number of pages
    with pdf_libs.pdfplumber.open(pdf_path) as pdf:
        total_pages = len(pdf.pages)

    logging.info(f"extracting tables from {total_pages} pages...")

    # process each page
    for page_num in range(1, total_pages + 1):
        page_tables = extract_tables_from_page(pdf_path, page_num, pdf_libs)

        for raw_df in page_tables:
            raw_df = pd.DataFrame(raw_df)

            if locked_header is None:
                # first table: detect and lock the header
                raw_df = repair_header(raw_df)
                locked_header = make_columns_unique(list(raw_df.columns))
            else:
                # subsequent tables: align to locked header
                raw_df = align_columns(raw_df, locked_header)

            all_tables.append(raw_df)

    return all_tables


# ============================================================================
# group and merge tables
# combine tables that are continuations of each other
# ============================================================================

def group_tables_by_continuation(tables):
    """
    group tables that are continuations of each other
    for example, an invoice table that spans 3 pages becomes one group
    """
    if not tables:
        return []
    
    groups = []
    current = [tables[0]]

    for t in tables[1:]:
        if detect_table_continuation(current[-1], t):
            # this table continues the previous one
            current.append(t)
        else:
            # new table starts here
            groups.append(current)
            current = [t]

    # don't forget the last group
    groups.append(current)
    return groups

def merge_table_group(group):
    """
    merge a group of table continuations into a single dataframe
    removes duplicate headers and combines all data rows
    """
    base = group[0].copy()
    base.columns = make_columns_unique(base.columns)

    for nxt in group[1:]:
        if nxt.empty:
            continue

        # if next table starts with a header row, skip it
        if row_looks_like_header(nxt.iloc[0]):
            nxt = nxt.iloc[1:].reset_index(drop=True)

        # align columns and append
        nxt = align_columns(nxt, list(base.columns))
        base = pd.concat([base, nxt], ignore_index=True)

    return base


import re
import pandas as pd

def parse_invoice_table_from_ocr(text):
    """
    Parse invoice table from OCR text
    Handles table structure: Item | Description | Qty | Unit | Net Price | Net Worth | VAT% | Gross Worth
    """
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # Extract invoice metadata
    invoice_data = {}
    patterns = {
        'invoice_number': r'(?:invoice\s*(?:no|number|#))[\:\.\s]*\n?\s*([A-Z0-9]+)',
        'invoice_date': r'(?:date\s*of\s*issue|invoice\s*date)[\:\s]*\n?\s*(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
    }
    
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            invoice_data[field] = match.group(1).strip()
    
    # Find line items in structured table format
    line_items = []
    
    # Find ITEMS section
    items_start_idx = -1
    for i, line in enumerate(lines):
        if re.match(r'^ITEMS?\s*$', line, re.IGNORECASE):
            items_start_idx = i
            break
    
    if items_start_idx < 0:
        return None
    
    # Process each line after ITEMS header
    i = items_start_idx + 1
    
    # Skip table headers
    while i < len(lines) and re.match(r'^(no\.|description|qty|um|net|price|vat|gross|worth)', lines[i], re.IGNORECASE):
        i += 1
    
    # Process item rows
    while i < len(lines):
        line = lines[i]
        
        # Stop at SUMMARY
        if re.match(r'^SUMMARY\s*$', line, re.IGNORECASE):
            break
        
        # Pattern for a line with numbers in table format
        # Matches: "1 Description 3,00 each 209,00 627,00 10% 689,70"
        # Looks for: item_num description quantity unit net_price net_worth vat% gross_worth
        
        # Check if line has multiple comma-separated numbers (likely a data row)
        number_pattern = r'(\d{1,3}(?:[\.,]\d{2,3})?)'
        numbers = re.findall(number_pattern, line)
        
        # A valid item line should have at least 4 numbers: qty, net_price, net_worth, gross_worth
        if len(numbers) >= 4:
            # Extract item number (optional, at start)
            item_num_match = re.match(r'^(\d{1,2})[\.)]?\s+', line)
            item_num = item_num_match.group(1) if item_num_match else ''
            
            # Find all numbers with commas (these are prices/quantities in European format)
            price_numbers = re.findall(r'(\d{1,3}[,\.]\d{2})', line)
            
            if len(price_numbers) >= 4:
                # Typical structure: quantity, net_price, net_worth, gross_worth
                quantity = price_numbers[0]
                net_price = price_numbers[1]
                net_worth = price_numbers[2]
                # VAT percentage might be between net_worth and gross_worth
                vat_match = re.search(r'(\d{1,2})%', line)
                vat_percent = vat_match.group(1) if vat_match else ''
                gross_worth = price_numbers[-1]  # Last number is gross worth
                
                # Extract description (everything between item number and first number)
                desc_text = line
                if item_num:
                    desc_text = re.sub(r'^\d{1,2}[\.)]?\s+', '', desc_text)
                # Remove all numbers and units from the end
                desc_text = re.sub(r'\s+\d{1,3}[,\.]\d{2,}.*$', '', desc_text)
                
                # Look ahead for description continuation lines
                description_parts = [desc_text.strip()]
                j = i + 1
                while j < len(lines) and j < i + 3:
                    next_line = lines[j].strip()
                    # If next line has no numbers or prices, it's likely description continuation
                    if not re.search(r'\d{1,3}[,\.]\d{2}', next_line) and len(next_line) > 3:
                        if not re.match(r'^(ITEMS|SUMMARY|VAT|Total|\d+\.)', next_line, re.IGNORECASE):
                            description_parts.append(next_line)
                            j += 1
                        else:
                            break
                    else:
                        break
                
                description = ' '.join(description_parts)
                
                # Add line item
                if description and len(description) > 3:
                    line_items.append({
                        'item_number': item_num,
                        'description': description,
                        'quantity': quantity,
                        'unit_price': net_price,
                        'net_worth': net_worth,
                        'vat_percent': vat_percent,
                        'gross_worth': gross_worth
                    })
                
                # Skip the continuation lines we processed
                i = j
                continue
        
        i += 1
    
    # Create dataframe
    if line_items:
        df = pd.DataFrame(line_items)
        
        # Add invoice metadata
        for field, value in invoice_data.items():
            df[field] = value
        
        return df
    
    return None


def parse_invoice_text_to_table(text):
    """
    parse invoice text into a structured table
    this handles invoices where the table isn't detected by pdfplumber
    extracts common invoice fields and line items
    supports multiple formats: proforma invoices, childcare invoices, etc.
    """
    import re
    
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    # try to extract invoice metadata
    invoice_data = {}
    
    # patterns for common invoice fields (support both $ and £)
    # handle both same-line and multi-line formats
    patterns = {
        'invoice_number': r'(?:invoice\s*(?:no|number|#))[:\.\s]*\n?\s*([A-Z0-9]+)',
        'invoice_date': r'(?:invoice\s*date)[:\s]*\n?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})',
        'due_date': r'(?:due\s*date)[:\s]*\n?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})',
        'total': r'(?:^total|total\s*(?:price)?)[:\s]*\n?\s*[£$€]?\s*([\d,]+\.?\d+)',
        'from': r'from[:\s]*([A-Za-z\s]+?)(?:\n|$|TERMS)',
        'to': r'to[:\s]*([A-Za-z\s]+?)(?:\n|$|before)',
    }
    
    for field, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            invoice_data[field] = match.group(1).strip()
    
    # find line items - look for lines that have prices (£ or $)
    line_items = []
    
    # look for price lines (support £, $, €)
    price_pattern = r'[£$€]\s*([\d,]+\.?\d{2})'
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # look for price in current line
        price_match = re.search(price_pattern, line)
        
        if price_match:
            price = price_match.group(0)
            
            # skip if this is the total line
            if re.match(r'^\s*total', line, re.IGNORECASE):
                i += 1
                continue
            
            # look for quantity or hours in the same line
            quantity = ''
            
            # check for hours format (1h 45m, 2h, etc)
            hours_match = re.search(r'(\d+h\s*\d*m?)', line)
            if hours_match:
                quantity = hours_match.group(1)
            else:
                # check for regular number quantity
                qty_match = re.search(r'\b(\d{1,5})\b', line)
                if qty_match:
                    # make sure it's not part of a price
                    qty_str = qty_match.group(1)
                    if qty_str not in price:
                        quantity = qty_str
            
            # look back for description (up to 5 lines)
            description_parts = []
            j = i - 1
            while j >= 0 and j > i - 5:
                prev_line = lines[j]
                
                # stop if we hit a header line
                if re.match(r'^(description|item|hours|total|price)', prev_line, re.IGNORECASE):
                    break
                
                # stop if we hit another price line
                if re.search(price_pattern, prev_line):
                    break
                
                # skip lines that are just numbers or dates
                if re.match(r'^\d+$', prev_line) or re.match(r'^\d{1,2}\s+\w+\s+\d{4}$', prev_line):
                    j -= 1
                    continue
                
                # this is part of the description
                if prev_line and len(prev_line) > 2:
                    description_parts.insert(0, prev_line)
                
                j -= 1
            
            # combine description
            description = ' '.join(description_parts).strip()
            
            # only add if we have a meaningful description
            if description and len(description) > 3:
                line_items.append({
                    'description': description,
                    'quantity': quantity if quantity else '1',
                    'price': price
                })
        
        i += 1
    
    # if we found line items, create a dataframe
    if line_items:
        import pandas as pd
        df = pd.DataFrame(line_items)
        
        # add invoice metadata as columns
        for field, value in invoice_data.items():
            df[field] = value
        
        return df
    
    return None


def extract_text_from_pdf(pdf_path, pdf_libs):
    """
    extract raw text from a pdf when it has text but no tables
    this is faster than ocr and works for pdfs with formatted text
    now tries to parse invoice structure first
    """
    try:
        all_text = []
        with pdf_libs.pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    all_text.append(text)
                    logging.info(f"extracted {len(text)} characters from page {i}")
        
        combined_text = '\n\n'.join(all_text)
        
        if combined_text:
            # first try to parse as invoice
            parsed_df = parse_invoice_text_to_table(combined_text)
            
            if parsed_df is not None and not parsed_df.empty:
                logging.info(f"parsed invoice text into {len(parsed_df)} line items with {len(parsed_df.columns)} columns")
                return [parsed_df]
            
            # if parsing failed, return as raw text
            df = pd.DataFrame({
                'extracted_text': [combined_text],
                'extraction_method': ['text_extraction'],
                'pages_processed': [len(all_text)],
                'total_characters': [len(combined_text)]
            })
            
            logging.info(f"extracted {len(combined_text)} characters from {len(all_text)} pages")
            return [df]
        
        return []
        
    except Exception as e:
        logging.error(f"text extraction failed: {e}")
        return []


# ============================================================================
# detect if pdf is scanned
# checks if pdf has extractable text or is just images
# ============================================================================

def is_pdf_scanned(pdf_path, pdf_libs):
    """
    detect if a pdf is scanned (image-based) or has real text
    scanned pdfs need ocr, regular pdfs can use table extraction
    """
    try:
        with pdf_libs.pdfplumber.open(pdf_path) as pdf:
            # check first few pages for text
            pages_to_check = min(3, len(pdf.pages))
            total_text_length = 0
            
            for i in range(pages_to_check):
                text = pdf.pages[i].extract_text()
                if text:
                    total_text_length += len(text.strip())
            
            # if we found very little text, it's probably scanned
            # typical scanned page has 0-50 characters of extractable text
            # regular pdf page has 500+ characters
            if total_text_length < 100:
                logging.info("pdf appears to be scanned (little to no extractable text)")
                return True
            
            # check if extracted text looks like garbage
            # sometimes scanned pdfs have random characters
            if pages_to_check > 0:
                first_page_text = pdf.pages[0].extract_text()
                if first_page_text:
                    # count readable characters vs total
                    import string
                    readable = sum(c in string.printable for c in first_page_text)
                    if len(first_page_text) > 0 and (readable / len(first_page_text)) < 0.5:
                        logging.info("pdf text appears corrupted, treating as scanned")
                        return True
            
            logging.info("pdf appears to have extractable text")
            return False
            
    except Exception as e:
        logging.warning(f"could not determine if pdf is scanned: {e}, assuming it is scanned")
        return True


# ============================================================================
# main pdf processor
# coordinates all the pdf extraction logic
# ============================================================================

def process_pdf(pdf_path, pdf_libs):
    """
    main function to process a pdf file
    automatically detects if pdf is scanned or regular
    routes to appropriate extraction method
    returns list of dataframes
    """
    # detect if pdf is scanned early
    logging.info("analyzing pdf type...")
    is_scanned = is_pdf_scanned(pdf_path, pdf_libs)
    
    if is_scanned:
        # this is a scanned pdf, go straight to ocr
        logging.info("detected scanned pdf, using ocr extraction")
        print("detected scanned pdf, this will take longer (processing with ocr)...")
        
        ocr_results = process_scanned_pdf_with_ocr(pdf_path, pdf_libs)
        
        if not ocr_results:
            logging.warning("ocr extraction failed, no data extracted")
            return []
        
        # combine all pages into one text block
        all_text = '\n\n'.join([r['text'] for r in ocr_results])
        
        # FIX: Try to parse as invoice table first (same as regular PDFs)
        parsed_df = parse_invoice_table_from_ocr(all_text)
        if parsed_df is None or parsed_df.empty:
            parsed_df = parse_invoice_text_to_table(all_text)
        
        if parsed_df is not None and not parsed_df.empty:
            # Successfully parsed into structured table
            logging.info(f"parsed OCR text into {len(parsed_df)} line items with {len(parsed_df.columns)} columns")
            return [parsed_df]
        
        # If parsing failed, return as raw text (fallback to original behavior)
        df = pd.DataFrame({
            'extracted_text': [all_text],
            'extraction_method': ['ocr'],
            'pages_processed': [len(ocr_results)],
            'total_characters': [len(all_text)]
        })
        
        logging.info(f"ocr extracted {len(all_text)} characters from {len(ocr_results)} pages (raw text - parsing failed)")
        return [df]

    
    else:
        # this is a regular pdf with extractable text
        logging.info("detected regular pdf, using table extraction")
        print("processing regular pdf with table extraction...")
        
        tables = extract_tables_from_pdf(pdf_path, pdf_libs)
        
        # check if we got any meaningful data
        # tables with at least 1 row of data are valid (changed from > 1 to >= 1)
        if tables and any(not df.empty and len(df) >= 1 for df in tables):
            # we got tables with data, process them normally
            groups = group_tables_by_continuation(tables)
            result = [merge_table_group(g) for g in groups if not g[0].empty]
            
            if result:
                logging.info(f"successfully extracted {len(result)} tables")
                return result
        
        # no tables found, but pdf has text - try direct text extraction first
        logging.info("no tables found, trying direct text extraction...")
        print("no tables found, extracting text directly...")
        
        text_result = extract_text_from_pdf(pdf_path, pdf_libs)
        if text_result:
            return text_result
        
        # text extraction also didn't work, maybe it's actually scanned
        logging.info("text extraction failed, trying ocr as last resort...")
        print("text extraction failed, trying ocr as fallback...")
        
        ocr_results = process_scanned_pdf_with_ocr(pdf_path, pdf_libs)
        
        if not ocr_results:
            logging.warning("all extraction methods failed, no data extracted")
            return []
        
        # combine all pages into one text block
        all_text = '\n\n'.join([r['text'] for r in ocr_results])
        
        df = pd.DataFrame({
            'extracted_text': [all_text],
            'extraction_method': ['ocr'],
            'pages_processed': [len(ocr_results)],
            'total_characters': [len(all_text)]
        })
        
        logging.info(f"ocr extracted {len(all_text)} characters from {len(ocr_results)} pages")
        return [df]


# ============================================================================
# main conversion function with file type flags
# this is the heart of the optimization - we route each file type to the right handler
# ============================================================================

def convert_to_csv(input_path):
    """
    convert various file types to csv
    uses file type flags to determine the optimal processing path
    this avoids loading unnecessary libraries and speeds things up significantly
    """
    filename = os.path.basename(input_path)
    name, ext = os.path.splitext(filename)
    output_path = os.path.join(OUTPUT_FOLDER, f"{name}.csv")

    # step 1: detect file type early
    # this tells us exactly what we're dealing with before doing any heavy work
    file_flags = FileTypeFlags(input_path)
    logging.info(f"detected file type: {file_flags}")

    try:
        # step 2: route to the appropriate handler based on file type
        
        # csv files: fastest path - just copy the file
        if file_flags.is_csv:
            logging.info(f"{filename} is already csv, copying to output folder")
            print(f"{filename} is already csv, copying to converted_csv")
            shutil.copy(input_path, output_path)
            return output_path

        # excel files: standard conversion with pandas
        elif file_flags.is_excel:
            logging.info(f"converting excel file: {filename}")
            print(f"converting excel file: {filename}")
            df = pd.read_excel(input_path, sheet_name=0)
            df = repair_header(df)
            df.to_csv(output_path, index=False)
            logging.info(f"converted excel to csv: {output_path}")
            print(f"converted excel to csv: {output_path}")
            return output_path

        # pdf files: complex processing - load libraries only now
        elif file_flags.is_pdf:
            logging.info(f"processing pdf file: {filename}")
            print(f"processing pdf file: {filename}")
            print("loading pdf processing libraries...")
            
            # lazy load pdf libraries only when we actually need them
            pdf_libs = get_pdf_libraries()
            
            # check if pdfplumber is available by trying to access it
            # this triggers the lazy load
            pdfplumber_module = pdf_libs.pdfplumber
            if not pdf_libs.pdfplumber_available:
                logging.error("pdfplumber is required but not available")
                print("error: pdfplumber library not installed")
                print("install with: pip install pdfplumber")
                return None
            
            # process the pdf (handles both regular and scanned pdfs)
            tables = process_pdf(input_path, pdf_libs)
            
            if not tables:
                logging.warning(f"no data extracted from {filename}")
                print(f"\nerror: could not extract data from {filename}")
                print("\npossible reasons:")
                print("1. pdf is scanned but ocr libraries not installed")
                print("   solution: pip install paddleocr pillow pdf2image opencv-python")
                print("2. pdf has no tables or text")
                print("3. pdf is corrupted or password protected")
                print("\nto install ocr support:")
                print("   pip install paddleocr pillow pdf2image opencv-python")
                return None

            # save results to csv
            if len(tables) == 1:
                # single table, just save it
                tables[0].to_csv(output_path, index=False)
            else:
                # multiple tables, combine with separators
                combined = []
                for i, t in enumerate(tables):
                    # add a separator row between tables
                    sep = pd.DataFrame({t.columns[0]: [f"--- table {i+1} ---"]})
                    combined.extend([t, sep])
                pd.concat(combined, ignore_index=True).to_csv(output_path, index=False)
            
            logging.info(f"converted pdf to csv: {output_path}")
            print(f"converted pdf to csv: {output_path}")
            return output_path
        
        # image files: process with ocr
        elif file_flags.is_image:
            logging.info(f"processing image file: {filename}")
            print(f"processing image file: {filename}")
            print("loading ocr libraries...")
            
            # lazy load pdf libraries (which also has ocr)
            pdf_libs = get_pdf_libraries()
            
            # process the image with ocr
            tables = process_image_with_ocr(input_path, pdf_libs)
            
            if not tables:
                logging.warning(f"no data extracted from {filename}")
                print(f"\nerror: could not extract text from {filename}")
                print("\npossible reasons:")
                print("1. ocr libraries not installed")
                print("   solution: pip install paddleocr opencv-python pillow")
                print("2. image quality is too low")
                print("3. image contains no text")
                print("\nto install ocr support:")
                print("   pip install paddleocr opencv-python pillow")
                return None
            
            # save results to csv
            if len(tables) == 1:
                tables[0].to_csv(output_path, index=False)
            else:
                combined = []
                for i, t in enumerate(tables):
                    sep = pd.DataFrame({t.columns[0]: [f"--- image section {i+1} ---"]})
                    combined.extend([t, sep])
                pd.concat(combined, ignore_index=True).to_csv(output_path, index=False)
            
            logging.info(f"converted image to csv: {output_path}")
            print(f"converted image to csv: {output_path}")
            return output_path
        
        # unsupported file types
        else:
            logging.warning(f"unsupported file type: {filename}")
            print(f"unsupported file type: {filename}")
            return None

    except Exception as e:
        print(f"error converting {filename}: {e}")
        logging.error(f"error converting {filename}: {e}")
        return None


# ============================================================================
# batch processing
# process all files in the input folder
# ============================================================================

def process_all_files():
    """
    process all files in the source folder
    moves originals to backup folder after successful conversion
    """
    files = [f for f in os.listdir(SOURCE_FOLDER) if os.path.isfile(os.path.join(SOURCE_FOLDER, f))]
    
    logging.info(f"\nstarting batch conversion: {len(files)} files found")
    
    for file in files:
        full_path = os.path.join(SOURCE_FOLDER, file)
        logging.info(f"\nprocessing: {file}")

        # convert the file
        csv_out = convert_to_csv(full_path)
        
        # move original to backup folder if conversion succeeded
        try:
            if csv_out:
                shutil.move(full_path, os.path.join(ORIGINAL_FOLDER, file))
                logging.info(f"moved original file to {ORIGINAL_FOLDER}")
            else:
                logging.warning(f"conversion failed for {file}, leaving original in place")
        except Exception as e:
            logging.warning(f"failed to move original {file}: {e}")


# ============================================================================
# main entry point
# ============================================================================

if __name__ == "__main__":
    process_all_files()
    logging.info("\nall tasks complete")
    logging.info(f"originals stored in: {ORIGINAL_FOLDER}")
    logging.info(f"converted csvs stored in: {OUTPUT_FOLDER}")