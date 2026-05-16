#!/usr/bin/env python3
"""AppleScript automation for DropCatch bulk backorders.

Uses osascript to control Safari or Chrome for semi-automated backorder
placement. Opens each domain page with a pause between each for the user
to review and confirm.

Modes:
  - tabs:  Open all domains as new tabs (fast, user clicks backorder manually)
  - step:  Open one at a time, wait for user keypress before next
  - generate: Output a standalone .scpt file for direct osascript use

DropCatch URL patterns:
  - Listing: https://www.dropcatch.com/snap/listing/{domain}
  - Domain:  https://www.dropcatch.com/domain/{domain}

Usage:
    python3 scripts/sprint28_dropcatch_applescript.py --domains ghost.com foo.com
    python3 scripts/sprint28_dropcatch_applescript.py --tier critical --mode step
    python3 scripts/sprint28_dropcatch_applescript.py --tier critical --mode generate --output bulk.scpt
    python3 scripts/sprint28_dropcatch_applescript.py --browser safari
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKORDER_QUEUE = PROJECT_ROOT / "data" / "backorder_queue.json"
DROPCATCH_URL = "https://www.dropcatch.com/snap/listing/{domain}"
TAB_DELAY_SEC = 2.0
STEP_DELAY_SEC = 1.0
MAX_BATCH_SIZE = 30


# ---------------------------------------------------------------------------
# AppleScript generators
# ---------------------------------------------------------------------------
def generate_chrome_open_tab(url: str) -> str:
    """Generate AppleScript to open a URL in a new Chrome tab."""
    return f'''tell application "Google Chrome"
    activate
    if (count of windows) = 0 then
        make new window
        set URL of active tab of front window to "{url}"
    else
        tell front window
            make new tab with properties {{URL:"{url}"}}
        end tell
    end if
end tell'''


def generate_safari_open_tab(url: str) -> str:
    """Generate AppleScript to open a URL in a new Safari tab."""
    return f'''tell application "Safari"
    activate
    if (count of windows) = 0 then
        make new document with properties {{URL:"{url}"}}
    else
        tell front window
            set current tab to (make new tab with properties {{URL:"{url}"}})
        end tell
    end if
end tell'''


def generate_bulk_script(domains: list[str], browser: str) -> str:
    """Generate a standalone AppleScript for bulk tab opening.

    This creates a single .scpt-compatible script that opens all domains
    with delays between each.
    """
    assert len(domains) > 0, "No domains provided"
    assert browser in ("chrome", "safari"), f"Unknown browser: {browser}"

    lines = [
        "-- DropCatch Bulk Backorder Opener",
        f"-- Generated for {len(domains)} domain(s)",
        f"-- Browser: {browser.title()}",
        "",
    ]

    if browser == "chrome":
        lines.append('tell application "Google Chrome"')
        lines.append("    activate")
        lines.append("    if (count of windows) = 0 then")
        lines.append("        make new window")
        lines.append("    end if")
        for i, domain in enumerate(domains):
            url = DROPCATCH_URL.format(domain=domain)
            if i == 0:
                lines.append(f'    set URL of active tab of front window to "{url}"')
            else:
                lines.append(f"    delay {TAB_DELAY_SEC}")
                lines.append("    tell front window")
                lines.append(f'        make new tab with properties {{URL:"{url}"}}')
                lines.append("    end tell")
        lines.append("end tell")
    else:
        lines.append('tell application "Safari"')
        lines.append("    activate")
        for i, domain in enumerate(domains):
            url = DROPCATCH_URL.format(domain=domain)
            if i == 0:
                lines.append(f'    make new document with properties {{URL:"{url}"}}')
            else:
                lines.append(f"    delay {TAB_DELAY_SEC}")
                lines.append("    tell front window")
                lines.append(
                    f'        set current tab to (make new tab with properties {{URL:"{url}"}})'
                )
                lines.append("    end tell")
        lines.append("end tell")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# osascript runner
# ---------------------------------------------------------------------------
def run_applescript(script: str) -> bool:
    """Execute an AppleScript string via osascript. Returns True on success."""
    assert len(script) > 0, "Empty AppleScript"
    result = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        print(f"  osascript error: {result.stderr.strip()}")
        return False
    return True


# ---------------------------------------------------------------------------
# Domain loading (shared with opener)
# ---------------------------------------------------------------------------
def load_domains(args: argparse.Namespace) -> list[str]:
    """Load domains from CLI args or backorder queue file."""
    if args.domains:
        return [d.strip().lower() for d in args.domains if d.strip()]

    queue_path = Path(args.queue_file)
    assert queue_path.exists(), f"Queue file not found: {queue_path}"
    with open(queue_path, "r") as f:
        data = json.load(f)

    queue = data.get("queue", [])
    if args.tier:
        allowed = {t.strip().upper() for t in args.tier.split(",")}
        queue = [d for d in queue if d.get("tier", "").upper() in allowed]

    seen: set[str] = set()
    result: list[str] = []
    for entry in queue:
        domain = entry.get("domain", "").strip().lower()
        if domain and domain not in seen:
            seen.add(domain)
            result.append(domain)
    return result


# ---------------------------------------------------------------------------
# Mode handlers
# ---------------------------------------------------------------------------
def mode_tabs(domains: list[str], browser: str, dry_run: bool) -> int:
    """Open all domains as browser tabs with delays between each."""
    assert len(domains) <= MAX_BATCH_SIZE, f"Too many ({len(domains)}). Max {MAX_BATCH_SIZE}."
    gen = generate_chrome_open_tab if browser == "chrome" else generate_safari_open_tab
    opened = 0

    for i, domain in enumerate(domains):
        url = DROPCATCH_URL.format(domain=domain)
        if dry_run:
            print(f"  [DRY RUN] Would open: {url}")
            opened += 1
        else:
            script = gen(url)
            if run_applescript(script):
                print(f"  Opened: {url}")
                opened += 1
            else:
                print(f"  FAILED: {url}")
        if i < len(domains) - 1 and not dry_run:
            time.sleep(TAB_DELAY_SEC)

    print(f"\nOpened {opened}/{len(domains)} tabs in {browser.title()}")
    return 0 if opened == len(domains) else 1


def mode_step(domains: list[str], browser: str, dry_run: bool) -> int:
    """Open domains one at a time, waiting for user confirmation."""
    gen = generate_chrome_open_tab if browser == "chrome" else generate_safari_open_tab

    for i, domain in enumerate(domains):
        url = DROPCATCH_URL.format(domain=domain)
        print(f"\n[{i + 1}/{len(domains)}] {domain}")
        print(f"  URL: {url}")

        if dry_run:
            print("  [DRY RUN] Skipped")
        else:
            script = gen(url)
            if run_applescript(script):
                print("  Opened in browser")
            else:
                print("  FAILED to open")

        if i < len(domains) - 1:
            try:
                input("  Press Enter for next domain (Ctrl+C to stop)... ")
            except KeyboardInterrupt:
                print("\n\nStopped by user.")
                return 0
            time.sleep(STEP_DELAY_SEC)

    print(f"\nAll {len(domains)} domains processed.")
    return 0


def mode_generate(domains: list[str], browser: str, output: str | None) -> int:
    """Generate a standalone AppleScript file."""
    script = generate_bulk_script(domains, browser)

    if output:
        out_path = Path(output)
        with open(out_path, "w") as f:
            f.write(script)
        print(f"Generated: {out_path} ({len(domains)} domains)")
    else:
        print(script)

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Build argument parser."""
    parser = argparse.ArgumentParser(
        description="AppleScript automation for DropCatch bulk backorders."
    )
    parser.add_argument("--domains", nargs="*", default=None, help="Domain names")
    parser.add_argument("--queue-file", default=str(BACKORDER_QUEUE), help="Queue JSON")
    parser.add_argument("--tier", type=str, default=None, help="Filter by tier")
    parser.add_argument(
        "--mode", choices=["tabs", "step", "generate"], default="tabs",
        help="Automation mode (default: tabs)"
    )
    parser.add_argument(
        "--browser", choices=["chrome", "safari"], default="chrome",
        help="Browser to control (default: chrome)"
    )
    parser.add_argument("--output", type=str, default=None, help="Output .scpt file path")
    parser.add_argument("--dry-run", action="store_true", help="No browser actions")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point."""
    args = build_parser().parse_args(argv)
    domains = load_domains(args)

    if not domains:
        print("No domains matched the filters.")
        return 0

    print(f"\nDropCatch AppleScript — {len(domains)} domain(s), mode={args.mode}")

    if args.mode == "tabs":
        return mode_tabs(domains, args.browser, args.dry_run)
    elif args.mode == "step":
        return mode_step(domains, args.browser, args.dry_run)
    elif args.mode == "generate":
        return mode_generate(domains, args.browser, args.output)
    else:
        print(f"Unknown mode: {args.mode}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
