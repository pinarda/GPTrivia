#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from typing import Any, Iterable, Tuple


PRESENTATION_NAME_DATE_FORMATS = (
    "%m.%d.%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)


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


def json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def truncate_text(value: str, limit: int = 240) -> str:
    if not value:
        return "(blank)"
    if len(value) <= limit:
        return value
    return f"{value[:limit]}..."


def print_json_block(label: str, value: Any):
    print(f"{label}:")
    print(json_dump(value))


def print_key_value_rows(rows: Iterable[Tuple[str, Any]]):
    for label, value in rows:
        print(f"{label}: {value}")


def collect_presentations_for_date(target_date: dt.date):
    from GPTrivia.models import MergedPresentation

    matches = []
    unparsable = []

    for presentation in MergedPresentation.objects.order_by("id"):
        parsed_date = parse_presentation_name_date(presentation.name)
        if parsed_date is None:
            unparsable.append(presentation)
            continue
        if parsed_date == target_date:
            matches.append((presentation, parsed_date))

    return matches, unparsable


def collect_rounds_for_date(target_date: dt.date):
    from GPTrivia.models import GPTriviaRound

    return list(
        GPTriviaRound.objects.filter(date=target_date).order_by("round_number", "id")
    )


def print_presentations(matches):
    if not matches:
        print("No MergedPresentation rows matched that date.")
        return

    print(f"MergedPresentation rows found: {len(matches)}")
    for presentation, parsed_date in matches:
        print("\n" + "=" * 72)
        print(
            f"MergedPresentation id={presentation.id} | status={presentation.status} "
            f"| parsed_date={parsed_date.isoformat()}"
        )
        print_key_value_rows(
            [
                ("name", presentation.name),
                ("presentation_id", presentation.presentation_id or "(blank)"),
                ("host", presentation.host or "(blank)"),
                ("scorekeeper", presentation.scorekeeper or "(blank)"),
                ("crowned_winner", presentation.crowned_winner or "(blank)"),
                ("tiebreak_winner", presentation.tiebreak_winner or "(blank)"),
            ]
        )
        print_json_block("round_names", presentation.round_names or [])
        print_json_block("creator_list", presentation.creator_list or [])
        print_json_block("joker_round_indices", presentation.joker_round_indices or {})
        print_json_block("player_list", presentation.player_list or {})
        print_json_block("style_points", presentation.style_points or {})
        print(f"notes: {truncate_text(presentation.notes)}")
        print(f"error_message: {truncate_text(presentation.error_message)}")


def print_rounds(rounds):
    if not rounds:
        print("No GPTriviaRound rows matched that date.")
        return

    print(f"\nGPTriviaRound rows found: {len(rounds)}")
    for round_obj in rounds:
        print("\n" + "-" * 72)
        print(
            f"Round id={round_obj.id} | round_number={round_obj.round_number} | "
            f"title={round_obj.title}"
        )
        print_key_value_rows(
            [
                ("creator", round_obj.creator or "(blank)"),
                ("secondary_creator", round_obj.secondary_creator or "(blank)"),
                ("major_category", round_obj.major_category or "(blank)"),
                ("minor_category1", round_obj.minor_category1 or "(blank)"),
                ("minor_category2", round_obj.minor_category2 or "(blank)"),
                ("cooperative", round_obj.cooperative),
                ("replay", round_obj.replay),
                ("max_score", round_obj.max_score),
                ("link", round_obj.link or "(blank)"),
            ]
        )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Print MergedPresentation and GPTriviaRound database details for a single trivia date."
        )
    )
    parser.add_argument(
        "date",
        help="Trivia date in YYYY-MM-DD format, for example 2023-05-12.",
    )
    args = parser.parse_args()

    target_date = parse_cli_date(args.date)
    configure_django()

    try:
        presentation_matches, unparsable = collect_presentations_for_date(target_date)
        rounds = collect_rounds_for_date(target_date)
    except Exception as exc:
        error_type = type(exc).__name__
        print(
            "Unable to query the configured database. "
            "This usually means you're running the script against a workspace copy "
            "that does not have the GPTrivia tables."
        )
        print(f"{error_type}: {exc}")
        return 1

    print(f"Inspecting trivia date: {target_date.isoformat()}")
    print_presentations(presentation_matches)
    print_rounds(rounds)

    if unparsable:
        print(f"\nUnparsable presentation names skipped: {len(unparsable)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
