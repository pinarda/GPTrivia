#!/usr/bin/env python3
import argparse
import json
import shutil
import socket
import subprocess
import tempfile
import time
from typing import Any, Dict, List, Optional

import requests


WEBDRIVER_STARTUP_TIMEOUT_SECONDS = 10
WEBDRIVER_REQUEST_TIMEOUT_SECONDS = 30


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_webdriver(port: int, process: subprocess.Popen) -> None:
    deadline = time.time() + WEBDRIVER_STARTUP_TIMEOUT_SECONDS
    base_url = f"http://127.0.0.1:{port}"
    while time.time() < deadline:
        if process.poll() is not None:
            raise RuntimeError("safaridriver exited before accepting connections.")
        try:
            requests.get(f"{base_url}/status", timeout=1)
            return
        except requests.RequestException:
            time.sleep(0.2)
    raise RuntimeError("Timed out waiting for safaridriver to start.")


def webdriver_request(method: str, url: str, *, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    response = requests.request(
        method,
        url,
        json=payload,
        timeout=WEBDRIVER_REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code >= 400:
        response_text = response.text.strip()
        raise RuntimeError(
            f"WebDriver request failed with HTTP {response.status_code} for {url}.\n"
            f"Response body: {response_text or '(empty)'}"
        )
    if not response.content:
        return {}
    return response.json()


def create_safari_session(port: int) -> str:
    base_url = f"http://127.0.0.1:{port}"
    response = webdriver_request(
        "POST",
        f"{base_url}/session",
        payload={
            "capabilities": {
                "alwaysMatch": {
                    "browserName": "safari",
                }
            }
        },
    )
    session_id = response.get("value", {}).get("sessionId") or response.get("sessionId")
    if not session_id:
        raise RuntimeError(f"Could not create Safari WebDriver session: {json.dumps(response, indent=2)}")
    return str(session_id)


def navigate_to_url(port: int, session_id: str, url: str) -> None:
    webdriver_request(
        "POST",
        f"http://127.0.0.1:{port}/session/{session_id}/url",
        payload={"url": url},
    )


def execute_script(port: int, session_id: str, script: str) -> Any:
    response = webdriver_request(
        "POST",
        f"http://127.0.0.1:{port}/session/{session_id}/execute/sync",
        payload={"script": script, "args": []},
    )
    return response.get("value")


def delete_session(port: int, session_id: str) -> None:
    try:
        webdriver_request("DELETE", f"http://127.0.0.1:{port}/session/{session_id}")
    except Exception:
        pass


def collect_candidate_drive_elements(port: int, session_id: str) -> List[Dict[str, Any]]:
    script = collect_candidate_drive_elements_script()
    return list(execute_script(port, session_id, script) or [])


def collect_candidate_drive_elements_script() -> str:
    return r"""
const norm = (value) => (value || '').toString().trim();
const hasDriveSignal = (text) => {
  const v = norm(text).toLowerCase();
  return v.includes('drive') || v.includes('open in drive') || v.includes('google drive');
};

const candidates = [];
for (const el of Array.from(document.querySelectorAll('*'))) {
  const href = norm(el.getAttribute && el.getAttribute('href'));
  const ariaLabel = norm(el.getAttribute && el.getAttribute('aria-label'));
  const title = norm(el.getAttribute && el.getAttribute('title'));
  const text = norm((el.innerText || el.textContent || '').replace(/\s+/g, ' ')).slice(0, 300);
  const dataAction = norm(el.getAttribute && el.getAttribute('data-action'));
  const role = norm(el.getAttribute && el.getAttribute('role'));

  const driveHref = href.includes('drive.google.com') || href.includes('/file/d/');
  const driveText = hasDriveSignal(text) || hasDriveSignal(ariaLabel) || hasDriveSignal(title);
  if (!driveHref && !driveText) {
    continue;
  }

  const rect = el.getBoundingClientRect();
  candidates.push({
    tag: el.tagName,
    role,
    href,
    aria_label: ariaLabel,
    title,
    text,
    data_action: dataAction,
    visible: !!(rect.width || rect.height),
    x: Math.round(rect.x),
    y: Math.round(rect.y),
    width: Math.round(rect.width),
    height: Math.round(rect.height),
  });
}
return candidates;
"""


def run_osascript(script: str) -> str:
    process = subprocess.run(
        ["osascript", "-"],
        input=script,
        text=True,
        capture_output=True,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"osascript failed with code {process.returncode}.\n"
            f"stderr: {process.stderr.strip() or '(empty)'}"
        )
    return (process.stdout or "").strip()


def apple_script_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def open_safari_url_via_apple_events(url: str) -> None:
    script = f"""
set targetUrl to {apple_script_string(url)}
tell application "Safari"
    activate
    if (count of windows) is 0 then
        make new document with properties {{URL:targetUrl}}
    else
        set URL of current tab of front window to targetUrl
    end if
end tell
"""
    run_osascript(script)


def collect_candidate_drive_elements_via_apple_events() -> List[Dict[str, Any]]:
    js_source = collect_candidate_drive_elements_script()
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as temp_file:
        temp_file.write(js_source)
        temp_path = temp_file.name

    try:
        script = f"""
set jsPath to {apple_script_string(temp_path)}
set jsSource to do shell script "cat " & quoted form of jsPath
tell application "Safari"
    activate
    set jsResult to do JavaScript jsSource in current tab of front window
end tell
return jsResult
"""
        output = run_osascript(script)
        if not output:
            return []
        return list(json.loads(output))
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Manual browser-automation probe for Google Slides music widgets. "
            "Opens a Safari automation session so you can manually open the "
            "'Open in Drive' menu, then dumps DOM candidates for the underlying link."
        )
    )
    parser.add_argument(
        "slide_url",
        help="Full Google Slides editor URL for the specific slide to inspect.",
    )
    parser.add_argument(
        "--mode",
        choices=["apple-events", "webdriver"],
        default="apple-events",
        help=(
            "How to probe Safari. 'apple-events' opens a normal Safari tab you can interact with; "
            "'webdriver' uses an automated Safari window."
        ),
    )
    args = parser.parse_args()

    if args.mode == "apple-events":
        try:
            open_safari_url_via_apple_events(args.slide_url)
        except RuntimeError as exc:
            print(str(exc))
            print(
                "\nIf Apple Events access failed, make sure:\n"
                "1. Safari is installed and can be opened normally.\n"
                "2. In Safari, enable `Develop > Allow JavaScript from Apple Events`.\n"
                "3. Approve any macOS Automation prompts for Terminal or your shell."
            )
            return 1

        print("\nSafari opened in a normal tab.")
        print("1. Sign into Google in that Safari window if needed.")
        print("2. Open the target slide if it is not already visible.")
        print("3. Click the music widget.")
        print("4. Open the menu that shows 'Open in Drive'.")
        print("5. Leave that menu visible, then come back here and press Enter.\n")
        input("Press Enter once the Drive menu is visible...")

        print("\nSafari automation window opened.")
        try:
            candidates = collect_candidate_drive_elements_via_apple_events()
        except RuntimeError as exc:
            print(str(exc))
            print(
                "\nSafari opened fine, but JavaScript injection failed. "
                "The most common fix is enabling `Develop > Allow JavaScript from Apple Events` in Safari."
            )
            return 1
        print("\nDOM candidates with Drive/file signals:")
        print(json.dumps(candidates, indent=2, sort_keys=True))

        if not candidates:
            print(
                "\nNo Drive-related DOM candidates were found. "
                "That suggests the visible menu may be rendered in a way the DOM probe cannot see, "
                "or the link is not exposed as a normal DOM href."
            )
        return 0

    safaridriver_path = shutil.which("safaridriver")
    if not safaridriver_path:
        print("safaridriver is not available on this machine.")
        return 1

    port = find_free_port()
    process = subprocess.Popen(
        [safaridriver_path, "-p", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    session_id = None
    try:
        wait_for_webdriver(port, process)
        session_id = create_safari_session(port)
        navigate_to_url(port, session_id, args.slide_url)

        print("\nSafari automation window opened.")
        print("1. Sign into Google in that Safari window if needed.")
        print("2. Open the target slide if it is not already visible.")
        print("3. Click the music widget.")
        print("4. Open the menu that shows 'Open in Drive'.")
        print("5. Leave that menu visible, then come back here and press Enter.\n")
        input("Press Enter once the Drive menu is visible...")

        candidates = collect_candidate_drive_elements(port, session_id)
        print("\nDOM candidates with Drive/file signals:")
        print(json.dumps(candidates, indent=2, sort_keys=True))

        if not candidates:
            print(
                "\nNo Drive-related DOM candidates were found. "
                "That suggests the visible menu may be rendered in a way the DOM probe cannot see, "
                "or the link is not exposed as a normal DOM href."
            )
        return 0
    except RuntimeError as exc:
        print(str(exc))
        print(
            "\nIf Safari session creation failed, the usual fixes are:\n"
            "1. Run `safaridriver --enable` once.\n"
            "2. In Safari, enable `Develop > Allow Remote Automation`.\n"
            "3. Re-run this script and approve any macOS automation prompts."
        )
        return 1
    finally:
        if session_id:
            delete_session(port, session_id)
        try:
            process.terminate()
            process.wait(timeout=3)
        except Exception:
            process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
