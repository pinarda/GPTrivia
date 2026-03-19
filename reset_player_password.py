#!/usr/bin/env python3
import argparse
import os
import sys


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def find_user(username: str):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    exact_match = User.objects.filter(username=username).first()
    if exact_match:
        return exact_match

    ci_matches = list(User.objects.filter(username__iexact=username).order_by("id"))
    if len(ci_matches) == 1:
        return ci_matches[0]
    if len(ci_matches) > 1:
        raise RuntimeError(
            "More than one user matched case-insensitively. "
            "Please rerun with the exact username."
        )
    return None


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Reset a Django user's password, defaulting to the shared fallback password `password`."
        )
    )
    parser.add_argument(
        "username",
        help="Username to update, for example Alex.",
    )
    parser.add_argument(
        "--password",
        default="password",
        help="New password to set. Defaults to `password`.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    args = parser.parse_args()

    if not args.yes and not sys.stdin.isatty():
        print("This script needs a TTY for confirmation unless you pass --yes.", file=sys.stderr)
        return 1

    configure_django()

    try:
        user = find_user(args.username)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if user is None:
        print(f"No user found with username `{args.username}`.", file=sys.stderr)
        return 1

    print(f"User found: id={user.id} username={user.username}")
    if not args.yes:
        confirm = input(
            f"Reset password for `{user.username}` to `{args.password}`? [y/N]: "
        ).strip().lower()
        if confirm not in {"y", "yes"}:
            print("Canceled.")
            return 0

    user.set_password(args.password)
    user.save(update_fields=["password"])
    print(f"Password updated for `{user.username}`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
