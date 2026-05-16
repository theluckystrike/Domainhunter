"""Automated domain acquisition offer system.

NASA Power of 10 compliant:
- All functions < 60 lines
- Min 2 assertions per function
- Fixed loop bounds
- No global mutable state
- Frozen dataclasses
"""
from __future__ import annotations

import csv
import logging
import smtplib
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Final

# ---------------------------------------------------------------------------
# Constants — no global mutable state
# ---------------------------------------------------------------------------
MAX_OFFERS: Final[int] = 100
MAX_FOLLOWUPS: Final[int] = 1
MAX_CSV_ROWS: Final[int] = 500
VALID_STATUSES: Final[tuple[str, ...]] = (
    "draft", "sent", "responded", "countered", "accepted", "completed",
)
VALID_METHODS: Final[tuple[str, ...]] = (
    "afternic", "dynadot", "whois", "dan", "sedo", "direct",
)
DB_FILENAME: Final[str] = "domain_offers.db"

logger: Final[logging.Logger] = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DomainOffer:
    """Immutable offer target loaded from CSV or database."""

    domain: str
    method: str
    offer_amount: int
    max_amount: int
    notes: str = ""


@dataclass(frozen=True)
class OfferResult:
    """Immutable result of an offer action."""

    domain: str
    action: str
    success: bool
    message: str
    dry_run: bool


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
_CREATE_TABLE_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS domain_offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    method TEXT NOT NULL,
    offer_amount INTEGER,
    max_amount INTEGER,
    sent_at TEXT,
    followup_at TEXT,
    status TEXT DEFAULT 'draft',
    response TEXT,
    counter_amount INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_CREATE_INDEX_SQL: Final[str] = """
CREATE INDEX IF NOT EXISTS idx_domain_offers_domain ON domain_offers(domain);
"""


# ---------------------------------------------------------------------------
# Database functions
# ---------------------------------------------------------------------------
def init_database(db_path: Path) -> sqlite3.Connection:
    """Initialize SQLite database with offer tracking schema."""
    assert isinstance(db_path, Path), f"db_path must be Path, got {type(db_path)}"
    assert db_path.suffix == ".db", f"db_path must end with .db, got {db_path.suffix}"

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(_CREATE_TABLE_SQL)
    cursor.execute(_CREATE_INDEX_SQL)
    conn.commit()

    # Verify table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='domain_offers'"
    )
    result = cursor.fetchone()
    assert result is not None, "domain_offers table was not created"

    return conn


def insert_offer(conn: sqlite3.Connection, offer: DomainOffer) -> int:
    """Insert a new offer record and return the row ID."""
    assert isinstance(offer, DomainOffer), f"offer must be DomainOffer, got {type(offer)}"
    assert offer.offer_amount > 0, f"offer_amount must be positive, got {offer.offer_amount}"

    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO domain_offers (domain, method, offer_amount, max_amount, status)
           VALUES (?, ?, ?, ?, 'draft')""",
        (offer.domain, offer.method, offer.offer_amount, offer.max_amount),
    )
    conn.commit()
    row_id = cursor.lastrowid
    assert row_id is not None and row_id > 0, "INSERT failed: no row ID returned"
    return row_id


def update_status(
    conn: sqlite3.Connection, domain: str, new_status: str,
) -> bool:
    """Update the status of an offer. Returns True if updated."""
    assert new_status in VALID_STATUSES, f"Invalid status: {new_status}"
    assert isinstance(domain, str) and len(domain) > 0, "domain must be non-empty string"

    cursor = conn.cursor()
    cursor.execute(
        "UPDATE domain_offers SET status = ? WHERE domain = ?",
        (new_status, domain),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_offer(conn: sqlite3.Connection, domain: str) -> sqlite3.Row | None:
    """Retrieve the latest offer for a domain."""
    assert isinstance(domain, str) and len(domain) > 0, "domain must be non-empty"
    assert conn is not None, "connection must not be None"

    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM domain_offers WHERE domain = ? ORDER BY id DESC LIMIT 1",
        (domain,),
    )
    return cursor.fetchone()


def get_followup_count(conn: sqlite3.Connection, domain: str) -> int:
    """Count follow-ups sent for a domain."""
    assert isinstance(domain, str) and len(domain) > 0, "domain must be non-empty"
    assert conn is not None, "connection must not be None"

    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM domain_offers WHERE domain = ? AND followup_at IS NOT NULL",
        (domain,),
    )
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def record_followup(conn: sqlite3.Connection, domain: str) -> bool:
    """Record a follow-up timestamp. Enforces MAX_FOLLOWUPS limit."""
    assert isinstance(domain, str) and len(domain) > 0, "domain must be non-empty"
    assert conn is not None, "connection must not be None"

    current_count = get_followup_count(conn, domain)
    if current_count >= MAX_FOLLOWUPS:
        logger.warning("Max follow-ups (%d) reached for %s", MAX_FOLLOWUPS, domain)
        return False

    now_str = datetime.now(tz=timezone.utc).isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE domain_offers SET followup_at = ? WHERE domain = ? AND followup_at IS NULL",
        (now_str, domain),
    )
    conn.commit()
    return cursor.rowcount > 0


def record_sent(conn: sqlite3.Connection, domain: str) -> bool:
    """Record that an offer was sent."""
    assert isinstance(domain, str) and len(domain) > 0, "domain must be non-empty"
    assert conn is not None, "connection must not be None"

    now_str = datetime.now(tz=timezone.utc).isoformat()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE domain_offers SET sent_at = ?, status = 'sent' WHERE domain = ?",
        (now_str, domain),
    )
    conn.commit()
    return cursor.rowcount > 0


def get_all_offers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Retrieve all offers, bounded by MAX_OFFERS."""
    assert conn is not None, "connection must not be None"

    cursor = conn.cursor()
    cursor.execute(
        f"SELECT * FROM domain_offers ORDER BY id ASC LIMIT {MAX_OFFERS}"
    )
    rows = cursor.fetchall()
    assert len(rows) <= MAX_OFFERS, f"Row count exceeds MAX_OFFERS: {len(rows)}"
    return rows


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------
def load_offer_targets(csv_path: Path) -> list[DomainOffer]:
    """Load offer targets from CSV file."""
    assert isinstance(csv_path, Path), f"csv_path must be Path, got {type(csv_path)}"
    assert csv_path.is_file(), f"CSV file not found: {csv_path}"

    offers: list[DomainOffer] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= MAX_CSV_ROWS:
                logger.warning("CSV row limit (%d) reached", MAX_CSV_ROWS)
                break
            offer = DomainOffer(
                domain=row["domain"].strip(),
                method=row["method"].strip(),
                offer_amount=int(row["offer_usd"]),
                max_amount=int(row["max_usd"]),
                notes=row.get("notes", "").strip(),
            )
            offers.append(offer)

    assert len(offers) <= MAX_CSV_ROWS, f"Too many offers: {len(offers)}"
    return offers


# ---------------------------------------------------------------------------
# WHOIS email extraction
# ---------------------------------------------------------------------------
def extract_whois_email(domain: str) -> str | None:
    """Extract registrant/admin email from WHOIS data via CLI."""
    assert isinstance(domain, str) and len(domain) > 0, "domain must be non-empty"
    assert "." in domain, f"Invalid domain format: {domain}"

    try:
        result = subprocess.run(
            ["whois", domain],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            logger.warning("WHOIS lookup failed for %s: %s", domain, result.stderr)
            return None

        output = result.stdout
        for line in output.splitlines():
            line_lower = line.lower()
            if any(
                key in line_lower
                for key in ("registrant email", "admin email", "tech email")
            ):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    email = parts[1].strip()
                    if "@" in email and "." in email:
                        return email

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        logger.error("WHOIS error for %s: %s", domain, exc)

    return None


# ---------------------------------------------------------------------------
# Offer template generation
# ---------------------------------------------------------------------------
def generate_offer_email(offer: DomainOffer, sender_email: str) -> dict[str, str]:
    """Generate a professional low-ball acquisition offer email."""
    assert isinstance(offer, DomainOffer), f"offer must be DomainOffer, got {type(offer)}"
    assert "@" in sender_email, f"Invalid sender email: {sender_email}"

    subject = f"Inquiry regarding {offer.domain}"
    body = f"""Hello,

I'm reaching out regarding the domain {offer.domain}. I'm a developer building
tools for the software development community and this domain aligns well with
a project I'm working on.

I'd like to make an offer of ${offer.offer_amount:,} USD for the domain.

I understand this may be below your expectations, but I'm a solo developer
with a limited budget. I'm happy to handle all transfer logistics and can
complete the transaction quickly through a mutually agreeable escrow service.

If you're open to discussing this, I'd love to hear from you.

Best regards,
Mike

---
This message was sent by a real person regarding a legitimate domain inquiry.
If you do not wish to receive further messages about this domain, simply reply
with "unsubscribe" and you will not be contacted again.
Physical address available upon request as required by CAN-SPAM Act.
Sender: {sender_email}"""

    return {"subject": subject, "body": body, "sender": sender_email}


def generate_followup_email(offer: DomainOffer, sender_email: str) -> dict[str, str]:
    """Generate a follow-up email for a previously sent offer."""
    assert isinstance(offer, DomainOffer), f"offer must be DomainOffer, got {type(offer)}"
    assert "@" in sender_email, f"Invalid sender email: {sender_email}"

    subject = f"Following up: {offer.domain}"
    body = f"""Hello,

I wanted to follow up on my previous inquiry about {offer.domain}.

I remain interested in acquiring this domain at ${offer.offer_amount:,} USD
and am flexible on timing and transfer method.

If you've had a chance to consider, I'd appreciate hearing back. If the
domain is not for sale, no worries at all -- just let me know and I won't
follow up again.

Best regards,
Mike

---
If you do not wish to receive further messages, reply "unsubscribe."
Physical address available upon request (CAN-SPAM Act compliance).
Sender: {sender_email}"""

    return {"subject": subject, "body": body, "sender": sender_email}


def generate_counter_response(
    offer: DomainOffer, counter_amount: int, sender_email: str,
) -> dict[str, str]:
    """Generate a response to a counter-offer."""
    assert isinstance(offer, DomainOffer), f"offer must be DomainOffer, got {type(offer)}"
    assert counter_amount > 0, f"counter_amount must be positive, got {counter_amount}"

    if counter_amount <= offer.max_amount:
        action = "accept"
        body_text = (
            f"Thank you for your response. I'd like to accept your price of "
            f"${counter_amount:,} USD for {offer.domain}. Please let me know "
            f"your preferred escrow service and transfer process."
        )
    else:
        midpoint = (offer.offer_amount + offer.max_amount) // 2
        action = "counter"
        body_text = (
            f"Thank you for your response regarding {offer.domain}. "
            f"Unfortunately ${counter_amount:,} is above my budget. "
            f"Would you consider ${midpoint:,} USD? I can complete the "
            f"transaction quickly through escrow."
        )

    subject = f"Re: {offer.domain}"
    body = f"""Hello,

{body_text}

Best regards,
Mike

---
Sender: {sender_email}"""

    return {"subject": subject, "body": body, "action": action, "sender": sender_email}


# ---------------------------------------------------------------------------
# Email sending (dry-run default)
# ---------------------------------------------------------------------------
def send_offer_email(
    email_data: dict[str, str],
    recipient: str,
    *,
    dry_run: bool = True,
    smtp_host: str = "",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_pass: str = "",
) -> OfferResult:
    """Send an offer email. Dry-run mode by default."""
    assert isinstance(email_data, dict), "email_data must be a dict"
    assert "subject" in email_data and "body" in email_data, "email_data needs subject and body"

    domain = email_data.get("subject", "").split()[-1] if email_data.get("subject") else "unknown"

    if dry_run:
        logger.info("[DRY RUN] Would send to %s: %s", recipient, email_data["subject"])
        return OfferResult(
            domain=domain, action="send_email",
            success=True, message=f"DRY RUN: email to {recipient}", dry_run=True,
        )

    if not all([smtp_host, smtp_user, smtp_pass]):
        return OfferResult(
            domain=domain, action="send_email",
            success=False, message="SMTP credentials not configured", dry_run=False,
        )

    try:
        msg = MIMEMultipart()
        msg["From"] = email_data["sender"]
        msg["To"] = recipient
        msg["Subject"] = email_data["subject"]
        msg.attach(MIMEText(email_data["body"], "plain"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(email_data["sender"], recipient, msg.as_string())

        return OfferResult(
            domain=domain, action="send_email",
            success=True, message=f"Sent to {recipient}", dry_run=False,
        )
    except (smtplib.SMTPException, OSError) as exc:
        return OfferResult(
            domain=domain, action="send_email",
            success=False, message=f"SMTP error: {exc}", dry_run=False,
        )


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------
def process_offers(
    db_path: Path,
    csv_path: Path,
    sender_email: str,
    *,
    dry_run: bool = True,
) -> list[OfferResult]:
    """Load CSV targets, insert into DB, generate offers. Dry-run by default."""
    assert isinstance(db_path, Path), "db_path must be Path"
    assert isinstance(csv_path, Path), "csv_path must be Path"

    conn = init_database(db_path)
    targets = load_offer_targets(csv_path)
    results: list[OfferResult] = []

    for i, target in enumerate(targets):
        if i >= MAX_OFFERS:
            logger.warning("MAX_OFFERS (%d) reached, stopping", MAX_OFFERS)
            break

        existing = get_offer(conn, target.domain)
        if existing is not None:
            logger.info("Offer already exists for %s, skipping insert", target.domain)
            results.append(OfferResult(
                domain=target.domain, action="skip",
                success=True, message="Already in database", dry_run=dry_run,
            ))
            continue

        row_id = insert_offer(conn, target)
        email_data = generate_offer_email(target, sender_email)

        if target.method == "whois":
            whois_email = extract_whois_email(target.domain)
            if whois_email and not dry_run:
                result = send_offer_email(email_data, whois_email, dry_run=dry_run)
                if result.success:
                    record_sent(conn, target.domain)
                results.append(result)
            else:
                action_msg = (
                    f"DRY RUN: WHOIS email={'found: ' + whois_email if whois_email else 'not found'}"
                    if dry_run
                    else f"WHOIS email not found for {target.domain}"
                )
                results.append(OfferResult(
                    domain=target.domain, action="whois_lookup",
                    success=True, message=action_msg, dry_run=dry_run,
                ))
        else:
            results.append(OfferResult(
                domain=target.domain, action="marketplace_offer",
                success=True,
                message=f"Submit ${target.offer_amount} on {target.method} (row {row_id})",
                dry_run=dry_run,
            ))

    conn.close()
    return results


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """CLI entry point for domain offeror."""
    import argparse

    parser = argparse.ArgumentParser(description="Domain Acquisition Offer System")
    parser.add_argument("--db", type=Path, default=Path(DB_FILENAME))
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--sender", type=str, default="offers@example.com")
    parser.add_argument("--live", action="store_true", help="Disable dry-run mode")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    assert args.csv.is_file(), f"CSV not found: {args.csv}"
    assert "@" in args.sender, f"Invalid sender: {args.sender}"

    results = process_offers(
        db_path=args.db, csv_path=args.csv,
        sender_email=args.sender, dry_run=not args.live,
    )

    for r in results:
        prefix = "[DRY]" if r.dry_run else "[LIVE]"
        status = "OK" if r.success else "FAIL"
        print(f"{prefix} {status} {r.domain}: {r.action} - {r.message}")


if __name__ == "__main__":
    main()
