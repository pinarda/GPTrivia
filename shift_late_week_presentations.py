#!/usr/bin/env python3
import argparse
import csv
import datetime as dt
import os
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple


PRESENTATION_NAME_DATE_FORMATS = (
    "%m.%d.%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)

DEFAULT_START = dt.date(2024, 8, 1)
SHIFTABLE_WEEKDAYS = {
    4: "Friday",
    5: "Saturday",
}


@dataclass
class PresentationShift:
    presentation_id: int
    status: str
    old_name: str
    new_name: str
    old_date: dt.date
    new_date: dt.date


@dataclass
class DateShift:
    old_date: dt.date
    new_date: dt.date
    weekday_name: str
    presentation_shifts: List[PresentationShift]
    round_ids: List[int]


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def parse_cli_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def parse_presentation_name_date(presentation_name: str) -> Tuple[Optional[dt.date], Optional[str]]:
    if not presentation_name:
        return None, None

    for date_format in PRESENTATION_NAME_DATE_FORMATS:
        try:
            return dt.datetime.strptime(presentation_name, date_format).date(), date_format
        except ValueError:
            continue

    return None, None


def format_presentation_name(target_date: dt.date, original_format: Optional[str]) -> str:
    if original_format:
        return target_date.strftime(original_format)
    return target_date.strftime("%m.%d.%Y")


def build_shift_plan(*, start_date: dt.date) -> Tuple[List[DateShift], List[object]]:
    from GPTrivia.models import GPTriviaRound, MergedPresentation

    presentations = list(MergedPresentation.objects.order_by("name", "id"))
    rounds_by_date: Dict[dt.date, List[int]] = defaultdict(list)
    for round_id, round_date in GPTriviaRound.objects.order_by("date", "round_number", "id").values_list("id", "date"):
        if round_date:
            rounds_by_date[round_date].append(round_id)

    shifts_by_date: Dict[dt.date, DateShift] = {}
    unparsable_presentations = []

    for presentation in presentations:
        parsed_date, parsed_format = parse_presentation_name_date(presentation.name)
        if parsed_date is None:
            unparsable_presentations.append(presentation)
            continue

        if parsed_date < start_date or parsed_date.weekday() not in SHIFTABLE_WEEKDAYS:
            continue

        new_date = parsed_date - dt.timedelta(days=1)
        shift = shifts_by_date.setdefault(
            parsed_date,
            DateShift(
                old_date=parsed_date,
                new_date=new_date,
                weekday_name=SHIFTABLE_WEEKDAYS[parsed_date.weekday()],
                presentation_shifts=[],
                round_ids=list(rounds_by_date.get(parsed_date, [])),
            ),
        )
        shift.presentation_shifts.append(
            PresentationShift(
                presentation_id=presentation.id,
                status=presentation.status,
                old_name=presentation.name,
                new_name=format_presentation_name(new_date, parsed_format),
                old_date=parsed_date,
                new_date=new_date,
            )
        )

    return sorted(shifts_by_date.values(), key=lambda shift: shift.old_date), unparsable_presentations


def print_report(date_shifts: Sequence[DateShift], *, start_date: dt.date, dry_run: bool):
    mode_label = "Dry run" if dry_run else "Apply"
    print(f"{mode_label}: shifting Friday/Saturday presentations from {start_date.isoformat()} onward back one day.")

    if not date_shifts:
        print("No matching presentation dates found.")
        return

    total_presentations = 0
    total_rounds = 0

    for date_shift in date_shifts:
        total_presentations += len(date_shift.presentation_shifts)
        total_rounds += len(date_shift.round_ids)

        print(
            f"\n{date_shift.old_date.isoformat()} ({date_shift.weekday_name}) -> "
            f"{date_shift.new_date.isoformat()} | "
            f"presentations={len(date_shift.presentation_shifts)} rounds={len(date_shift.round_ids)}"
        )
        for presentation_shift in date_shift.presentation_shifts:
            print(
                "  "
                f"presentation id={presentation_shift.presentation_id:<5} "
                f"status={presentation_shift.status:<5} "
                f"{presentation_shift.old_name} -> {presentation_shift.new_name}"
            )

    print(f"\nPresentation rows to update: {total_presentations}")
    print(f"Round rows to update: {total_rounds}")


def write_csv(path: str, date_shifts: Sequence[DateShift]):
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "old_date",
                "new_date",
                "presentation_id",
                "status",
                "old_name",
                "new_name",
                "round_ids_moved",
            ]
        )
        for date_shift in date_shifts:
            round_ids = ",".join(str(round_id) for round_id in date_shift.round_ids)
            for presentation_shift in date_shift.presentation_shifts:
                writer.writerow(
                    [
                        date_shift.old_date.isoformat(),
                        date_shift.new_date.isoformat(),
                        presentation_shift.presentation_id,
                        presentation_shift.status,
                        presentation_shift.old_name,
                        presentation_shift.new_name,
                        round_ids,
                    ]
                )


def apply_shift_plan(date_shifts: Sequence[DateShift]):
    from django.db import transaction
    from GPTrivia.models import GPTriviaRound, MergedPresentation

    with transaction.atomic():
        for date_shift in date_shifts:
            for presentation_shift in date_shift.presentation_shifts:
                MergedPresentation.objects.filter(id=presentation_shift.presentation_id).update(
                    name=presentation_shift.new_name
                )

            if date_shift.round_ids:
                GPTriviaRound.objects.filter(id__in=date_shift.round_ids).update(
                    date=date_shift.new_date
                )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Shift Friday/Saturday MergedPresentation dates from August 2024 onward back one day, "
            "and move all GPTriviaRound rows on those dates back one day as well."
        )
    )
    parser.add_argument(
        "--start",
        default=DEFAULT_START.isoformat(),
        help=f"Start date in YYYY-MM-DD format. Default: {DEFAULT_START.isoformat()}",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the changes. Without this flag, the script only prints a dry run.",
    )
    parser.add_argument(
        "--csv",
        help="Optional CSV output path.",
    )
    args = parser.parse_args()

    start_date = parse_cli_date(args.start)

    configure_django()
    date_shifts, unparsable_presentations = build_shift_plan(start_date=start_date)

    if args.csv:
        write_csv(args.csv, date_shifts)
        print(f"Wrote CSV report to {args.csv}")

    print_report(date_shifts, start_date=start_date, dry_run=not args.apply)
    if unparsable_presentations:
        print(f"Unparsable presentation names skipped: {len(unparsable_presentations)}")

    if args.apply and date_shifts:
        apply_shift_plan(date_shifts)
        print("\nApplied date shifts successfully.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
