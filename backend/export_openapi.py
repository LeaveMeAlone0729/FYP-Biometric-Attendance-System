"""Export the current public API contract without connecting to the database."""

import argparse
import json
from pathlib import Path

from app import app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "docs" / "openapi.json",
    )
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
    print(f"API specification written to {args.output}")


if __name__ == "__main__":
    main()
