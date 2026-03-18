#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import os


PRESENTATION_NAME_DATE_FORMATS = (
    "%m.%d.%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)

DEFAULT_START = dt.date(2025, 7, 1)
DEFAULT_END = dt.date(2025, 9, 30)


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def parse_presentation_name_date(presentation_name: str):
    if not presentation_name:
        return None

    for date_format in PRESENTATION_NAME_DATE_FORMATS:
        try:
            return dt.datetime.strptime(presentation_name, date_format).date()
        except ValueError:
            continue

    return None


def parse_cli_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def collect_presentations(*, ready_only: bool, exclude_blank_id: bool):
    from GPTrivia.models import MergedPresentation

    queryset = MergedPresentation.objects.order_by("name", "id")
    if ready_only:
        queryset = queryset.filter(status=MergedPresentation.STATUS_READY)
    if exclude_blank_id:
        queryset = queryset.exclude(presentation_id="")
    return list(queryset)


def filter_presentations_by_date(presentations, *, start_date: dt.date, end_date: dt.date):
    matches = []
    unparsable = []

    for presentation in presentations:
        parsed_date = parse_presentation_name_date(presentation.name)
        if parsed_date is None:
            unparsable.append(presentation)
            continue

        if start_date <= parsed_date <= end_date:
            matches.append((parsed_date, presentation))

    return matches, unparsable


def print_report(matches, *, start_date: dt.date, end_date: dt.date):
    print(f"Searching presentations from {start_date.isoformat()} through {end_date.isoformat()} (inclusive).")

    if not matches:
        print("No presentations found in that range.")
        return

    current_date = None
    for parsed_date, presentation in matches:
        if parsed_date != current_date:
            current_date = parsed_date
            print(f"\n{parsed_date:%B %d, %Y}")

        print(
            "  "
            f"id={presentation.id:<5} "
            f"status={presentation.status:<5} "
            f"name={presentation.name:<12} "
            f"presentation_id={presentation.presentation_id or '(blank)'}"
        )

    print(f"\nPresentations found: {len(matches)}")


def write_csv(path: str, matches):
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["parsed_date", "id", "status", "name", "presentation_id"])
        for parsed_date, presentation in matches:
            writer.writerow(
                [
                    parsed_date.isoformat(),
                    presentation.id,
                    presentation.status,
                    presentation.name,
                    presentation.presentation_id,
                ]
            )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Report MergedPresentation rows whose parsed date falls within a given date range."
        )
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START.isoformat(),
        help=f"Range start date in YYYY-MM-DD format. Default: {DEFAULT_START.isoformat()}",
    )
    parser.add_argument(
        "--end",
        default=DEFAULT_END.isoformat(),
        help=f"Range end date in YYYY-MM-DD format. Default: {DEFAULT_END.isoformat()}",
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

    start_date = parse_cli_date(args.start)
    end_date = parse_cli_date(args.end)
    if end_date < start_date:
        parser.error("--end must be on or after --start")

    configure_django()
    presentations = collect_presentations(
        ready_only=args.ready_only,
        exclude_blank_id=args.exclude_blank_id,
    )
    matches, unparsable = filter_presentations_by_date(
        presentations,
        start_date=start_date,
        end_date=end_date,
    )

    if args.csv:
        write_csv(args.csv, matches)
        print(f"Wrote CSV report to {args.csv}")

    print_report(matches, start_date=start_date, end_date=end_date)
    if unparsable:
        print(f"Unparsable presentation names skipped: {len(unparsable)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
