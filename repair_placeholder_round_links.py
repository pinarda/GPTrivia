#!/usr/bin/env python3
import argparse
import base64
import datetime as dt
import os
import pickle
import re
import sys
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Dict, List, Optional, Sequence, Tuple

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from GPTrivia.mail import (
    CLIENT_SECRET_FILE,
    MAIL_NAME_MAP,
    URL_PATTERN,
    _extract_presentation_link_parts,
    _format_pacific_timestamp,
    build_credentials,
    token_file_path,
)


PLACEHOLDER_PRESENTATION_ID = "1gC9DR9TmQK_9ls8Npw8Sc99qKI6YN9nRqLuVj0W07ns"
SHARED_CREATOR_WILDCARDS = {
    "swooper",
    "hailscience",
}


def log_progress(message: str):
    print(message, file=sys.stderr, flush=True)


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def load_credentials():
    credentials = None

    if os.path.exists(token_file_path):
        with open(token_file_path, "rb") as token_file:
            credentials = pickle.load(token_file)

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        with open(token_file_path, "wb") as token_file:
            pickle.dump(credentials, token_file)

    if credentials and credentials.valid:
        return credentials

    if not os.path.exists(CLIENT_SECRET_FILE):
        raise RuntimeError(
            "No valid Google token was found and the configured client secret file "
            f"does not exist: {CLIENT_SECRET_FILE}."
        )

    credentials = build_credentials()
    with open(token_file_path, "wb") as token_file:
        pickle.dump(credentials, token_file)
    return credentials


def normalize_creator_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def normalize_title_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (name or "").lower()).strip()


def _map_sender_to_creator(sender_header: str) -> str:
    display_name, email_address = parseaddr(sender_header or "")
    raw_value = display_name or (email_address.split("@")[0] if email_address else "") or sender_header
    first_token = raw_value.strip().split()[0] if raw_value.strip() else ""
    first_token = first_token.strip("<>\"'(),")

    for key, value in MAIL_NAME_MAP.items():
        if key.lower() == first_token.lower():
            return value

    return first_token.title() if first_token else "Unknown"


def _extract_text_plain_body(payload: dict) -> Optional[str]:
    mime_type = payload.get("mimeType")
    body = payload.get("body", {})
    encoded = body.get("data")

    if mime_type == "text/plain" and encoded:
        try:
            return base64.urlsafe_b64decode(encoded.encode("ascii")).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return None

    for part in payload.get("parts", []):
        text_body = _extract_text_plain_body(part)
        if text_body:
            return text_body

    return None


def _extract_shared_name_from_subject(subject_header: str) -> str:
    if not subject_header:
        return ""

    prefix = "Presentation shared with you:"
    if subject_header.startswith(prefix):
        shared_name = subject_header[len(prefix):].strip()
    else:
        shared_name = subject_header.strip()

    return shared_name.strip().strip('"').strip("'").strip()


def _build_round_link(presentation_id: str, slide_id: Optional[str], *, link_style: str) -> str:
    if link_style == "edit":
        base = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        return f"{base}#slide=id.{slide_id}" if slide_id else base

    base = f"https://docs.google.com/presentation/d/{presentation_id}/embed?start=false"
    return f"{base}#slide=id.{slide_id}" if slide_id else base


@dataclass(frozen=True)
class SharedRoundCandidate:
    presentation_id: str
    creator: str
    shared_date_iso: str
    shared_date_label: str
    shared_name: str
    normalized_shared_name: str
    original_url: str
    repair_link: str


def iter_target_rounds(*, include_blank: bool, creator_filter: Optional[str], limit: Optional[int]):
    from GPTrivia.models import GPTriviaRound

    queryset = GPTriviaRound.objects.order_by("date", "round_number", "title")

    round_objects = []
    for round_obj in queryset:
        link_value = round_obj.link or ""
        if PLACEHOLDER_PRESENTATION_ID in link_value or (include_blank and not link_value):
            if creator_filter and normalize_creator_name(round_obj.creator) != normalize_creator_name(creator_filter):
                continue
            round_objects.append(round_obj)
            if limit and len(round_objects) >= limit:
                break

    return round_objects


def _target_creator_date_pairs(rounds) -> set:
    pairs = set()
    for round_obj in rounds:
        if not round_obj.date:
            continue
        round_creator = normalize_creator_name(round_obj.creator)
        pairs.add((round_creator, round_obj.date.isoformat()))
        for wildcard_creator in SHARED_CREATOR_WILDCARDS:
            pairs.add((wildcard_creator, round_obj.date.isoformat()))
    return pairs


def _target_creator_name_pairs(rounds) -> set:
    pairs = set()
    for round_obj in rounds:
        normalized_title = normalize_title_name(round_obj.title)
        if not normalized_title:
            continue
        round_creator = normalize_creator_name(round_obj.creator)
        pairs.add((round_creator, normalized_title))
        for wildcard_creator in SHARED_CREATOR_WILDCARDS:
            pairs.add((wildcard_creator, normalized_title))
    return pairs


def _parse_shared_date(internal_date: str) -> Tuple[str, str]:
    shared_date_label = _format_pacific_timestamp(internal_date or "0")
    try:
        shared_date_iso = dt.datetime.strptime(shared_date_label, "%B %d, %Y").date().isoformat()
    except ValueError:
        shared_date_iso = ""
    return shared_date_iso, shared_date_label


def _fetch_message_ids(gmail_service) -> List[str]:
    query = 'subject:"Presentation shared with you:"'
    message_ids: List[str] = []
    page_token = None
    page_count = 0

    while True:
        page_count += 1
        response = gmail_service.users().messages().list(
            userId="me",
            q=query,
            maxResults=500,
            pageToken=page_token,
        ).execute()
        message_ids.extend(message["id"] for message in response.get("messages", []))
        log_progress(f"[gmail] fetched page {page_count} | messages so far: {len(message_ids)}")
        page_token = response.get("nextPageToken")
        if not page_token:
            return message_ids


def _fetch_message_metadata(gmail_service, message_id: str) -> Optional[dict]:
    try:
        return gmail_service.users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "internalDate", "Subject"],
        ).execute()
    except HttpError as exc:
        print(f"Skipping Gmail metadata {message_id}: {exc}", file=sys.stderr)
        return None


def _fetch_message_full(gmail_service, message_id: str) -> Optional[dict]:
    try:
        return gmail_service.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()
    except HttpError as exc:
        print(f"Skipping Gmail message {message_id}: {exc}", file=sys.stderr)
        return None


def collect_shared_round_candidates(
    *,
    credentials,
    link_style: str,
    progress_every: int,
    target_pairs,
    match_mode: str,
) -> List[SharedRoundCandidate]:
    gmail_service = build("gmail", "v1", credentials=credentials)
    candidates_by_presentation_id: Dict[str, SharedRoundCandidate] = {}
    message_ids = _fetch_message_ids(gmail_service)

    log_progress(f"[gmail] processing {len(message_ids)} shared-presentation messages")
    matched_metadata = 0
    fetched_bodies = 0

    for index, message_id in enumerate(message_ids, start=1):
        if index == 1 or index % progress_every == 0 or index == len(message_ids):
            log_progress(
                "[gmail] processing message "
                f"{index}/{len(message_ids)} | metadata matches: {matched_metadata} | "
                f"full bodies fetched: {fetched_bodies} | unique candidate decks: {len(candidates_by_presentation_id)}"
            )

        metadata = _fetch_message_metadata(gmail_service, message_id)
        if metadata is None:
            continue

        headers = {header["name"]: header["value"] for header in metadata.get("payload", {}).get("headers", [])}
        creator = _map_sender_to_creator(headers.get("From", ""))
        shared_date_iso, shared_date_label = _parse_shared_date(metadata.get("internalDate", "0"))
        shared_name = _extract_shared_name_from_subject(headers.get("Subject", ""))
        normalized_shared_name = normalize_title_name(shared_name)

        if match_mode == "name":
            target_key = (normalize_creator_name(creator), normalized_shared_name)
        else:
            target_key = (normalize_creator_name(creator), shared_date_iso)

        if target_key not in target_pairs:
            continue

        matched_metadata += 1

        message = _fetch_message_full(gmail_service, message_id)
        if message is None:
            continue
        fetched_bodies += 1

        body_text = _extract_text_plain_body(message.get("payload", {}))
        if not body_text:
            continue

        url_match = URL_PATTERN.search(body_text)
        if not url_match:
            continue

        original_url = url_match.group(1)
        presentation_id, slide_id = _extract_presentation_link_parts(original_url)
        if not presentation_id:
            continue

        candidate = SharedRoundCandidate(
            presentation_id=presentation_id,
            creator=creator,
            shared_date_iso=shared_date_iso,
            shared_date_label=shared_date_label,
            shared_name=shared_name,
            normalized_shared_name=normalized_shared_name,
            original_url=original_url,
            repair_link=_build_round_link(presentation_id, slide_id, link_style=link_style),
        )

        existing = candidates_by_presentation_id.get(presentation_id)
        if existing is None or candidate.shared_date_iso >= existing.shared_date_iso:
            candidates_by_presentation_id[presentation_id] = candidate

    log_progress(
        f"[gmail] finished scanning messages | metadata matches: {matched_metadata} | "
        f"full bodies fetched: {fetched_bodies} | unique candidate decks: {len(candidates_by_presentation_id)}"
    )
    return list(candidates_by_presentation_id.values())


def choose_candidate_for_round(
    round_obj,
    candidates: Sequence[SharedRoundCandidate],
    *,
    allow_date_only: bool,
    match_mode: str,
):
    round_creator = normalize_creator_name(round_obj.creator)
    round_date_iso = round_obj.date.isoformat() if round_obj.date else ""
    round_title_name = normalize_title_name(round_obj.title)

    creator_candidates = [
        candidate
        for candidate in candidates
        if normalize_creator_name(candidate.creator) == round_creator
        or normalize_creator_name(candidate.creator) in SHARED_CREATOR_WILDCARDS
    ]
    if not creator_candidates:
        return None, "no_creator_match", []

    if match_mode == "name":
        creator_and_name = [
            candidate
            for candidate in creator_candidates
            if candidate.normalized_shared_name == round_title_name
        ]
        if len(creator_and_name) == 1:
            return creator_and_name[0], "creator+name", creator_and_name
        if len(creator_and_name) > 1:
            return None, "ambiguous_name", creator_and_name
        return None, "no_safe_match", creator_candidates

    creator_and_date = [
        candidate
        for candidate in creator_candidates
        if candidate.shared_date_iso == round_date_iso
    ]
    if len(creator_and_date) == 1:
        return creator_and_date[0], "creator+date", creator_and_date
    if len(creator_and_date) > 1:
        return None, "ambiguous_date", creator_and_date

    if allow_date_only:
        date_only = [
            candidate
            for candidate in candidates
            if candidate.shared_date_iso == round_date_iso
        ]
        if len(date_only) == 1:
            return date_only[0], "date_only", date_only
        if len(date_only) > 1:
            return None, "ambiguous_date_only", date_only

    return None, "no_safe_match", creator_candidates


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find GPTrivia rounds still using the placeholder link and repair them "
            "by matching against shared Google Slides rounds using creator and shared date."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the repaired links back to GPTriviaRound records. Default is dry-run.",
    )
    parser.add_argument(
        "--include-blank",
        action="store_true",
        help="Also attempt to repair rounds with a blank link.",
    )
    parser.add_argument(
        "--creator",
        help="Only repair rounds for this creator.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only inspect this many placeholder rounds.",
    )
    parser.add_argument(
        "--allow-date-only",
        action="store_true",
        help="Allow a unique date-only match when creator matching fails in date mode.",
    )
    parser.add_argument(
        "--match-mode",
        choices=("date", "name"),
        default="date",
        help="Match shared rounds by creator plus date or creator plus shared file name. Default: date.",
    )
    parser.add_argument(
        "--link-style",
        choices=("embed", "edit"),
        default="embed",
        help="Write repaired links in embed or edit form. Default: embed.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Print progress every N processed messages/rounds. Default: 25.",
    )
    args = parser.parse_args()

    configure_django()

    try:
        credentials = load_credentials()
    except Exception as exc:
        print(f"Failed to initialize Google credentials: {exc}", file=sys.stderr)
        return 1

    rounds = list(
        iter_target_rounds(
            include_blank=args.include_blank,
            creator_filter=args.creator,
            limit=args.limit,
        )
    )
    if not rounds:
        print("No placeholder rounds found.")
        return 0

    log_progress(f"[rounds] found {len(rounds)} placeholder rounds to inspect")
    if args.match_mode == "name":
        target_pairs = _target_creator_name_pairs(rounds)
        log_progress(f"[rounds] unique creator/name pairs to search: {len(target_pairs)}")
    else:
        target_pairs = _target_creator_date_pairs(rounds)
        log_progress(f"[rounds] unique creator/date pairs to search: {len(target_pairs)}")

    candidates = collect_shared_round_candidates(
        credentials=credentials,
        link_style=args.link_style,
        progress_every=max(1, args.progress_every),
        target_pairs=target_pairs,
        match_mode=args.match_mode,
    )
    if not candidates:
        print("No shared presentation candidates were found in Gmail.", file=sys.stderr)
        return 1
    log_progress(f"[gmail] candidate pool ready: {len(candidates)} unique decks")

    updated = 0
    unmatched = 0
    ambiguous = 0

    for index, round_obj in enumerate(rounds, start=1):
        if index == 1 or index % max(1, args.progress_every) == 0 or index == len(rounds):
            log_progress(
                "[rounds] matching "
                f"{index}/{len(rounds)} | updated={updated} unmatched={unmatched} ambiguous={ambiguous}"
            )

        candidate, reason, related_candidates = choose_candidate_for_round(
            round_obj,
            candidates,
            allow_date_only=args.allow_date_only,
            match_mode=args.match_mode,
        )

        round_label = (
            f"id={round_obj.id} date={round_obj.date:%B %d, %Y} "
            f"creator={round_obj.creator} title={round_obj.title}"
        )

        if candidate is None:
            print(f"SKIP  {round_label} | {reason}")
            for preview in related_candidates[:3]:
                print(
                    "      candidate="
                    f"{preview.creator} | {preview.shared_date_label} | {preview.shared_name or '(no subject name)'} | {preview.original_url}"
                )
            if reason.startswith("ambiguous"):
                ambiguous += 1
            else:
                unmatched += 1
            continue

        print(
            f"{'APPLY' if args.apply else 'WOULD'} {round_label} | "
            f"match={reason} | shared={candidate.shared_date_label} | "
            f"name={candidate.shared_name or '(no subject name)'} | link={candidate.repair_link}"
        )
        if args.apply:
            round_obj.link = candidate.repair_link
            round_obj.save(update_fields=["link"])
        updated += 1

    print("\nSummary:")
    print(f"  scanned_rounds: {len(rounds)}")
    print(f"  updated_or_would_update: {updated}")
    print(f"  unmatched: {unmatched}")
    print(f"  ambiguous: {ambiguous}")
    print(f"  apply_mode: {args.apply}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
