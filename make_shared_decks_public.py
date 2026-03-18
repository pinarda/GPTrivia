#!/usr/bin/env python3
import argparse
import os
import pickle
import sys
from typing import Iterable, Optional

from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from GPTrivia.mail import CLIENT_SECRET_FILE, SCOPES, build_credentials, token_file_path


PRESENTATION_MIME_TYPE = "application/vnd.google-apps.presentation"


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
            f"does not exist: {CLIENT_SECRET_FILE}. "
            "Set up token.pickle first or update CLIENT_SECRET_FILE."
        )

    credentials = build_credentials()
    with open(token_file_path, "wb") as token_file:
        pickle.dump(credentials, token_file)
    return credentials


def build_drive_query(*, owned_only: bool, shared_with_me_only: bool, name_contains: Optional[str]) -> str:
    query_parts = [
        f"mimeType = '{PRESENTATION_MIME_TYPE}'",
        "trashed = false",
    ]

    if owned_only:
        query_parts.append("'me' in owners")

    if shared_with_me_only:
        query_parts.append("sharedWithMe = true")

    if name_contains:
        safe_name = name_contains.replace("'", "\\'")
        query_parts.append(f"name contains '{safe_name}'")

    return " and ".join(query_parts)


def iter_presentations(
    drive_service,
    *,
    owned_only: bool,
    shared_with_me_only: bool,
    name_contains: Optional[str],
    limit: Optional[int],
) -> Iterable[dict]:
    query = build_drive_query(
        owned_only=owned_only,
        shared_with_me_only=shared_with_me_only,
        name_contains=name_contains,
    )

    page_token = None
    yielded = 0
    while True:
        response = drive_service.files().list(
            q=query,
            spaces="drive",
            fields=(
                "nextPageToken, "
                "files(id, name, webViewLink, shared, ownedByMe, owners(displayName,emailAddress), capabilities(canShare))"
            ),
            pageToken=page_token,
            pageSize=min(limit - yielded, 1000) if limit else 1000,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute()

        for file_info in response.get("files", []):
            yield file_info
            yielded += 1
            if limit and yielded >= limit:
                return

        page_token = response.get("nextPageToken")
        if not page_token:
            return


def get_existing_anyone_permission(drive_service, file_id: str) -> Optional[dict]:
    response = drive_service.permissions().list(
        fileId=file_id,
        fields="permissions(id,type,role,allowFileDiscovery)",
        supportsAllDrives=True,
    ).execute()

    for permission in response.get("permissions", []):
        if permission.get("type") == "anyone":
            return permission
    return None


def ensure_anyone_with_link_reader(drive_service, file_info: dict, *, dry_run: bool) -> str:
    file_id = file_info["id"]
    anyone_permission = get_existing_anyone_permission(drive_service, file_id)
    if anyone_permission:
        role = anyone_permission.get("role", "unknown")
        discovery = anyone_permission.get("allowFileDiscovery")
        if role in {"reader", "writer", "commenter"} and discovery is False:
            return "already_public"
        if dry_run:
            return "would_update_existing_anyone_permission"

        drive_service.permissions().update(
            fileId=file_id,
            permissionId=anyone_permission["id"],
            body={
                "role": "reader",
                "allowFileDiscovery": False,
            },
            supportsAllDrives=True,
        ).execute()
        return "updated_existing_anyone_permission"

    if dry_run:
        return "would_create_anyone_permission"

    drive_service.permissions().create(
        fileId=file_id,
        body={
            "type": "anyone",
            "role": "reader",
            "allowFileDiscovery": False,
        },
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return "created_anyone_permission"


def main():
    parser = argparse.ArgumentParser(
        description="Make Google Slides decks readable by anyone with the link."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without modifying Drive permissions.",
    )
    parser.add_argument(
        "--owned-only",
        action="store_true",
        help="Only process presentations owned by the authenticated Drive account.",
    )
    parser.add_argument(
        "--shared-with-me-only",
        action="store_true",
        help="Only process presentations that appear in Shared with me.",
    )
    parser.add_argument(
        "--name-contains",
        help="Only process presentations whose Drive name contains this text.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Process at most this many presentations.",
    )
    args = parser.parse_args()

    try:
        credentials = load_credentials()
        drive_service = build("drive", "v3", credentials=credentials)
    except Exception as exc:
        print(f"Failed to initialize Google Drive credentials: {exc}", file=sys.stderr)
        return 1

    summary = {
        "already_public": 0,
        "created_anyone_permission": 0,
        "updated_existing_anyone_permission": 0,
        "would_create_anyone_permission": 0,
        "would_update_existing_anyone_permission": 0,
        "skipped_no_share_permission": 0,
        "failed": 0,
    }

    processed = 0
    for file_info in iter_presentations(
        drive_service,
        owned_only=args.owned_only,
        shared_with_me_only=args.shared_with_me_only,
        name_contains=args.name_contains,
        limit=args.limit,
    ):
        processed += 1
        can_share = bool((file_info.get("capabilities") or {}).get("canShare", False))
        owner_names = ", ".join(
            owner.get("displayName") or owner.get("emailAddress") or "Unknown"
            for owner in (file_info.get("owners") or [])
        ) or "Unknown"
        descriptor = f"{file_info['name']} ({file_info['id']})"

        if not can_share:
            summary["skipped_no_share_permission"] += 1
            print(f"SKIP  {descriptor} | owner={owner_names} | cannot change sharing")
            continue

        try:
            result = ensure_anyone_with_link_reader(
                drive_service,
                file_info,
                dry_run=args.dry_run,
            )
            summary[result] += 1
            print(f"OK    {descriptor} | owner={owner_names} | {result}")
        except HttpError as exc:
            summary["failed"] += 1
            print(f"FAIL  {descriptor} | owner={owner_names} | {exc}", file=sys.stderr)

    print("\nSummary:")
    print(f"  Processed: {processed}")
    for key, value in summary.items():
        print(f"  {key}: {value}")

    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
