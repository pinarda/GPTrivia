#!/usr/bin/env python3
import argparse
import os
import re
import sys
from typing import Optional


PRESENTATION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
GOOGLE_SLIDES_URL_PATTERN = re.compile(r"/presentation/d/([A-Za-z0-9_-]+)")


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def collect_blank_presentations(*, ready_only: bool):
    from GPTrivia.models import MergedPresentation

    queryset = MergedPresentation.objects.filter(presentation_id="").order_by("name", "id")
    if ready_only:
        queryset = queryset.filter(status=MergedPresentation.STATUS_READY)
    return list(queryset)


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


def _format_summary_list(values, *, empty_text: str) -> str:
    if not values:
        return empty_text
    preview = [str(value) for value in values[:6] if value]
    if not preview:
        return empty_text
    suffix = " ..." if len(values) > len(preview) else ""
    return ", ".join(preview) + suffix


def _print_presentation_header(index: int, total: int, presentation):
    print("\n" + "=" * 72)
    print(f"[{index}/{total}] MergedPresentation id={presentation.id}")
    print(f"Name: {presentation.name or '(blank)'}")
    print(f"Status: {presentation.status}")
    print(f"Current presentation_id: {(presentation.presentation_id or '(blank)')}")
    print(f"Creators: {_format_summary_list(presentation.creator_list or [], empty_text='(none)')}")
    print(f"Rounds: {_format_summary_list(presentation.round_names or [], empty_text='(none)')}")
    if presentation.error_message:
        print(f"Error message: {presentation.error_message[:160]}")
    print("=" * 72)


def _check_duplicate_id(presentation_id: str, current_presentation_id: int):
    from GPTrivia.models import MergedPresentation

    return list(
        MergedPresentation.objects.filter(presentation_id=presentation_id)
        .exclude(id=current_presentation_id)
        .values_list("id", "name")
    )


def interactive_fill(presentations):
    updated = 0
    skipped = 0

    for index, presentation in enumerate(presentations, start=1):
        _print_presentation_header(index, len(presentations), presentation)

        while True:
            response = input(
                "Enter presentation ID or Google Slides URL "
                "(`Enter` to skip, `q` to quit): "
            ).strip()

            if not response:
                skipped += 1
                print("Skipped.")
                break

            if response.lower() in {"q", "quit", "exit"}:
                print("\nStopping early.")
                return updated, skipped, True

            parsed_id = parse_presentation_id_input(response)
            if parsed_id == "":
                print("That doesn't look like a valid presentation ID or Google Slides URL. Try again.")
                continue

            duplicates = _check_duplicate_id(parsed_id, presentation.id)
            if duplicates:
                print("Warning: this presentation ID is already used by:")
                for duplicate_id, duplicate_name in duplicates:
                    print(f"  id={duplicate_id} name={duplicate_name}")
                confirm = input("Use it anyway? [y/N]: ").strip().lower()
                if confirm not in {"y", "yes"}:
                    continue

            presentation.presentation_id = parsed_id
            presentation.save(update_fields=["presentation_id"])
            updated += 1
            print(f"Saved presentation_id={parsed_id}")
            break

    return updated, skipped, False


def main():
    parser = argparse.ArgumentParser(
        description="Interactively fill blank MergedPresentation presentation_id values."
    )
    parser.add_argument(
        "--ready-only",
        action="store_true",
        help="Only prompt for ready presentations.",
    )
    args = parser.parse_args()

    if not sys.stdin.isatty():
        print("This script is interactive and needs a TTY.", file=sys.stderr)
        return 1

    configure_django()
    presentations = collect_blank_presentations(ready_only=args.ready_only)

    if not presentations:
        print("No presentations with blank presentation_id values found.")
        return 0

    print(f"Found {len(presentations)} presentations with blank presentation_id values.")
    updated, skipped, stopped_early = interactive_fill(presentations)

    print("\nSummary:")
    print(f"  updated: {updated}")
    print(f"  skipped: {skipped}")
    print(f"  remaining: {max(len(presentations) - updated - skipped, 0) if stopped_early else 0}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
