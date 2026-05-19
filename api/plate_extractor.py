import re
import base64
import cv2
import numpy as np

reader = None


def clean_plate(text):
    text = str(text).upper()
    text = re.sub(r"[^A-Z0-9]", "", text)

    matches = re.findall(r"[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}", text)
    if matches:
        return matches[0]

    return text[:20] if text else "PLATE_NOT_FOUND"


def get_reader():
    global reader

    if reader is None:
        import easyocr
        print("Loading EasyOCR only now...")
        reader = easyocr.Reader(["en"], gpu=False)
        print("EasyOCR loaded.")

    return reader


def extract_plate_from_image(image_input):
    try:
        if not image_input:
            return "PLATE_NOT_FOUND"

        image_bytes = base64.b64decode(image_input)

        img_array = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

        if img is None:
            return "PLATE_NOT_FOUND"

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        gray = cv2.bilateralFilter(gray, 11, 17, 17)

        ocr_reader = get_reader()
        results = ocr_reader.readtext(gray)

        print("OCR RESULTS:", results)

        all_text = " ".join([r[1] for r in results])

        return clean_plate(all_text)

    except Exception as e:
        print("PLATE EXTRACTION ERROR:", e)
        return "PLATE_NOT_FOUND"