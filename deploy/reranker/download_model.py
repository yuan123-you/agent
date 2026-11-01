"""Download exactly the pinned model artifacts into an explicitly supplied directory."""
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

LOCK = json.loads(Path(__file__).with_name("model-lock.json").read_text())


def download(directory):
    root = Path(directory).resolve()
    root.mkdir(parents=True, exist_ok=True)
    for name, record in LOCK["files"].items():
        if Path(name).name != name:
            raise ValueError("artifact must be a local filename")
        target = root / name
        if target.exists():
            with target.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() == record["sha256"]:
                    print("VERIFIED", name, flush=True)
                    continue
        temporary = root / (name + ".part")
        try:
            url = f'https://huggingface.co/{LOCK["repository"]}/resolve/{LOCK["revision"]}/{record["path"]}'
            digest = hashlib.sha256()
            with urllib.request.urlopen(url, timeout=180) as response, temporary.open("wb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
            if digest.hexdigest() != record["sha256"]:
                raise ValueError("download checksum mismatch")
            temporary.replace(target)
            print("DOWNLOADED_VERIFIED", name, target.stat().st_size, flush=True)
        finally:
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: download_model.py MODEL_DIRECTORY")
    download(sys.argv[1])
