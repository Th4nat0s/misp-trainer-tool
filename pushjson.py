#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from pymisp import MISPEvent, PyMISP


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Push MISP event JSON files from a folder to a MISP instance.",
        epilog=(
            "Example: ./pushjson.py --key API_KEY --url https://misp.local "
            "--folder ./events"
        ),
    )
    parser.add_argument("--key", required=True, help="MISP API key.")
    parser.add_argument("--url", required=True, help="MISP base URL.")
    parser.add_argument(
        "--folder", required=True, help="Folder containing event JSON files."
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification.",
    )
    return parser


def load_event(path: Path) -> MISPEvent:
    with path.open(encoding="utf-8") as handle:
        payload = json.load(handle)

    event = MISPEvent()
    event.load(payload)
    return event


def extract_event_payload(response: dict[str, Any]) -> dict[str, Any]:
    if "Event" in response and isinstance(response["Event"], dict):
        return response["Event"]
    return response


def main() -> int:
    args = build_parser().parse_args()
    folder = Path(args.folder)

    if not folder.exists():
        print(f"Folder does not exist: {folder}", file=sys.stderr)
        return 1
    if not folder.is_dir():
        print(f"Not a folder: {folder}", file=sys.stderr)
        return 1

    json_files = sorted(
        path for path in folder.iterdir() if path.suffix.lower() == ".json"
    )
    if not json_files:
        print(f"No JSON files found in {folder}", file=sys.stderr)
        return 1

    misp = PyMISP(args.url, args.key, ssl=not args.insecure)
    failures = 0

    for index, json_file in enumerate(json_files, start=1):
        try:
            event = load_event(json_file)
            response = misp.add_event(event)

            if isinstance(response, dict) and response.get("errors"):
                failures += 1
                print(
                    f"[{index}/{len(json_files)}] failed {json_file.name}",
                    file=sys.stderr,
                )
                print(f"MISP error: {response['errors']}", file=sys.stderr)
                continue

            event_payload = extract_event_payload(response)
            print(
                f"[{index}/{len(json_files)}] pushed {json_file.name} "
                f"id={event_payload.get('id', 'n/a')} uuid={event_payload.get('uuid', 'n/a')}"
            )
        except Exception as error:
            failures += 1
            print(
                f"[{index}/{len(json_files)}] failed {json_file.name}", file=sys.stderr
            )
            print(f"MISP error: {error}", file=sys.stderr)

    if failures:
        print(f"Completed with {failures} failure(s).", file=sys.stderr)
        return 1

    print(f"Pushed {len(json_files)} event(s) successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
