#!/usr/bin/env python3
import argparse
import base64
import os
import pickle
import re
import sys
from dataclasses import dataclass
from email.utils import parseaddr
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from GPTrivia.mail import (
    CLIENT_SECRET_FILE,
    MAIL_NAME_MAP,
    SCOPES,
    URL_PATTERN,
    _extract_presentation_link_parts,
    _format_pacific_timestamp,
    _normalize_round_title,
    build_credentials,
    token_file_path,
)


PLACEHOLDER_PRESENTATION_ID = "1gC9DR9TmQK_9ls8Npw8Sc99qKI6YN9nRqLuVj0W07ns"
GOOGLE_SLIDES_MIME_TYPE = "application/vnd.google-apps.presentation"


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


def _first_slide_title_and_id(presentation: dict) -> Tuple[str, Optional[str]]:
    slides = presentation.get("slides", [])
    if not slides:
        return "", None

    first_slide = slides[0]
    title_chunks: List[str] = []
    for element in first_slide.get("pageElements", []):
        shape = element.get("shape", {})
        for text_element in shape.get("text", {}).get("textElements", []):
            text_run = text_element.get("textRun")
            if text_run and "content" in text_run:
                title_chunks.append(text_run["content"])

    title_text = re.sub(r"\s+", " ", " ".join(title_chunks)).strip()
    return title_text, first_slide.get("objectId")


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
    title: str
    normalized_title: str
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


def _fetch_message_ids(gmail_service) -> List[str]:
    query = 'subject:"Presentation shared with you:"'
    message_ids: List[str] = []
    page_token = None

    while True:
        response = gmail_service.users().messages().list(
            userId="me",
            q=query,
            maxResults=500,
            pageToken=page_token,
        ).execute()
        message_ids.extend(message["id"] for message in response.get("messages", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return message_ids


def collect_shared_round_candidates(*, credentials, link_style: str) -> List[SharedRoundCandidate]:
    gmail_service = build("gmail", "v1", credentials=credentials)
    drive_service = build("drive", "v3", credentials=credentials)
    slides_service = build("slides", "v1", credentials=credentials)

    candidates_by_presentation_id: Dict[str, SharedRoundCandidate] = {}
    presentation_cache: Dict[str, Optional[Tuple[str, Optional[str], str]]] = {}

    for message_id in _fetch_message_ids(gmail_service):
        try:
            message = gmail_service.users().messages().get(
                userId="me",
                id=message_id,
                format="full",
            ).execute()
        except HttpError as exc:
            print(f"Skipping Gmail message {message_id}: {exc}", file=sys.stderr)
            continue

        headers = {header["name"]: header["value"] for header in message.get("payload", {}).get("headers", [])}
        sender_header = headers.get("From", "")
        creator = _map_sender_to_creator(sender_header)
        shared_date_label = _format_pacific_timestamp(message.get("internalDate", "0"))
        shared_date_iso = None
        try:
            import datetime as _datetime

            shared_date_iso = _datetime.datetime.strptime(shared_date_label, "%B %d, %Y").date().isoformat()
        except ValueError:
            shared_date_iso = ""

        body_text = _extract_text_plain_body(message.get("payload", {}))
        if not body_text:
            continue

        url_match = URL_PATTERN.search(body_text)
        if not url_match:
            continue

        original_url = url_match.group(1)
        presentation_id, _ = _extract_presentation_link_parts(original_url)
        if not presentation_id:
            continue

        if presentation_id not in presentation_cache:
            try:
                metadata = drive_service.files().get(
                    fileId=presentation_id,
                    fields="id,mimeType,name",
                    supportsAllDrives=True,
                ).execute()
            except HttpError as exc:
                print(f"Skipping Drive file {presentation_id}: {exc}", file=sys.stderr)
                presentation_cache[presentation_id] = None
                continue

            if metadata.get("mimeType") != GOOGLE_SLIDES_MIME_TYPE:
                presentation_cache[presentation_id] = None
                continue

            try:
                presentation = slides_service.presentations().get(presentationId=presentation_id).execute()
            except HttpError as exc:
                print(f"Skipping Slides presentation {presentation_id}: {exc}", file=sys.stderr)
                presentation_cache[presentation_id] = None
                continue

            title_text, first_slide_id = _first_slide_title_and_id(presentation)
            display_title = title_text or metadata.get("name", "")
            presentation_cache[presentation_id] = (display_title, first_slide_id, metadata.get("name", ""))

        cached = presentation_cache.get(presentation_id)
        if not cached:
            continue

        display_title, first_slide_id, _drive_name = cached
        normalized_title = _normalize_round_title(display_title)
        candidate = SharedRoundCandidate(
            presentation_id=presentation_id,
            creator=creator,
            shared_date_iso=shared_date_iso,
            shared_date_label=shared_date_label,
            title=display_title,
            normalized_title=normalized_title,
            original_url=original_url,
            repair_link=_build_round_link(presentation_id, first_slide_id, link_style=link_style),
        )

        existing = candidates_by_presentation_id.get(presentation_id)
        if existing is None or candidate.shared_date_iso >= existing.shared_date_iso:
            candidates_by_presentation_id[presentation_id] = candidate

    return list(candidates_by_presentation_id.values())


def _title_contains(candidate_title: str, round_title: str) -> bool:
    if not candidate_title or not round_title:
        return False
    return candidate_title in round_title or round_title in candidate_title


def choose_candidate_for_round(round_obj, candidates: Sequence[SharedRoundCandidate], *, allow_date_only: bool):
    round_title = _normalize_round_title(round_obj.title)
    round_creator = normalize_creator_name(round_obj.creator)
    round_date_iso = round_obj.date.isoformat() if round_obj.date else ""

    creator_candidates = [
        candidate
        for candidate in candidates
        if normalize_creator_name(candidate.creator) == round_creator
    ]
    if not creator_candidates:
        return None, "no_creator_match", []

    title_exact = [
        candidate
        for candidate in creator_candidates
        if candidate.normalized_title and candidate.normalized_title == round_title
    ]
    title_exact_and_date = [
        candidate for candidate in title_exact if candidate.shared_date_iso == round_date_iso
    ]
    if len(title_exact_and_date) == 1:
        return title_exact_and_date[0], "creator+title+date", title_exact_and_date
    if len(title_exact) == 1:
        return title_exact[0], "creator+title", title_exact
    if len(title_exact_and_date) > 1 or len(title_exact) > 1:
        return None, "ambiguous_title", title_exact_and_date or title_exact

    fuzzy_title_and_date = [
        candidate
        for candidate in creator_candidates
        if candidate.shared_date_iso == round_date_iso
        and _title_contains(candidate.normalized_title, round_title)
    ]
    if len(fuzzy_title_and_date) == 1:
        return fuzzy_title_and_date[0], "creator+date+fuzzy_title", fuzzy_title_and_date
    if len(fuzzy_title_and_date) > 1:
        return None, "ambiguous_fuzzy_title", fuzzy_title_and_date

    if allow_date_only:
        date_only = [
            candidate
            for candidate in creator_candidates
            if candidate.shared_date_iso == round_date_iso
        ]
        if len(date_only) == 1:
            return date_only[0], "creator+date", date_only
        if len(date_only) > 1:
            return None, "ambiguous_date", date_only

    return None, "no_safe_match", creator_candidates


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Find GPTrivia rounds still using the placeholder link and repair them "
            "by matching against shared Google Slides rounds."
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
        help="Allow a unique creator+date match even when title matching fails.",
    )
    parser.add_argument(
        "--link-style",
        choices=("embed", "edit"),
        default="embed",
        help="Write repaired links in embed or edit form. Default: embed.",
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

    candidates = collect_shared_round_candidates(credentials=credentials, link_style=args.link_style)
    if not candidates:
        print("No shared presentation candidates were found in Gmail.", file=sys.stderr)
        return 1

    updated = 0
    unmatched = 0
    ambiguous = 0

    for round_obj in rounds:
        candidate, reason, related_candidates = choose_candidate_for_round(
            round_obj,
            candidates,
            allow_date_only=args.allow_date_only,
        )

        round_label = (
            f"id={round_obj.id} date={round_obj.date:%B %d, %Y} "
            f"creator={round_obj.creator} title={round_obj.title}"
        )

        if candidate is None:
            print(f"SKIP  {round_label} | {reason}")
            preview_candidates = related_candidates[:3]
            for preview in preview_candidates:
                print(
                    "      candidate="
                    f"{preview.creator} | {preview.shared_date_label} | {preview.title} | {preview.original_url}"
                )
            if reason.startswith("ambiguous"):
                ambiguous += 1
            else:
                unmatched += 1
            continue

        print(
            f"{'APPLY' if args.apply else 'WOULD'} {round_label} | "
            f"match={reason} | shared={candidate.shared_date_label} | link={candidate.repair_link}"
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
