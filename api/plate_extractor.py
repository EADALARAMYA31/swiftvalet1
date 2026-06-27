import re
import base64
import cv2
import numpy as np

reader = None


def get_reader():
    global reader
    if reader is None:
        import easyocr
        print("Loading EasyOCR...")
        reader = easyocr.Reader(["en"], gpu=False)
        print("EasyOCR loaded.")
    return reader


# ---------------- IMAGE PREPROCESSING ----------------
def preprocess_image(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # upscale helps OCR a lot
    gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

    # denoise
    gray = cv2.bilateralFilter(gray, 9, 75, 75)

    # improve contrast
    gray = cv2.equalizeHist(gray)

    # threshold (important for plates)
    gray = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31, 2
    )

    return gray


# ---------------- CLEAN TEXT ----------------
def clean_text(text):
    if not text:
        return ""

    text = text.upper()
    text = re.sub(r"[^A-Z0-9]", "", text)
    return text


# ---------------- PLATE PATTERNS ----------------
def match_plate(text):
    patterns = [
        r"[A-Z]{2}\d{2}[A-Z]{1,3}\d{4}",   # AP39AB1234
        r"[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}", # MH14A1234
        r"[A-Z]{2}\d{2}[A-Z]{2}\d{4}",     # AP39AB1234 (alt)
    ]

    for p in patterns:
        match = re.search(p, text)
        if match:
            return match.group(0)

    return None


# ---------------- MAIN FUNCTION ----------------
def extract_plate_from_image(image_base64):
    try:
        if not image_base64:
            return "PLATE_NOT_FOUND"

        image_bytes = base64.b64decode(image_base64)
        np_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(np_array, cv2.IMREAD_COLOR)

        if img is None:
            return "PLATE_NOT_FOUND"

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)

        ocr = get_reader()

        results = ocr.readtext(gray, detail=1)

        text_all = ""

        for r in results:
            text_all += r[1] + " "

        text_all = text_all.upper()
        text_all = re.sub(r"[^A-Z0-9]", "", text_all)

        print("OCR RAW TEXT:", text_all)

        match = re.search(r"[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{4}", text_all)

        if match:
            return match.group(0)

        return "PLATE_NOT_FOUND"

    except Exception as e:
        print("OCR ERROR:", e)
        return "PLATE_NOT_FOUND"