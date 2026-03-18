#!/usr/bin/env python3
import argparse
import ast
import csv
import json
import os
from typing import Dict


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def collect_presentations(*, ready_only: bool, exclude_blank_id: bool):
    from GPTrivia.models import MergedPresentation

    queryset = MergedPresentation.objects.order_by("name", "id")
    if ready_only:
        queryset = queryset.filter(status=MergedPresentation.STATUS_READY)
    if exclude_blank_id:
        queryset = queryset.exclude(presentation_id="")
    return list(queryset)


def parse_joker_round_indices(raw_value) -> Dict[str, str]:
    if raw_value in (None, "", {}, []):
        return {}

    payload = raw_value
    if isinstance(raw_value, str):
        normalized_text = raw_value.replace("~~~~", "'")
        try:
            payload = json.loads(normalized_text.replace("'", '"'))
        except Exception:
            try:
                payload = ast.literal_eval(normalized_text)
            except Exception:
                return {}

    if not isinstance(payload, dict):
        return {}

    normalized = {}
    for key, value in payload.items():
        if value is None:
            continue

        cleaned_value = str(value).replace("~~~~", "'").strip()
        if not cleaned_value or cleaned_value.lower() in {"select", "none", "null"}:
            continue

        normalized[str(key).strip()] = cleaned_value

    return normalized


def build_missing_joker_report(presentations):
    matches = []

    for presentation in presentations:
        joker_mapping = parse_joker_round_indices(presentation.joker_round_indices)
        if joker_mapping:
            continue

        matches.append(
            {
                "id": presentation.id,
                "status": presentation.status,
                "name": presentation.name,
                "presentation_id": presentation.presentation_id or "",
                "round_count": len(presentation.round_names or []),
                "creator_count": len(presentation.creator_list or []),
                "player_count": len(presentation.player_list or []),
            }
        )

    return matches


def print_report(matches):
    if not matches:
        print("No presentations without recorded jokers found.")
        return

    print("Presentations without recorded jokers:\n")
    for row in matches:
        print(
            "  "
            f"id={row['id']:<5} "
            f"status={row['status']:<5} "
            f"name={row['name']:<14} "
            f"presentation_id={row['presentation_id'] or '(blank)'} "
            f"rounds={row['round_count']:<2} "
            f"creators={row['creator_count']:<2} "
            f"players={row['player_count']}"
        )

    print(f"\nPresentations found: {len(matches)}")


def write_csv(path: str, matches):
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "id",
                "status",
                "name",
                "presentation_id",
                "round_count",
                "creator_count",
                "player_count",
            ]
        )
        for row in matches:
            writer.writerow(
                [
                    row["id"],
                    row["status"],
                    row["name"],
                    row["presentation_id"],
                    row["round_count"],
                    row["creator_count"],
                    row["player_count"],
                ]
            )


def main():
    parser = argparse.ArgumentParser(
        description="Report MergedPresentation rows that do not have any joker selections recorded."
    )
    parser.add_argument(
        "--ready-only",
        action="store_true",
        help="Only consider ready presentations.",
    )
    parser.add_argument(
        "--exclude-blank-id",
        action="store_true",
        help="Ignore rows with a blank presentation_id.",
    )
    parser.add_argument(
        "--csv",
        help="Optional CSV output path.",
    )
    args = parser.parse_args()

    configure_django()
    presentations = collect_presentations(
        ready_only=args.ready_only,
        exclude_blank_id=args.exclude_blank_id,
    )
    matches = build_missing_joker_report(presentations)

    if args.csv:
        write_csv(args.csv, matches)
        print(f"Wrote CSV report to {args.csv}")

    print_report(matches)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
