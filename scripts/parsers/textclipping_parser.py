import subprocess


def extract_text(filepath: str) -> str:
    """Extract text from macOS .textClipping files."""
    try:
        result = subprocess.run(["strings", filepath], capture_output=True, text=True, timeout=10)
        lines = [l.strip() for l in result.stdout.splitlines() if len(l.strip()) > 10]
        return "\n".join(lines)
    except Exception:
        try:
            with open(filepath, "rb") as f:
                return f.read().decode("utf-8", errors="ignore")
        except Exception:
            return ""
