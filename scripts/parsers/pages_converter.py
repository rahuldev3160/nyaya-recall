import subprocess
import tempfile
import os


def extract_text(filepath: str) -> str:
    """Convert Apple .pages file to text using macOS textutil (built-in)."""
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            ["textutil", "-convert", "txt", "-output", tmp_path, filepath],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(f"textutil error: {result.stderr}")
        with open(tmp_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
