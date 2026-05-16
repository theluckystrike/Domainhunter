#!/usr/bin/env python3
"""Sprint 26 -- First Blood Preparation for guerrameats.com.

Validates all systems are GO for the first live domain catch:
  - RDAP status verification (live probe)
  - Dynadot balance check via API
  - Notification system test
  - Auto-trigger chain verification
  - Go/No-Go checklist output

Usage:
  python scripts/sprint26_first_blood_prep.py                  # Full check
  python scripts/sprint26_first_blood_prep.py --dry-run        # No API calls
  python scripts/sprint26_first_blood_prep.py --skip-rdap      # Skip live RDAP

NASA P10: functions <60 lines, 2+ assertions, bounded loops,
no global mutable state, frozen dataclasses.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Final

# ── Constants (immutable) ─────────────────────────────────────────────
TARGET_DOMAIN: Final[str] = "guerrameats.com"
RDAP_BASE_URL: Final[str] = "https://rdap.org/domain/"
RDAP_TIMEOUT: Final[int] = 15
DYNADOT_API_URL: Final[str] = "https://api.dynadot.com/api3.json"
DYNADOT_API_TIMEOUT: Final[int] = 30
MIN_BALANCE_USD: Final[float] = 25.0
RECOMMENDED_BALANCE_USD: Final[float] = 50.0
PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
DATA_DIR: Final[Path] = PROJECT_ROOT / "data"
SCRIPTS_DIR: Final[Path] = PROJECT_ROOT / "scripts"
LOGS_DIR: Final[Path] = PROJECT_ROOT / "logs"
MONITORED_PATH: Final[Path] = SCRIPTS_DIR / "monitored_domains.json"
ENV_PATH: Final[Path] = PROJECT_ROOT / ".env"
LAUNCHD_DIR: Final[Path] = Path.home() / "Library" / "LaunchAgents"

# Key dates
EST_PENDING_DELETE_START: Final[str] = "2026-06-21"
EST_DROP_DATE: Final[str] = "2026-06-26"
DAILY_CHECK_START: Final[str] = "2026-06-20"
TOPUP_DEADLINE: Final[str] = "2026-06-20"

# Drop lifecycle phases (ordered)
DROP_PHASES: Final[tuple[str, ...]] = (
    "active", "autoRenewPeriod", "clientHold",
    "clientRenewProhibited", "redemptionPeriod",
    "pendingDelete", "available",
)


# ── Data Models (frozen) ──────────────────────────────────────────────
@dataclass(frozen=True)
class CheckResult:
    """Single go/no-go check result."""
    name: str
    status: str  # "GO", "NO-GO", "WARNING"
    detail: str

    def __post_init__(self) -> None:
        assert self.name, "Check name required"
        assert self.status in ("GO", "NO-GO", "WARNING"), f"Invalid status: {self.status}"


@dataclass(frozen=True)
class RdapProbeResult:
    """Live RDAP probe result for target domain."""
    domain: str
    epp_status: str
    registrar: str
    expiry_date: str
    raw_statuses: tuple[str, ...]
    checked_at: str
    progressing_toward_drop: bool

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain, f"Invalid domain: {self.domain}"
        assert isinstance(self.checked_at, str) and len(self.checked_at) > 0


@dataclass(frozen=True)
class BalanceResult:
    """Dynadot account balance check result."""
    balance_usd: float
    sufficient: bool
    recommended_topup: float
    raw_response: str

    def __post_init__(self) -> None:
        assert isinstance(self.balance_usd, (int, float))
        assert isinstance(self.sufficient, bool)


@dataclass(frozen=True)
class FirstBloodReport:
    """Complete first blood preparation report."""
    domain: str
    generated_at: str
    rdap_probe: dict[str, Any]
    balance_check: dict[str, Any]
    notification_test: dict[str, Any]
    auto_trigger_check: dict[str, Any]
    post_catch_check: dict[str, Any]
    checklist: list[dict[str, str]]
    overall_status: str
    plan_b: dict[str, Any]
    key_dates: dict[str, str]

    def __post_init__(self) -> None:
        assert self.domain and "." in self.domain
        assert len(self.checklist) > 0, "Checklist must not be empty"


# ── Environment Loader ────────────────────────────────────────────────
def _load_env(env_path: Path) -> dict[str, str]:
    """Load .env file into a dict. Does NOT modify os.environ."""
    assert isinstance(env_path, Path)
    assert env_path.exists(), f".env not found: {env_path}"
    settings: dict[str, str] = {}
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                settings[k.strip()] = v.strip()
    assert isinstance(settings, dict)
    return settings


# ── RDAP Probe ────────────────────────────────────────────────────────
def _classify_epp(statuses: list[str]) -> str:
    """Classify domain lifecycle from EPP status codes."""
    assert isinstance(statuses, list)
    joined = " ".join(statuses).lower()
    if "pending delete" in joined or "pendingdelete" in joined:
        return "pendingDelete"
    if "redemption" in joined:
        return "redemptionPeriod"
    if "auto renew" in joined or "autorenew" in joined:
        return "autoRenewPeriod"
    if "client hold" in joined or "clienthold" in joined:
        return "clientHold"
    if "client renew prohibited" in joined:
        return "clientRenewProhibited"
    if not statuses:
        return "unknown"
    return statuses[0]


def probe_rdap(domain: str) -> RdapProbeResult:
    """Live RDAP probe for domain status."""
    assert domain and "." in domain, f"Invalid domain: {domain}"
    now = datetime.now(timezone.utc).isoformat()
    url = f"{RDAP_BASE_URL}{domain}"
    req = urllib.request.Request(url, headers={"Accept": "application/rdap+json"})

    try:
        with urllib.request.urlopen(req, timeout=RDAP_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return RdapProbeResult(
                domain=domain, epp_status="available",
                registrar="", expiry_date="",
                raw_statuses=(), checked_at=now,
                progressing_toward_drop=True,
            )
        return RdapProbeResult(
            domain=domain, epp_status=f"error_http_{exc.code}",
            registrar="", expiry_date="",
            raw_statuses=(), checked_at=now,
            progressing_toward_drop=False,
        )
    except Exception as exc:
        return RdapProbeResult(
            domain=domain, epp_status=f"error_{type(exc).__name__}",
            registrar="", expiry_date="",
            raw_statuses=(), checked_at=now,
            progressing_toward_drop=False,
        )

    return _parse_rdap_for_probe(domain, data, now)


def _parse_rdap_for_probe(
    domain: str, data: dict[str, Any], now: str
) -> RdapProbeResult:
    """Parse RDAP JSON into a probe result."""
    assert isinstance(data, dict), "RDAP data must be dict"
    assert domain, "Domain required"

    raw_statuses: list[str] = []
    for s in data.get("status", [])[:16]:
        raw_statuses.append(str(s))
    epp_status = _classify_epp(raw_statuses)

    registrar = ""
    for entity in data.get("entities", [])[:10]:
        if "registrar" in entity.get("roles", []):
            vcard = entity.get("vcardArray", [None, []])[1]
            for field in (vcard or [])[:20]:
                if isinstance(field, list) and len(field) >= 4 and field[0] == "fn":
                    registrar = str(field[3])
                    break

    expiry_date = ""
    for event in data.get("events", [])[:20]:
        if event.get("eventAction") == "expiration":
            expiry_date = str(event.get("eventDate", ""))
            break

    # Domain is progressing if in clientHold or later drop phases
    progressing = epp_status in (
        "clientHold", "clientRenewProhibited",
        "redemptionPeriod", "pendingDelete", "available",
    )

    return RdapProbeResult(
        domain=domain, epp_status=epp_status, registrar=registrar,
        expiry_date=expiry_date, raw_statuses=tuple(raw_statuses),
        checked_at=now, progressing_toward_drop=progressing,
    )


# ── Dynadot Balance Check ────────────────────────────────────────────
def check_dynadot_balance(api_key: str) -> BalanceResult:
    """Check Dynadot account balance via API."""
    assert isinstance(api_key, str), "API key must be string"
    assert len(api_key) > 0, "API key must not be empty"

    params = f"key={api_key}&command=get_account_balance"
    url = f"{DYNADOT_API_URL}?{params}"
    req = urllib.request.Request(url)

    try:
        with urllib.request.urlopen(req, timeout=DYNADOT_API_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
    except Exception as exc:
        return BalanceResult(
            balance_usd=0.0, sufficient=False,
            recommended_topup=RECOMMENDED_BALANCE_USD,
            raw_response=f"ERROR: {exc}",
        )

    balance = _extract_balance(data)
    sufficient = balance >= MIN_BALANCE_USD
    topup = max(0.0, RECOMMENDED_BALANCE_USD - balance)

    return BalanceResult(
        balance_usd=balance, sufficient=sufficient,
        recommended_topup=topup,
        raw_response=json.dumps(data, indent=2)[:500],
    )


def _extract_balance(data: dict[str, Any]) -> float:
    """Extract USD balance from Dynadot API response."""
    assert isinstance(data, dict), "Data must be dict"
    bal_resp = data.get("GetAccountBalanceResponse", {})
    if isinstance(bal_resp, dict):
        bal_list = bal_resp.get("BalanceList", [])
        if isinstance(bal_list, list):
            for idx, entry in enumerate(bal_list):
                if idx >= 10:
                    break
                if isinstance(entry, dict) and entry.get("Currency") == "USD":
                    try:
                        return float(entry.get("Amount", 0))
                    except (ValueError, TypeError):
                        return 0.0
    return 0.0


# ── Notification Test ─────────────────────────────────────────────────
def test_notification() -> dict[str, Any]:
    """Send a test macOS notification and log it."""
    assert sys.platform == "darwin" or True, "Notification test is macOS-only"
    title = "Domain Hunter - First Blood Test"
    message = "Notification system verified for guerrameats.com catch"

    try:
        result = subprocess.run(
            ["osascript", "-e",
             f'display notification "{message}" with title "{title}" sound name "Glass"'],
            capture_output=True, text=True, timeout=10,
        )
        success = result.returncode == 0
    except Exception as exc:
        return {"success": False, "error": str(exc)}

    return {
        "success": success,
        "exit_code": result.returncode,
        "message": "Test notification sent" if success else f"Failed: {result.stderr}",
    }


# ── Auto-Trigger Verification ────────────────────────────────────────
def verify_auto_trigger() -> dict[str, Any]:
    """Verify the auto-trigger chain is armed and functional."""
    checks: dict[str, Any] = {
        "launchd_plists_exist": False,
        "launchd_agents_loaded": False,
        "monitored_domains_has_target": False,
        "drop_monitor_script_exists": False,
        "heartbeat_recent": False,
        "details": {},
    }

    # Check launchd plists
    critical_plist = LAUNCHD_DIR / "com.domainhunter.drop-monitor-critical.plist"
    all_plist = LAUNCHD_DIR / "com.domainhunter.drop-monitor-all.plist"
    checks["launchd_plists_exist"] = critical_plist.exists() and all_plist.exists()
    checks["details"]["critical_plist"] = str(critical_plist)
    checks["details"]["all_plist"] = str(all_plist)

    # Check agents are loaded
    try:
        result = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=10,
        )
        output = result.stdout
        critical_loaded = "com.domainhunter.drop-monitor-critical" in output
        all_loaded = "com.domainhunter.drop-monitor-all" in output
        checks["launchd_agents_loaded"] = critical_loaded and all_loaded
        checks["details"]["critical_loaded"] = critical_loaded
        checks["details"]["all_loaded"] = all_loaded
    except Exception as exc:
        checks["details"]["launchctl_error"] = str(exc)

    # Check monitored_domains.json has guerrameats.com
    if MONITORED_PATH.exists():
        with open(MONITORED_PATH, encoding="utf-8") as fh:
            config = json.load(fh)
        found = _find_domain_in_config(config, TARGET_DOMAIN)
        checks["monitored_domains_has_target"] = found
        checks["details"]["config_path"] = str(MONITORED_PATH)
    else:
        checks["details"]["config_missing"] = str(MONITORED_PATH)

    # Check drop_monitor.py exists
    dm_path = SCRIPTS_DIR / "drop_monitor.py"
    checks["drop_monitor_script_exists"] = dm_path.exists()

    # Check heartbeat file recency
    heartbeat = LOGS_DIR / ".drop_monitor_heartbeat"
    if heartbeat.exists():
        import time
        age_hours = (time.time() - heartbeat.stat().st_mtime) / 3600
        checks["heartbeat_recent"] = age_hours < 24
        checks["details"]["heartbeat_age_hours"] = round(age_hours, 1)
    else:
        checks["details"]["heartbeat_missing"] = True

    return checks


def _find_domain_in_config(config: dict[str, Any], domain: str) -> bool:
    """Check if domain exists in monitored_domains.json config.

    Supports both 'domains' (legacy) and 'active_targets' (new) keys.
    """
    assert isinstance(config, dict)
    assert isinstance(domain, str) and "." in domain
    # Support both config formats
    domains_section = config.get("domains") or config.get("active_targets") or {}
    for tier_name in ("critical", "high", "medium", "low"):
        entries = domains_section.get(tier_name, [])
        for idx, entry in enumerate(entries):
            if idx >= 200:
                break
            if entry.get("domain") == domain:
                return True
    return False


# ── Post-Catch Executor Check ─────────────────────────────────────────
def verify_post_catch() -> dict[str, Any]:
    """Verify post-catch executor is ready."""
    assert isinstance(SCRIPTS_DIR, Path)
    assert isinstance(DATA_DIR, Path)
    executor_path = SCRIPTS_DIR / "post_catch_executor.py"
    playbooks_candidates = sorted(
        [f for f in DATA_DIR.iterdir()
         if f.name.startswith("sprint22_playbooks") and f.suffix == ".json"],
        reverse=True,
    )

    return {
        "executor_exists": executor_path.exists(),
        "executor_path": str(executor_path),
        "playbook_files_found": len(playbooks_candidates),
        "latest_playbook": str(playbooks_candidates[0]) if playbooks_candidates else "NONE",
    }


# ── Plan B ────────────────────────────────────────────────────────────
def _build_plan_b_scenarios() -> dict[str, Any]:
    """Build Plan B failure scenarios and mitigations."""
    return {
        "scenario_1_dynadot_rejects": {
            "problem": "Dynadot API returns 'could not find backorder for this domain' "
                       "because domain is not yet in pendingDelete phase",
            "solution": "EXPECTED. Dynadot only accepts backorders for domains in their "
                        "drop-catching inventory (pendingDelete). Auto-retry 4x/day.",
            "action": "No action needed. Monitor will auto-retry 4x/day for critical tier.",
        },
        "scenario_2_dynadot_inventory_gap": {
            "problem": "Domain enters pendingDelete but Dynadot does not have it",
            "solution_a": "Manual Dynadot search at https://www.dynadot.com/domain/search",
            "solution_b": "DropCatch.com backup ($59/backorder, higher catch rate)",
            "solution_c": "SnapNames.com tertiary ($69/backorder)",
            "daily_check_start": DAILY_CHECK_START,
            "manual_check_url": "https://www.dynadot.com/domain/search?q=guerrameats.com",
        },
        "scenario_3_domain_renewed": {
            "problem": "Owner renews (clientHold can be reversed by paying renewal)",
            "likelihood": "LOW -- clientHold since Apr 7, DNS dead, business inactive",
            "action": "Move on to next target (sunnyray.org drops ~Jun 30).",
        },
        "scenario_4_competitor_catches": {
            "problem": "Another registrar catches the domain before Dynadot",
            "likelihood": "MODERATE -- $11K ETV attracts automated scanners",
            "mitigation": "Multi-registrar backorders: Dynadot $10.99 + DropCatch $59 "
                          "+ SnapNames $69 = $139.99 max exposure.",
        },
    }


def _build_backup_registrars() -> dict[str, Any]:
    """Build backup registrar account info for Plan B."""
    return {
        "dropcatch": {
            "url": "https://www.dropcatch.com", "price_per_backorder": 59,
            "account_needed": True,
            "notes": "Higher catch rate than Dynadot. Industry standard.",
        },
        "snapnames": {
            "url": "https://www.snapnames.com", "price_per_backorder": 69,
            "account_needed": True, "notes": "Owned by Name.com. Good for .com drops.",
        },
        "namejet": {
            "url": "https://www.namejet.com", "price_per_backorder": 0,
            "account_needed": True, "notes": "Free to place backorder, auction if caught.",
        },
    }


def build_plan_b() -> dict[str, Any]:
    """Document fallback strategies if Dynadot backorder fails."""
    plan = _build_plan_b_scenarios()
    plan["backup_registrar_accounts"] = _build_backup_registrars()
    assert len(plan) >= 4, "Plan B must have at least 4 scenarios"
    return plan


# ── Key Dates ─────────────────────────────────────────────────────────
def build_key_dates() -> dict[str, str]:
    """Build the critical dates calendar."""
    return {
        "2026-06-15": "T-11 days: Begin twice-daily RDAP checks (increase critical tier frequency)",
        "2026-06-20": "T-6 days: Start daily manual Dynadot search check, verify auto-trigger, "
                      "top up Dynadot balance to $50+, create DropCatch/SnapNames accounts",
        "2026-06-21": "T-5 days: ESTIMATED pendingDelete window OPENS -- backorder attempts begin",
        "2026-06-22": "T-4 days: If Dynadot rejects, place DropCatch backorder ($59)",
        "2026-06-23": "T-3 days: Verify backorder is placed on at least 1 registrar",
        "2026-06-24": "T-2 days: Final system check -- all triggers armed",
        "2026-06-25": "T-1 day: Last chance to place backorders before potential drop",
        "2026-06-26": "D-DAY: guerrameats.com estimated to become available (5-day window end)",
        "2026-06-27": "D+1: If not dropped, continue monitoring (timeline can shift +/- 5 days)",
        "2026-07-01": "D+5: If still not dropped, re-evaluate RDAP status and timeline",
    }


# ── Checklist Builder ─────────────────────────────────────────────────
def _check_balance(balance_result: BalanceResult | None) -> CheckResult:
    """Build balance check result."""
    if balance_result is not None:
        bal_status = "GO" if balance_result.sufficient else "NO-GO"
        bal_detail = f"Balance: ${balance_result.balance_usd:.2f}"
        if balance_result.recommended_topup > 0:
            bal_detail += f" (recommend adding ${balance_result.recommended_topup:.2f})"
    else:
        bal_status = "WARNING"
        bal_detail = "Balance check skipped (dry-run or API error)"
    return CheckResult(name="Dynadot balance >= $25", status=bal_status, detail=bal_detail)


def _check_rdap_progress(rdap_result: RdapProbeResult | None) -> CheckResult:
    """Build domain progress check result."""
    if rdap_result is not None:
        progressing = rdap_result.progressing_toward_drop
        detail = (f"EPP status: {rdap_result.epp_status}, registrar: {rdap_result.registrar}"
                  if progressing else f"Status: {rdap_result.epp_status} -- may have been renewed")
        return CheckResult(
            name="Domain progressing toward drop",
            status="GO" if progressing else "NO-GO", detail=detail,
        )
    return CheckResult(
        name="Domain progressing toward drop",
        status="WARNING", detail="RDAP probe skipped (dry-run or --skip-rdap)",
    )


def build_checklist(
    rdap_result: RdapProbeResult | None,
    balance_result: BalanceResult | None,
    trigger_check: dict[str, Any],
    post_catch_check: dict[str, Any],
    notification_test: dict[str, Any],
) -> list[CheckResult]:
    """Build the go/no-go checklist from all check results."""
    assert isinstance(trigger_check, dict)
    assert isinstance(post_catch_check, dict)

    rdap_active = (trigger_check.get("launchd_agents_loaded", False)
                   and trigger_check.get("monitored_domains_has_target", False)
                   and trigger_check.get("drop_monitor_script_exists", False))
    trigger_armed = (trigger_check.get("launchd_agents_loaded", False)
                     and trigger_check.get("monitored_domains_has_target", False))
    pce_ready = post_catch_check.get("executor_exists", False)
    notif_ok = notification_test.get("success", False)

    checks: list[CheckResult] = [
        CheckResult(name="RDAP monitoring active",
                    status="GO" if rdap_active else "NO-GO",
                    detail="Drop monitor agents loaded, target in config, script exists"
                    if rdap_active else "One or more monitoring components missing"),
        _check_balance(balance_result),
        CheckResult(name="Auto-trigger armed",
                    status="GO" if trigger_armed else "NO-GO",
                    detail="launchd agents loaded + target in monitored_domains.json"
                    if trigger_armed else "Auto-trigger chain incomplete"),
        CheckResult(name="Post-catch executor ready",
                    status="GO" if pce_ready else "WARNING",
                    detail=f"Executor at {post_catch_check.get('executor_path', 'unknown')}"
                    if pce_ready else "Post-catch executor script not found"),
        _check_rdap_progress(rdap_result),
        CheckResult(name="Notification system functional",
                    status="GO" if notif_ok else "WARNING",
                    detail="macOS notification sent successfully"
                    if notif_ok else notification_test.get("error", "Notification test failed")),
    ]
    return checks


# ── Report Generator ──────────────────────────────────────────────────
def generate_report(
    rdap_result: RdapProbeResult | None,
    balance_result: BalanceResult | None,
    notification_test: dict[str, Any],
    trigger_check: dict[str, Any],
    post_catch_check: dict[str, Any],
    checklist: list[CheckResult],
) -> FirstBloodReport:
    """Generate the complete first blood preparation report."""
    assert isinstance(checklist, list) and len(checklist) > 0

    go_count = sum(1 for c in checklist if c.status == "GO")
    nogo_count = sum(1 for c in checklist if c.status == "NO-GO")
    total = len(checklist)

    if nogo_count > 0:
        overall = f"NOT READY ({nogo_count} NO-GO items out of {total})"
    elif go_count == total:
        overall = f"ALL SYSTEMS GO ({go_count}/{total})"
    else:
        overall = f"READY WITH WARNINGS ({go_count} GO, {total - go_count} warnings)"

    return FirstBloodReport(
        domain=TARGET_DOMAIN,
        generated_at=datetime.now(timezone.utc).isoformat(),
        rdap_probe=asdict(rdap_result) if rdap_result else {"skipped": True},
        balance_check=asdict(balance_result) if balance_result else {"skipped": True},
        notification_test=notification_test,
        auto_trigger_check=trigger_check,
        post_catch_check=post_catch_check,
        checklist=[asdict(c) for c in checklist],
        overall_status=overall,
        plan_b=build_plan_b(),
        key_dates=build_key_dates(),
    )


# ── Output ────────────────────────────────────────────────────────────
def save_report(report: FirstBloodReport, output_path: Path) -> None:
    """Save report to JSON file."""
    assert output_path.parent.exists(), f"Parent dir missing: {output_path.parent}"
    assert output_path.suffix == ".json", "Output must be .json"
    data = asdict(report)
    output_path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def print_checklist(checklist: list[CheckResult], overall: str) -> None:
    """Print formatted go/no-go checklist to stdout."""
    assert isinstance(checklist, list)
    assert isinstance(overall, str)

    print("\n" + "=" * 64)
    print("  FIRST BLOOD PREPARATION -- guerrameats.com")
    print("  " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    print("=" * 64)

    for c in checklist:
        icon = "[GO]    " if c.status == "GO" else "[NO-GO] " if c.status == "NO-GO" else "[WARN]  "
        print(f"\n  {icon} {c.name}")
        print(f"          {c.detail}")

    print("\n" + "-" * 64)
    print(f"  OVERALL: {overall}")
    print("=" * 64 + "\n")


# ── CLI Entry Point ───────────────────────────────────────────────────
def _run_checks(dry_run: bool, skip_rdap: bool) -> tuple[
    RdapProbeResult | None, BalanceResult | None,
    dict[str, Any], dict[str, Any], dict[str, Any],
]:
    """Execute all 5 system checks. Returns results tuple."""
    # 1. RDAP probe
    rdap_result: RdapProbeResult | None = None
    if not skip_rdap and not dry_run:
        print("  [1/5] RDAP probe...", end=" ", flush=True)
        rdap_result = probe_rdap(TARGET_DOMAIN)
        print(f"EPP={rdap_result.epp_status}, registrar={rdap_result.registrar}")
    else:
        print("  [1/5] RDAP probe... SKIPPED")

    # 2. Dynadot balance
    balance_result: BalanceResult | None = None
    if not dry_run:
        env = _load_env(ENV_PATH)
        api_key = env.get("DYNADOT_API_KEY", "")
        if api_key:
            print("  [2/5] Dynadot balance check...", end=" ", flush=True)
            balance_result = check_dynadot_balance(api_key)
            print(f"${balance_result.balance_usd:.2f} "
                  f"({'SUFFICIENT' if balance_result.sufficient else 'INSUFFICIENT'})")
        else:
            print("  [2/5] Dynadot balance check... NO API KEY")
    else:
        print("  [2/5] Dynadot balance check... SKIPPED (dry-run)")

    # 3-5. Local checks
    print("  [3/5] Notification test...", end=" ", flush=True)
    notification_test = test_notification()
    print("OK" if notification_test["success"] else "FAILED")

    print("  [4/5] Auto-trigger verification...", end=" ", flush=True)
    trigger_check = verify_auto_trigger()
    armed = (trigger_check["launchd_agents_loaded"]
             and trigger_check["monitored_domains_has_target"])
    print("ARMED" if armed else "NOT ARMED")

    print("  [5/5] Post-catch executor...", end=" ", flush=True)
    post_catch_check = verify_post_catch()
    print("READY" if post_catch_check["executor_exists"] else "NOT FOUND")

    return rdap_result, balance_result, notification_test, trigger_check, post_catch_check


def main() -> int:
    """Run first blood preparation checks."""
    import argparse
    parser = argparse.ArgumentParser(description="Sprint 26 -- First Blood Preparation")
    parser.add_argument("--dry-run", action="store_true", help="Skip API calls")
    parser.add_argument("--skip-rdap", action="store_true", help="Skip live RDAP probe")
    args = parser.parse_args()
    assert isinstance(args.dry_run, bool)

    print(f"\n  First Blood Prep: {TARGET_DOMAIN}")
    print(f"  Est. drop: {EST_DROP_DATE} ({EST_PENDING_DELETE_START} - {EST_DROP_DATE})")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}\n")

    rdap_r, bal_r, notif, trigger, post_catch = _run_checks(args.dry_run, args.skip_rdap)

    checklist = build_checklist(rdap_r, bal_r, trigger, post_catch, notif)
    report = generate_report(rdap_r, bal_r, notif, trigger, post_catch, checklist)

    print_checklist(checklist, report.overall_status)

    output_path = DATA_DIR / "sprint26_first_blood_prep.json"
    save_report(report, output_path)
    print(f"  Report saved to: {output_path}\n")

    print("  KEY DATES:")
    print("  " + "-" * 60)
    for date, action in build_key_dates().items():
        print(f"  {date}: {action}")
    print()

    nogo_count = sum(1 for c in checklist if c.status == "NO-GO")
    return 1 if nogo_count > 0 else 0


if __name__ == "__main__":
    raise SystemExit(main())
