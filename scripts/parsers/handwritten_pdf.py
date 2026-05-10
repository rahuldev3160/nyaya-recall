import anthropic
import base64
import io
import os
from pdf2image import convert_from_path
from tqdm import tqdm


def extract_text(filepath: str, dpi: int = 150) -> str:
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    images = convert_from_path(filepath, dpi=dpi)
    text_parts = []

    for i, img in enumerate(tqdm(images, desc=f"Vision OCR: {filepath.split('/')[-1]}", leave=False)):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

        response = client.messages.create(
            model=os.getenv("AI_MODEL_FAST", "claude-haiku-4-5-20251001"),
            max_tokens=4096,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
                    {"type": "text", "text": (
                        "Transcribe all handwritten text in this image exactly as written. "
                        "Include all text, headings, bullet points, arrows, and margin notes. "
                        "Preserve structure where possible. Output only the transcribed text."
                    )}
                ]
            }]
        )
        text = response.content[0].text.strip()
        if text:
            text_parts.append(f"[Page {i + 1}]\n{text}")

    return "\n\n".join(text_parts)
