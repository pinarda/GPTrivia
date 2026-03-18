#!/usr/bin/env python3
import argparse
import ast
import csv
import datetime as dt
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence


PRESENTATION_NAME_DATE_FORMATS = (
    "%m.%d.%Y",
    "%Y-%m-%d",
    "%m/%d/%Y",
)

DEFAULT_CURRENT_DB = "db.sqlite3"
DEFAULT_BACKUP_DBS = (
    "db_save.sqlite3",
    "dbMay21.sqlite3",
    "db_dev.sqlite3",
)


@dataclass
class PresentationRow:
    db_label: str
    id: int
    name: str
    status: str
    presentation_id: str
    joker_round_indices: object
    round_names: object
    creator_list: object
    player_list: object


def parse_presentation_name_date(presentation_name: str) -> Optional[dt.date]:
    if not presentation_name:
        return None

    for date_format in PRESENTATION_NAME_DATE_FORMATS:
        try:
            return dt.datetime.strptime(presentation_name, date_format).date()
        except ValueError:
            continue

    return None


def parse_serialized_jsonish(raw_value, fallback):
    if raw_value in (None, "", [], {}):
        return fallback

    if isinstance(raw_value, (dict, list)):
        return raw_value

    if not isinstance(raw_value, str):
        return fallback

    normalized_text = raw_value.replace("~~~~", "'")
    try:
        return json.loads(normalized_text.replace("'", '"'))
    except Exception:
        try:
            return ast.literal_eval(normalized_text)
        except Exception:
            return fallback


def parse_joker_round_indices(raw_value) -> Dict[str, str]:
    payload = parse_serialized_jsonish(raw_value, {})
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


def count_serialized_items(raw_value) -> int:
    payload = parse_serialized_jsonish(raw_value, [])
    if isinstance(payload, dict):
        return len(payload)
    if isinstance(payload, (list, tuple, set)):
        return len(payload)
    return 0


def load_presentations(db_path: Path, *, ready_only: bool, exclude_blank_id: bool) -> List[PresentationRow]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    query = """
        SELECT
            id,
            name,
            COALESCE(status, ''),
            COALESCE(presentation_id, ''),
            joker_round_indices,
            round_names,
            creator_list,
            player_list
        FROM GPTrivia_mergedpresentation
    """
    conditions = []
    if ready_only:
        conditions.append("status = 'ready'")
    if exclude_blank_id:
        conditions.append("presentation_id <> ''")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY name, id"

    with sqlite3.connect(str(db_path)) as connection:
        rows = connection.execute(query).fetchall()

    return [
        PresentationRow(
            db_label=db_path.name,
            id=row[0],
            name=row[1] or "",
            status=row[2] or "",
            presentation_id=row[3] or "",
            joker_round_indices=row[4],
            round_names=row[5],
            creator_list=row[6],
            player_list=row[7],
        )
        for row in rows
    ]


def build_missing_current_presentations(
    current_rows: Sequence[PresentationRow],
) -> List[PresentationRow]:
    return [
        row
        for row in current_rows
        if not parse_joker_round_indices(row.joker_round_indices)
    ]


def build_backup_index(rows: Sequence[PresentationRow]):
    by_date: Dict[str, List[PresentationRow]] = {}
    by_name: Dict[str, List[PresentationRow]] = {}

    for row in rows:
        parsed_date = parse_presentation_name_date(row.name)
        if parsed_date:
            by_date.setdefault(parsed_date.isoformat(), []).append(row)
        by_name.setdefault(row.name.strip().lower(), []).append(row)

    return by_date, by_name


def summarize_joker_mapping(raw_value) -> str:
    joker_mapping = parse_joker_round_indices(raw_value)
    if not joker_mapping:
        return "(none)"

    preview_items = list(joker_mapping.items())[:3]
    preview = ", ".join(f"{key}={value}" for key, value in preview_items)
    if len(joker_mapping) > 3:
        preview += f", ... ({len(joker_mapping)} total)"
    return preview


def find_backup_matches(
    current_missing_rows: Sequence[PresentationRow],
    backup_rows_by_db: Dict[str, Sequence[PresentationRow]],
):
    matches = []
    indexed_backups = {
        db_label: build_backup_index(rows)
        for db_label, rows in backup_rows_by_db.items()
    }

    for current_row in current_missing_rows:
        parsed_date = parse_presentation_name_date(current_row.name)
        row_matches = []

        for db_label, (rows_by_date, rows_by_name) in indexed_backups.items():
            candidates: Iterable[PresentationRow] = []
            if parsed_date:
                candidates = rows_by_date.get(parsed_date.isoformat(), [])
            elif current_row.name:
                candidates = rows_by_name.get(current_row.name.strip().lower(), [])

            joker_candidates = [
                candidate
                for candidate in candidates
                if parse_joker_round_indices(candidate.joker_round_indices)
            ]

            row_matches.append(
                {
                    "db_label": db_label,
                    "candidates": list(candidates),
                    "joker_candidates": joker_candidates,
                }
            )

        matches.append(
            {
                "current": current_row,
                "parsed_date": parsed_date,
                "backup_matches": row_matches,
            }
        )

    return matches


def print_report(match_rows):
    if not match_rows:
        print("No current presentations without jokers found.")
        return

    for match_row in match_rows:
        current = match_row["current"]
        parsed_date = match_row["parsed_date"]
        print()
        print(
            f"Current: id={current.id} "
            f"name={current.name} "
            f"date={(parsed_date.isoformat() if parsed_date else 'unparsed')} "
            f"presentation_id={current.presentation_id or '(blank)'}"
        )

        found_any = False
        for backup_match in match_row["backup_matches"]:
            joker_candidates = backup_match["joker_candidates"]
            if not joker_candidates:
                print(f"  {backup_match['db_label']}: no jokered presentation found")
                continue

            found_any = True
            print(f"  {backup_match['db_label']}:")
            for candidate in joker_candidates:
                print(
                    "    "
                    f"id={candidate.id:<5} "
                    f"name={candidate.name:<14} "
                    f"presentation_id={candidate.presentation_id or '(blank)'} "
                    f"jokers={summarize_joker_mapping(candidate.joker_round_indices)}"
                )

        if not found_any:
            print("  No backup match with jokers found for this presentation.")


def write_csv(path: str, match_rows):
    with open(path, "w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(
            [
                "current_id",
                "current_name",
                "current_date",
                "current_presentation_id",
                "backup_db",
                "backup_id",
                "backup_name",
                "backup_presentation_id",
                "joker_count",
                "joker_preview",
            ]
        )

        for match_row in match_rows:
            current = match_row["current"]
            parsed_date = match_row["parsed_date"]
            wrote_any = False
            for backup_match in match_row["backup_matches"]:
                for candidate in backup_match["joker_candidates"]:
                    joker_mapping = parse_joker_round_indices(candidate.joker_round_indices)
                    writer.writerow(
                        [
                            current.id,
                            current.name,
                            parsed_date.isoformat() if parsed_date else "",
                            current.presentation_id,
                            backup_match["db_label"],
                            candidate.id,
                            candidate.name,
                            candidate.presentation_id,
                            len(joker_mapping),
                            summarize_joker_mapping(candidate.joker_round_indices),
                        ]
                    )
                    wrote_any = True

            if not wrote_any:
                writer.writerow(
                    [
                        current.id,
                        current.name,
                        parsed_date.isoformat() if parsed_date else "",
                        current.presentation_id,
                        "",
                        "",
                        "",
                        "",
                        0,
                        "",
                    ]
                )


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Look at current presentations without jokers and check backup SQLite databases "
            "for same-date presentations that do have joker selections."
        )
    )
    parser.add_argument(
        "--current-db",
        default=DEFAULT_CURRENT_DB,
        help=f"Current SQLite database path. Default: {DEFAULT_CURRENT_DB}",
    )
    parser.add_argument(
        "--backup-db",
        action="append",
        dest="backup_dbs",
        help=(
            "Backup SQLite database path to search. "
            f"Can be provided multiple times. Defaults to: {', '.join(DEFAULT_BACKUP_DBS)}"
        ),
    )
    parser.add_argument(
        "--ready-only",
        action="store_true",
        help="Only consider ready presentations in current and backup databases.",
    )
    parser.add_argument(
        "--exclude-blank-id",
        action="store_true",
        help="Ignore rows with a blank presentation_id in current and backup databases.",
    )
    parser.add_argument(
        "--csv",
        help="Optional CSV output path.",
    )
    args = parser.parse_args()

    current_db_path = Path(args.current_db)
    backup_db_paths = [Path(path) for path in (args.backup_dbs or DEFAULT_BACKUP_DBS)]

    current_rows = load_presentations(
        current_db_path,
        ready_only=args.ready_only,
        exclude_blank_id=args.exclude_blank_id,
    )
    current_missing_rows = build_missing_current_presentations(current_rows)

    backup_rows_by_db = {
        backup_db_path.name: load_presentations(
            backup_db_path,
            ready_only=args.ready_only,
            exclude_blank_id=args.exclude_blank_id,
        )
        for backup_db_path in backup_db_paths
    }

    match_rows = find_backup_matches(current_missing_rows, backup_rows_by_db)

    if args.csv:
        write_csv(args.csv, match_rows)
        print(f"Wrote CSV report to {args.csv}")

    print(
        f"Current presentations missing jokers: {len(current_missing_rows)} "
        f"from {current_db_path.name}"
    )
    print_report(match_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
