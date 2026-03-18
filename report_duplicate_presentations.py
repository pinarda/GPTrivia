#!/usr/bin/env python3
import argparse
import csv
import os
from collections import defaultdict
from typing import Dict, List, Optional


PRESENTATION_NAME_DATE_FORMATS = (
    "%m.%d.%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def parse_presentation_name_date(presentation_name: str):
    import datetime as dt

    if not presentation_name:
        return None

    for date_format in PRESENTATION_NAME_DATE_FORMATS:
        try:
            return dt.datetime.strptime(presentation_name, date_format).date()
        except ValueError:
            continue

    return None


def collect_presentations(*, ready_only: bool, exclude_blank_id: bool):
    from GPTrivia.models import MergedPresentation

    queryset = MergedPresentation.objects.order_by("name", "id")
    if ready_only:
        queryset = queryset.filter(status=MergedPresentation.STATUS_READY)
    if exclude_blank_id:
        queryset = queryset.exclude(presentation_id="")
    return list(queryset)


def build_duplicate_groups(presentations) -> Dict[str, List[object]]:
    groups: Dict[str, List[object]] = defaultdict(list)

    for presentation in presentations:
        parsed_date = parse_presentation_name_date(presentation.name)
        if parsed_date is None:
            continue
        groups[parsed_date.isoformat()].append(presentation)

    return {
        iso_date: group
        for iso_date, group in groups.items()
        if len(group) > 1
    }


def print_report(duplicate_groups):
    if not duplicate_groups:
        print("No duplicate presentation dates found.")
        return

    for iso_date in sorted(duplicate_groups.keys()):
        group = duplicate_groups[iso_date]
        print(f"\n{iso_date} | duplicates={len(group)}")
        for presentation in group:
            print(
                "  "
                f"id={presentation.id:<5} "
                f"status={presentation.status:<5} "
                f"name={presentation.name:<12} "
                f"presentation_id={presentation.presentation_id or '(blank)'}"
            )


def write_csv(path: str, duplicate_groups):
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["parsed_date", "id", "status", "name", "presentation_id"])
        for iso_date in sorted(duplicate_groups.keys()):
            for presentation in duplicate_groups[iso_date]:
                writer.writerow(
                    [
                        iso_date,
                        presentation.id,
                        presentation.status,
                        presentation.name,
                        presentation.presentation_id,
                    ]
                )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Report MergedPresentation rows that resolve to the same presentation date."
        )
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
    duplicate_groups = build_duplicate_groups(presentations)

    if args.csv:
        write_csv(args.csv, duplicate_groups)
        print(f"Wrote CSV report to {args.csv}")

    print_report(duplicate_groups)
    print(f"\nDuplicate dates found: {len(duplicate_groups)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
