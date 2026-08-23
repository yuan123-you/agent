"""Generate committed large synthetic KB resources and retrieval cases."""
from pathlib import Path
import json

try:
    from backend.scripts.kb_dataset import write_dataset
except ModuleNotFoundError:
    from kb_dataset import write_dataset


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[2]
    stats = write_dataset(
        root / "backend/src/main/resources/kbseed/generated",
        root / "eval/dataset/kb_large_rag.jsonl",
    )
    print(json.dumps(stats, ensure_ascii=False))
