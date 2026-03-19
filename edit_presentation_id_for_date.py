#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import re
import sys
from typing import Optional


PRESENTATION_NAME_DATE_FORMATS = (
    "%m.%d.%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)
PRESENTATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
GOOGLE_SLIDES_URL_PATTERN = re.compile(r"/presentation/d/([A-Za-z0-9_-]+)")


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def parse_cli_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def parse_presentation_name_date(presentation_name: str):
    if not presentation_name:
        return None

    for date_format in PRESENTATION_NAME_DATE_FORMATS:
        try:
            return dt.datetime.strptime(presentation_name, date_format).date()
        except ValueError:
            continue

    return None


def parse_presentation_id_input(raw_value: str) -> Optional[str]:
    value = (raw_value or "").strip()
    if not value:
        return None

    url_match = GOOGLE_SLIDES_URL_PATTERN.search(value)
    if url_match:
        return url_match.group(1)

    if PRESENTATION_ID_PATTERN.fullmatch(value):
        return value

    return ""


def collect_presentations_for_date(target_date: dt.date, *, ready_only: bool):
    from GPTrivia.models import MergedPresentation

    queryset = MergedPresentation.objects.order_by("id")
    if ready_only:
        queryset = queryset.filter(status=MergedPresentation.STATUS_READY)

    matches = []
    for presentation in queryset:
        if parse_presentation_name_date(presentation.name) == target_date:
            matches.append(presentation)

    return matches


def _format_summary_list(values, *, empty_text: str) -> str:
    if not values:
        return empty_text

    if isinstance(values, dict):
        preview_items = [
            f"{key}={value}" if value not in ("", None) else str(key)
            for key, value in list(values.items())[:6]
            if key or value
        ]
        if not preview_items:
            return empty_text
        suffix = " ..." if len(values) > len(preview_items) else ""
        return ", ".join(preview_items) + suffix

    preview = [str(value) for value in list(values)[:6] if value not in ("", None)]
    if not preview:
        return empty_text
    suffix = " ..." if len(values) > len(preview) else ""
    return ", ".join(preview) + suffix


def print_presentations(target_date: dt.date, presentations):
    print(f"Presentations for {target_date.isoformat()}: {len(presentations)}")
    for index, presentation in enumerate(presentations, start=1):
        print("\n" + "=" * 72)
        print(f"{index}. MergedPresentation id={presentation.id}")
        print(f"   status: {presentation.status}")
        print(f"   name: {presentation.name or '(blank)'}")
        print(f"   presentation_id: {presentation.presentation_id or '(blank)'}")
        print(f"   creators: {_format_summary_list(presentation.creator_list or [], empty_text='(none)')}")
        print(f"   rounds: {_format_summary_list(presentation.round_names or [], empty_text='(none)')}")
        print(f"   players: {_format_summary_list(presentation.player_list or {}, empty_text='(none)')}")
        print(f"   jokers: {_format_summary_list(presentation.joker_round_indices or {}, empty_text='(none)')}")


def choose_presentation(presentations):
    if len(presentations) == 1:
        return presentations[0]

    while True:
        response = input(
            f"Choose which presentation row to edit [1-{len(presentations)}] (`q` to quit): "
        ).strip().lower()

        if response in {"q", "quit", "exit"}:
            return None

        try:
            selected_index = int(response)
        except ValueError:
            print("Please enter a row number or `q`.")
            continue

        if 1 <= selected_index <= len(presentations):
            return presentations[selected_index - 1]

        print(f"Please choose a number between 1 and {len(presentations)}.")


def check_duplicate_id(presentation_id: str, current_presentation_pk: int):
    from GPTrivia.models import MergedPresentation

    return list(
        MergedPresentation.objects.filter(presentation_id=presentation_id)
        .exclude(id=current_presentation_pk)
        .values_list("id", "name", "status")
    )


def update_presentation_id(presentation):
    print("\nSelected row:")
    print(f"  id={presentation.id}")
    print(f"  name={presentation.name or '(blank)'}")
    print(f"  current presentation_id={presentation.presentation_id or '(blank)'}")

    while True:
        response = input(
            "Enter the new presentation ID or Google Slides URL "
            "(`Enter` to cancel, `q` to quit): "
        ).strip()

        if not response:
            print("Canceled.")
            return False

        if response.lower() in {"q", "quit", "exit"}:
            return False

        parsed_id = parse_presentation_id_input(response)
        if parsed_id == "":
            print("That doesn't look like a valid presentation ID or Google Slides URL. Try again.")
            continue

        duplicates = check_duplicate_id(parsed_id, presentation.id)
        if duplicates:
            print("Warning: this presentation ID is already used by:")
            for duplicate_id, duplicate_name, duplicate_status in duplicates:
                print(f"  id={duplicate_id} name={duplicate_name} status={duplicate_status}")
            confirm = input("Use it anyway? [y/N]: ").strip().lower()
            if confirm not in {"y", "yes"}:
                continue

        confirm = input(
            f"Save presentation_id={parsed_id} to MergedPresentation id={presentation.id}? [y/N]: "
        ).strip().lower()
        if confirm not in {"y", "yes"}:
            print("No changes made.")
            return False

        presentation.presentation_id = parsed_id
        presentation.save(update_fields=["presentation_id"])
        print(f"Saved presentation_id={parsed_id}")
        return True


def main():
    parser = argparse.ArgumentParser(
        description="Interactively edit the MergedPresentation presentation_id for a single trivia date."
    )
    parser.add_argument(
        "date",
        help="Trivia date in YYYY-MM-DD format, for example 2023-09-29.",
    )
    parser.add_argument(
        "--ready-only",
        action="store_true",
        help="Only consider ready presentations.",
    )
    args = parser.parse_args()

    if not sys.stdin.isatty():
        print("This script is interactive and needs a TTY.", file=sys.stderr)
        return 1

    target_date = parse_cli_date(args.date)
    configure_django()
    presentations = collect_presentations_for_date(target_date, ready_only=args.ready_only)

    if not presentations:
        print(f"No presentations found for {target_date.isoformat()}.")
        return 0

    print_presentations(target_date, presentations)
    presentation = choose_presentation(presentations)
    if presentation is None:
        print("No changes made.")
        return 0

    update_presentation_id(presentation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
