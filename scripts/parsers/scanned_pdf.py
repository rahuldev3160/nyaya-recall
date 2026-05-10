import pytesseract
from pdf2image import convert_from_path
from tqdm import tqdm


def extract_text(filepath: str, dpi: int = 200) -> str:
    images = convert_from_path(filepath, dpi=dpi)
    text_parts = []
    for img in tqdm(images, desc=f"OCR: {filepath.split('/')[-1]}", leave=False):
        text = pytesseract.image_to_string(img, lang="eng")
        if text.strip():
            text_parts.append(text)
    return "\n\n".join(text_parts)
