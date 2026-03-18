#!/usr/bin/env python3
import argparse
import os
import sys
from collections import defaultdict
from typing import Dict, List


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


def _format_summary_list(values, *, empty_text: str) -> str:
    if not values:
        return empty_text

    if isinstance(values, dict):
        items = [
            f"{key}={value}" if value not in ("", None) else str(key)
            for key, value in list(values.items())[:6]
            if key or value
        ]
        if not items:
            return empty_text
        suffix = " ..." if len(values) > len(items) else ""
        return ", ".join(items) + suffix

    if isinstance(values, (list, tuple)):
        preview_values = list(values[:6])
        total_count = len(values)
    elif isinstance(values, set):
        preview_values = list(values)[:6]
        total_count = len(values)
    else:
        preview_values = [values]
        total_count = 1

    preview = [str(value) for value in preview_values if value not in ("", None)]
    if not preview:
        return empty_text
    suffix = " ..." if total_count > len(preview) else ""
    return ", ".join(preview) + suffix


def _format_text_preview(value, *, empty_text: str, limit: int = 160) -> str:
    if not value:
        return empty_text
    value = str(value).strip()
    if not value:
        return empty_text
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def _print_duplicate_group(group_index: int, total_groups: int, iso_date: str, presentations):
    print("\n" + "=" * 80)
    print(f"[{group_index}/{total_groups}] Duplicate presentation date: {iso_date}")
    print(f"Rows in this group: {len(presentations)}")
    print("=" * 80)

    for idx, presentation in enumerate(presentations, start=1):
        print(
            f"{idx}. id={presentation.id} | status={presentation.status} | "
            f"name={presentation.name} | presentation_id={presentation.presentation_id or '(blank)'}"
        )
        print(f"   creators: {_format_summary_list(presentation.creator_list or [], empty_text='(none)')}")
        print(f"   rounds: {_format_summary_list(presentation.round_names or [], empty_text='(none)')}")
        print(f"   players: {_format_summary_list(presentation.player_list or [], empty_text='(none)')}")
        print(f"   jokers: {_format_summary_list(presentation.joker_round_indices or [], empty_text='(none)')}")
        print(f"   host/scorekeeper: {presentation.host or '(none)'} / {presentation.scorekeeper or '(none)'}")
        print(
            "   winners: "
            f"crowned={presentation.crowned_winner or '(none)'} | "
            f"tiebreak={presentation.tiebreak_winner or '(none)'}"
        )
        print(f"   style points: {_format_summary_list(presentation.style_points or {}, empty_text='(none)')}")
        print(f"   notes: {_format_text_preview(presentation.notes, empty_text='(none)')}")
        if presentation.error_message:
            print(f"   error: {_format_text_preview(presentation.error_message, empty_text='(none)')}")


def resolve_duplicate_groups(duplicate_groups):
    from GPTrivia.models import MergedPresentation

    groups_resolved = 0
    groups_skipped = 0
    rows_deleted = 0

    sorted_groups = sorted(duplicate_groups.items())

    for group_index, (iso_date, presentations) in enumerate(sorted_groups, start=1):
        _print_duplicate_group(group_index, len(sorted_groups), iso_date, presentations)

        while True:
            response = input(
                "Choose which row to keep by number "
                "(`s` to skip, `q` to quit): "
            ).strip().lower()

            if response in {"q", "quit", "exit"}:
                print("\nStopping early.")
                return groups_resolved, groups_skipped, rows_deleted, True

            if response in {"s", "skip"}:
                groups_skipped += 1
                print("Skipped.")
                break

            try:
                keep_index = int(response)
            except ValueError:
                print("Please enter a row number, `s`, or `q`.")
                continue

            if keep_index < 1 or keep_index > len(presentations):
                print(f"Please choose a number between 1 and {len(presentations)}.")
                continue

            keep_presentation = presentations[keep_index - 1]
            delete_presentations = [
                presentation for idx, presentation in enumerate(presentations, start=1) if idx != keep_index
            ]

            print(
                f"Keeping id={keep_presentation.id} and deleting "
                f"{len(delete_presentations)} other row(s) for {iso_date}."
            )
            confirm = input("Proceed? [y/N]: ").strip().lower()
            if confirm not in {"y", "yes"}:
                print("No changes made for this group.")
                continue

            delete_ids = [presentation.id for presentation in delete_presentations]
            deleted_count, _ = MergedPresentation.objects.filter(id__in=delete_ids).delete()
            rows_deleted += deleted_count
            groups_resolved += 1
            print(f"Deleted {deleted_count} row(s).")
            break

    return groups_resolved, groups_skipped, rows_deleted, False


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Interactively resolve duplicate MergedPresentation rows by date."
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
    args = parser.parse_args()

    if not sys.stdin.isatty():
        print("This script is interactive and needs a TTY.", file=sys.stderr)
        return 1

    configure_django()
    presentations = collect_presentations(
        ready_only=args.ready_only,
        exclude_blank_id=args.exclude_blank_id,
    )
    duplicate_groups = build_duplicate_groups(presentations)

    if not duplicate_groups:
        print("No duplicate presentation dates found.")
        return 0

    print(f"Found {len(duplicate_groups)} duplicate date group(s).")
    groups_resolved, groups_skipped, rows_deleted, stopped_early = resolve_duplicate_groups(duplicate_groups)

    remaining_groups = max(len(duplicate_groups) - groups_resolved - groups_skipped, 0) if stopped_early else 0

    print("\nSummary:")
    print(f"  groups_resolved: {groups_resolved}")
    print(f"  groups_skipped: {groups_skipped}")
    print(f"  rows_deleted: {rows_deleted}")
    print(f"  remaining_groups: {remaining_groups}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
