#!/usr/bin/env python3
import argparse
import csv
import os
import sys


PLACEHOLDER_PRESENTATION_ID = "1gC9DR9TmQK_9ls8Npw8Sc99qKI6YN9nRqLuVj0W07ns"


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def iter_placeholder_rounds(*, include_blank: bool):
    from GPTrivia.models import GPTriviaRound

    queryset = GPTriviaRound.objects.filter(link__icontains=PLACEHOLDER_PRESENTATION_ID).order_by(
        "date",
        "round_number",
        "title",
    )

    if include_blank:
        blank_queryset = GPTriviaRound.objects.filter(link="").order_by(
            "date",
            "round_number",
            "title",
        )
        seen_ids = set()
        for round_obj in queryset:
            seen_ids.add(round_obj.id)
            yield round_obj, "placeholder"
        for round_obj in blank_queryset:
            if round_obj.id not in seen_ids:
                yield round_obj, "blank"
        return

    for round_obj in queryset:
        yield round_obj, "placeholder"


def write_csv(path: str, rows):
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "id",
                "date",
                "round_number",
                "creator",
                "title",
                "major_category",
                "minor_category1",
                "minor_category2",
                "link_status",
                "link",
            ]
        )
        for round_obj, link_status in rows:
            writer.writerow(
                [
                    round_obj.id,
                    round_obj.date.isoformat(),
                    round_obj.round_number,
                    round_obj.creator,
                    round_obj.title,
                    round_obj.major_category,
                    round_obj.minor_category1,
                    round_obj.minor_category2,
                    link_status,
                    round_obj.link,
                ]
            )


def print_report(rows, *, show_link: bool):
    total = 0
    current_date = None

    for round_obj, link_status in rows:
        total += 1
        if round_obj.date != current_date:
            current_date = round_obj.date
            print(f"\n{current_date:%B %d, %Y}")

        line = (
            f"  id={round_obj.id:<5} "
            f"round={round_obj.round_number:<2} "
            f"creator={round_obj.creator:<12} "
            f"status={link_status:<11} "
            f"title={round_obj.title}"
        )
        print(line)
        if show_link:
            print(f"    link={round_obj.link}")

    print(f"\nTotal rounds found: {total}")


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Report GPTrivia rounds whose link still points at the placeholder Google Slides deck."
        )
    )
    parser.add_argument(
        "--include-blank",
        action="store_true",
        help="Also include rounds whose link is blank.",
    )
    parser.add_argument(
        "--show-link",
        action="store_true",
        help="Print the full stored link for each round.",
    )
    parser.add_argument(
        "--csv",
        help="Optional output path for a CSV export.",
    )
    args = parser.parse_args()

    configure_django()
    rows = list(iter_placeholder_rounds(include_blank=args.include_blank))

    if args.csv:
        write_csv(args.csv, rows)
        print(f"Wrote CSV report to {args.csv}")

    print_report(rows, show_link=args.show_link)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
