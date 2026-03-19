#!/usr/bin/env python3
import argparse
import datetime as dt
import json
import os
from typing import Any, Dict, List, Optional, Tuple


PRESENTATION_NAME_DATE_FORMATS = (
    "%m.%d.%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)

JSON_FIELD_SPECS = {
    "round_names": list,
    "creator_list": list,
    "joker_round_indices": dict,
    "player_list": dict,
    "style_points": dict,
}


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def parse_cli_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, "%Y-%m-%d").date()


def parse_presentation_name_date(presentation_name: str) -> Optional[dt.date]:
    if not presentation_name:
        return None

    for date_format in PRESENTATION_NAME_DATE_FORMATS:
        try:
            return dt.datetime.strptime(presentation_name, date_format).date()
        except ValueError:
            continue

    return None


def expected_default(expected_type):
    if expected_type is list:
        return []
    return {}


def normalize_json_field(raw_value: Any, expected_type) -> Dict[str, Any]:
    if isinstance(raw_value, expected_type):
        return {
            "valid": True,
            "parsed": raw_value,
            "issue": "",
            "replacement": None,
        }

    if raw_value is None:
        return {
            "valid": True,
            "parsed": None,
            "issue": "",
            "replacement": None,
        }

    if isinstance(raw_value, str):
        if not raw_value.strip():
            return {
                "valid": False,
                "parsed": None,
                "issue": "blank string",
                "replacement": expected_default(expected_type),
            }
        try:
            parsed_value = json.loads(raw_value)
        except (TypeError, ValueError) as exc:
            return {
                "valid": False,
                "parsed": None,
                "issue": f"invalid json ({exc})",
                "replacement": expected_default(expected_type),
            }
        if isinstance(parsed_value, expected_type):
            return {
                "valid": True,
                "parsed": parsed_value,
                "issue": "",
                "replacement": None,
            }
        return {
            "valid": False,
            "parsed": parsed_value,
            "issue": f"wrong JSON type ({type(parsed_value).__name__})",
            "replacement": expected_default(expected_type),
        }

    return {
        "valid": False,
        "parsed": raw_value,
        "issue": f"unexpected type ({type(raw_value).__name__})",
        "replacement": expected_default(expected_type),
    }


def load_presentations_for_date(target_date: dt.date) -> List[Dict[str, Any]]:
    from django.db import connection
    from GPTrivia.models import MergedPresentation

    table_name = MergedPresentation._meta.db_table
    select_columns = [
        "id",
        "name",
        "presentation_id",
        "status",
        "host",
        "scorekeeper",
        "crowned_winner",
        "tiebreak_winner",
        *JSON_FIELD_SPECS.keys(),
    ]

    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {', '.join(select_columns)} FROM {table_name} ORDER BY id"
        )
        rows = cursor.fetchall()

    presentations = []
    for row in rows:
        row_data = dict(zip(select_columns, row))
        parsed_date = parse_presentation_name_date(row_data["name"])
        if parsed_date != target_date:
            continue
        presentations.append(row_data)

    return presentations


def print_presentation_report(presentation: Dict[str, Any]) -> List[Tuple[str, Any]]:
    print("\n" + "=" * 72)
    print(
        f"MergedPresentation id={presentation['id']} | status={presentation['status']} "
        f"| name={presentation['name']}"
    )
    print(f"presentation_id: {presentation['presentation_id'] or '(blank)'}")
    print(f"host: {presentation['host'] or '(blank)'}")
    print(f"scorekeeper: {presentation['scorekeeper'] or '(blank)'}")
    print(f"crowned_winner: {presentation['crowned_winner'] or '(blank)'}")
    print(f"tiebreak_winner: {presentation['tiebreak_winner'] or '(blank)'}")

    repairs = []
    for field_name, expected_type in JSON_FIELD_SPECS.items():
        raw_value = presentation[field_name]
        result = normalize_json_field(raw_value, expected_type)
        print(f"\n{field_name}:")
        print(f"  raw: {repr(raw_value)}")
        if result["valid"]:
            print("  status: valid")
        else:
            print(f"  status: repair needed ({result['issue']})")
            print(f"  replacement: {json.dumps(result['replacement'], sort_keys=True)}")
            repairs.append((field_name, result["replacement"]))

    return repairs


def apply_repairs(presentation_id: int, repairs: List[Tuple[str, Any]]) -> None:
    from django.db import connection
    from GPTrivia.models import MergedPresentation

    if not repairs:
        return

    assignments = []
    params: List[Any] = []
    for field_name, replacement in repairs:
        assignments.append(f"{field_name} = %s")
        params.append(json.dumps(replacement, sort_keys=True))
    params.append(presentation_id)

    table_name = MergedPresentation._meta.db_table
    query = f"UPDATE {table_name} SET {', '.join(assignments)} WHERE id = %s"

    with connection.cursor() as cursor:
        cursor.execute(query, params)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Inspect one scoresheet date for malformed MergedPresentation JSON fields "
            "and optionally repair them to safe defaults."
        )
    )
    parser.add_argument(
        "date",
        nargs="?",
        default="2023-05-12",
        help="Trivia date in YYYY-MM-DD format. Default: 2023-05-12.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the repaired JSON values back to the database. Default is dry-run.",
    )
    args = parser.parse_args()

    target_date = parse_cli_date(args.date)
    configure_django()

    presentations = load_presentations_for_date(target_date)
    if not presentations:
        print(f"No MergedPresentation rows matched {target_date.isoformat()}.")
        return 0

    print(f"Inspecting and repairing JSON fields for trivia date: {target_date.isoformat()}")

    total_repairs = 0
    for presentation in presentations:
        repairs = print_presentation_report(presentation)
        total_repairs += len(repairs)
        if args.apply and repairs:
            apply_repairs(presentation["id"], repairs)
            print("  applied: yes")
        elif repairs:
            print("  applied: no (dry-run)")
        else:
            print("  applied: not needed")

    if total_repairs == 0:
        print("\nNo malformed JSON fields found.")
    elif args.apply:
        print(f"\nApplied {total_repairs} field repair(s).")
    else:
        print(f"\nWould repair {total_repairs} field(s). Re-run with --apply to write changes.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
