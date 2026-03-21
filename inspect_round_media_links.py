#!/usr/bin/env python3
import argparse
import json
import os
from typing import Any


def configure_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "GPTrivia.settings")

    import django

    django.setup()


def json_dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str)


def print_block(label: str, value: Any):
    print(f"{label}:")
    print(json_dump(value))


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Inspect a round's source slide media payload and Apps Script-visible "
            "linked media metadata."
        )
    )
    parser.add_argument(
        "round_id",
        type=int,
        help="GPTriviaRound id to inspect.",
    )
    parser.add_argument(
        "--slide-number",
        type=int,
        default=0,
        help="Optional 1-based slide number within the analyzed round range to inspect.",
    )
    args = parser.parse_args()

    configure_django()

    from GPTrivia.models import GPTriviaRound
    from GPTrivia.round_analysis import _build_round_slide_payload, _run_apps_script_function

    try:
        round_obj = GPTriviaRound.objects.get(id=args.round_id)
    except GPTriviaRound.DoesNotExist:
        print(f"Round {args.round_id} does not exist.")
        return 1

    print(f"Round id: {round_obj.id}")
    print(f"Title: {round_obj.title}")
    print(f"Creator: {round_obj.creator}")
    print(f"Date: {round_obj.date}")
    print(f"Source link: {round_obj.source_link or '(blank)'}")
    print(f"Stored link: {round_obj.link or '(blank)'}")

    try:
        slide_payload = _build_round_slide_payload(round_obj, include_thumbnails=False)
    except Exception as exc:
        print(f"Could not build slide payload: {type(exc).__name__}: {exc}")
        return 1

    print(f"Presentation id: {slide_payload.get('presentation_id') or '(blank)'}")
    print(f"Slide range: {slide_payload.get('slide_range_label') or '(blank)'}")

    selected_slides = slide_payload.get("slides", [])
    if args.slide_number:
        selected_slides = [
            slide for slide in selected_slides if int(slide.get("slide_number") or 0) == args.slide_number
        ]
        if not selected_slides:
            print(f"No analyzed slide matched slide number {args.slide_number}.")
            return 1

    for slide in selected_slides:
        slide_number = slide.get("slide_number")
        slide_id = slide.get("slide_id") or ""
        print("\n" + "=" * 72)
        print(f"Slide {slide_number} | slide_id={slide_id}")
        print(f"Slide URL: {slide.get('slide_url') or '(blank)'}")
        print(f"Slide text: {slide.get('text') or '(blank)'}")
        print_block("media_items", slide.get("media_items") or [])
        print_block("text_items", slide.get("text_items") or [])

        try:
            linked_rows = _run_apps_script_function(
                "getSlideLinkedMediaUrls",
                [slide_payload.get("presentation_id"), slide_id],
            )
        except Exception as exc:
            linked_rows = {
                "error": f"{type(exc).__name__}: {exc}",
            }
        print_block("apps_script_linked_rows", linked_rows)

        try:
            debug_rows = _run_apps_script_function(
                "debugSlideLinkedMediaUrls",
                [slide_payload.get("presentation_id"), slide_id],
            )
        except Exception as exc:
            debug_rows = {
                "error": f"{type(exc).__name__}: {exc}",
            }
        print_block("apps_script_debug_rows", debug_rows)

        try:
            page_element_debug = _run_apps_script_function(
                "debugSlidePageElements",
                [slide_payload.get("presentation_id"), slide_id],
            )
        except Exception as exc:
            page_element_debug = {
                "error": f"{type(exc).__name__}: {exc}",
            }
        print_block("apps_script_page_element_debug", page_element_debug)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
