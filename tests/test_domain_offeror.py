"""Tests for domain_offeror.py — automated domain acquisition offer system.

NASA Power of 10 compliant: min 2 assertions per test function.
"""
from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

import pytest

from tools.domain_offeror import (
    DB_FILENAME,
    MAX_FOLLOWUPS,
    MAX_OFFERS,
    VALID_STATUSES,
    DomainOffer,
    OfferResult,
    generate_counter_response,
    generate_followup_email,
    generate_offer_email,
    get_all_offers,
    get_followup_count,
    get_offer,
    init_database,
    insert_offer,
    load_offer_targets,
    process_offers,
    record_followup,
    record_sent,
    send_offer_email,
    update_status,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    """Return a temp database path."""
    path = tmp_path / DB_FILENAME
    assert tmp_path.is_dir()
    return path


@pytest.fixture()
def db_conn(db_path: Path) -> sqlite3.Connection:
    """Return an initialized database connection."""
    conn = init_database(db_path)
    assert conn is not None
    yield conn
    conn.close()


@pytest.fixture()
def sample_offer() -> DomainOffer:
    """Return a sample DomainOffer."""
    offer = DomainOffer(
        domain="devhub.io",
        method="afternic",
        offer_amount=500,
        max_amount=1000,
        notes="DR 27 best authority play",
    )
    assert offer.domain == "devhub.io"
    return offer


@pytest.fixture()
def csv_file(tmp_path: Path) -> Path:
    """Create a temporary CSV file with offer targets."""
    csv_path = tmp_path / "test_targets.csv"
    csv_path.write_text(
        "domain,method,offer_usd,max_usd,notes\n"
        "devhub.io,afternic,500,1000,DR 27 best authority play\n"
        "apitools.com,dynadot,200,400,tech niche\n"
        "sitegrader.com,whois,100,300,SEO tool keyword\n",
        encoding="utf-8",
    )
    assert csv_path.is_file()
    return csv_path


# ---------------------------------------------------------------------------
# Test 1: Database initialization
# ---------------------------------------------------------------------------
def test_init_database_creates_table(db_path: Path) -> None:
    """Database init creates the domain_offers table and index."""
    conn = init_database(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='domain_offers'"
    )
    table = cursor.fetchone()
    assert table is not None, "domain_offers table not created"

    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_domain_offers_domain'"
    )
    index = cursor.fetchone()
    assert index is not None, "domain index not created"
    conn.close()


# ---------------------------------------------------------------------------
# Test 2: Database rejects bad path
# ---------------------------------------------------------------------------
def test_init_database_rejects_non_db_extension(tmp_path: Path) -> None:
    """Database init rejects non-.db file extensions."""
    bad_path = tmp_path / "test.txt"
    with pytest.raises(AssertionError, match="must end with .db"):
        init_database(bad_path)
    assert not bad_path.exists()


# ---------------------------------------------------------------------------
# Test 3: Insert and retrieve offer
# ---------------------------------------------------------------------------
def test_insert_and_get_offer(db_conn: sqlite3.Connection, sample_offer: DomainOffer) -> None:
    """Insert an offer and retrieve it by domain."""
    row_id = insert_offer(db_conn, sample_offer)
    assert row_id > 0, "Insert must return positive row ID"

    row = get_offer(db_conn, "devhub.io")
    assert row is not None, "Offer must be retrievable after insert"
    assert row["domain"] == "devhub.io"
    assert row["offer_amount"] == 500
    assert row["status"] == "draft"


# ---------------------------------------------------------------------------
# Test 4: CSV loading
# ---------------------------------------------------------------------------
def test_load_offer_targets(csv_file: Path) -> None:
    """CSV loading returns correct number of offers with valid fields."""
    offers = load_offer_targets(csv_file)
    assert len(offers) == 3, f"Expected 3 offers, got {len(offers)}"

    first = offers[0]
    assert first.domain == "devhub.io"
    assert first.offer_amount == 500
    assert first.max_amount == 1000
    assert first.method == "afternic"


# ---------------------------------------------------------------------------
# Test 5: CSV loading rejects missing file
# ---------------------------------------------------------------------------
def test_load_csv_rejects_missing_file(tmp_path: Path) -> None:
    """CSV loading raises AssertionError for missing file."""
    missing = tmp_path / "nonexistent.csv"
    with pytest.raises(AssertionError, match="CSV file not found"):
        load_offer_targets(missing)
    assert not missing.exists()


# ---------------------------------------------------------------------------
# Test 6: Offer template generation
# ---------------------------------------------------------------------------
def test_generate_offer_email(sample_offer: DomainOffer) -> None:
    """Offer email template includes domain and amount."""
    email = generate_offer_email(sample_offer, "test@example.com")
    assert "devhub.io" in email["subject"], "Subject must contain domain"
    assert "$500" in email["body"], "Body must contain offer amount"
    assert "unsubscribe" in email["body"].lower(), "Body must include CAN-SPAM unsubscribe"
    assert email["sender"] == "test@example.com"


# ---------------------------------------------------------------------------
# Test 7: Follow-up email generation
# ---------------------------------------------------------------------------
def test_generate_followup_email(sample_offer: DomainOffer) -> None:
    """Follow-up email references domain and original offer."""
    email = generate_followup_email(sample_offer, "test@example.com")
    assert "devhub.io" in email["subject"], "Follow-up subject must contain domain"
    assert "$500" in email["body"], "Follow-up body must reference offer amount"
    assert "unsubscribe" in email["body"].lower(), "Follow-up must include CAN-SPAM"


# ---------------------------------------------------------------------------
# Test 8: Status transitions
# ---------------------------------------------------------------------------
def test_status_transitions(db_conn: sqlite3.Connection, sample_offer: DomainOffer) -> None:
    """Status updates follow valid transitions."""
    insert_offer(db_conn, sample_offer)

    for status in ("sent", "responded", "countered", "accepted", "completed"):
        result = update_status(db_conn, "devhub.io", status)
        assert result is True, f"Status update to '{status}' must succeed"
        row = get_offer(db_conn, "devhub.io")
        assert row["status"] == status, f"Status must be '{status}' after update"


# ---------------------------------------------------------------------------
# Test 9: Invalid status rejected
# ---------------------------------------------------------------------------
def test_invalid_status_rejected(db_conn: sqlite3.Connection, sample_offer: DomainOffer) -> None:
    """Invalid statuses are rejected by assertion."""
    insert_offer(db_conn, sample_offer)

    with pytest.raises(AssertionError, match="Invalid status"):
        update_status(db_conn, "devhub.io", "invalid_status")

    row = get_offer(db_conn, "devhub.io")
    assert row["status"] == "draft", "Status must remain 'draft' after invalid update"


# ---------------------------------------------------------------------------
# Test 10: Dry-run mode
# ---------------------------------------------------------------------------
def test_dry_run_does_not_send(sample_offer: DomainOffer) -> None:
    """Dry-run mode returns success without sending."""
    email_data = generate_offer_email(sample_offer, "test@example.com")
    result = send_offer_email(email_data, "recipient@example.com", dry_run=True)

    assert result.dry_run is True, "Result must indicate dry-run mode"
    assert result.success is True, "Dry-run must succeed"
    assert "DRY RUN" in result.message, "Message must indicate dry run"


# ---------------------------------------------------------------------------
# Test 11: Max follow-up enforcement
# ---------------------------------------------------------------------------
def test_max_followup_enforcement(db_conn: sqlite3.Connection, sample_offer: DomainOffer) -> None:
    """Follow-ups are capped at MAX_FOLLOWUPS per domain."""
    insert_offer(db_conn, sample_offer)

    # First follow-up should succeed
    first = record_followup(db_conn, "devhub.io")
    assert first is True, "First follow-up must succeed"

    # Second follow-up should be rejected
    second = record_followup(db_conn, "devhub.io")
    assert second is False, "Second follow-up must be rejected (MAX_FOLLOWUPS=1)"

    count = get_followup_count(db_conn, "devhub.io")
    assert count == MAX_FOLLOWUPS, f"Follow-up count must be {MAX_FOLLOWUPS}"


# ---------------------------------------------------------------------------
# Test 12: Record sent updates status and timestamp
# ---------------------------------------------------------------------------
def test_record_sent(db_conn: sqlite3.Connection, sample_offer: DomainOffer) -> None:
    """Recording a sent offer updates status to 'sent' and sets sent_at."""
    insert_offer(db_conn, sample_offer)
    result = record_sent(db_conn, "devhub.io")
    assert result is True, "record_sent must succeed"

    row = get_offer(db_conn, "devhub.io")
    assert row["status"] == "sent", "Status must be 'sent'"
    assert row["sent_at"] is not None, "sent_at must be set"


# ---------------------------------------------------------------------------
# Test 13: Counter-offer response — within budget
# ---------------------------------------------------------------------------
def test_counter_response_accept(sample_offer: DomainOffer) -> None:
    """Counter-offer within max_amount generates accept response."""
    response = generate_counter_response(sample_offer, 800, "test@example.com")
    assert response["action"] == "accept", "Counter within budget must be accepted"
    assert "$800" in response["body"], "Body must reference counter amount"


# ---------------------------------------------------------------------------
# Test 14: Counter-offer response — over budget
# ---------------------------------------------------------------------------
def test_counter_response_over_budget(sample_offer: DomainOffer) -> None:
    """Counter-offer above max_amount generates counter response."""
    response = generate_counter_response(sample_offer, 2000, "test@example.com")
    assert response["action"] == "counter", "Counter above budget must generate counter"
    assert "$2,000" in response["body"], "Body must reference their counter amount"


# ---------------------------------------------------------------------------
# Test 15: Frozen dataclasses
# ---------------------------------------------------------------------------
def test_frozen_dataclasses() -> None:
    """DomainOffer and OfferResult are immutable."""
    offer = DomainOffer(domain="test.com", method="whois", offer_amount=100, max_amount=200)
    with pytest.raises(AttributeError):
        offer.domain = "changed.com"  # type: ignore[misc]

    result = OfferResult(domain="test.com", action="send", success=True, message="ok", dry_run=True)
    with pytest.raises(AttributeError):
        result.success = False  # type: ignore[misc]

    assert offer.domain == "test.com"
    assert result.success is True


# ---------------------------------------------------------------------------
# Test 16: get_all_offers bounded by MAX_OFFERS
# ---------------------------------------------------------------------------
def test_get_all_offers_bounded(db_conn: sqlite3.Connection) -> None:
    """get_all_offers returns at most MAX_OFFERS rows."""
    for i in range(5):
        offer = DomainOffer(
            domain=f"domain{i}.com", method="whois",
            offer_amount=100, max_amount=200,
        )
        insert_offer(db_conn, offer)

    rows = get_all_offers(db_conn)
    assert len(rows) == 5, f"Expected 5 rows, got {len(rows)}"
    assert len(rows) <= MAX_OFFERS, "Row count must not exceed MAX_OFFERS"


# ---------------------------------------------------------------------------
# Test 17: Process offers integration (dry-run)
# ---------------------------------------------------------------------------
def test_process_offers_dry_run(tmp_path: Path, csv_file: Path) -> None:
    """process_offers in dry-run mode creates DB records without sending."""
    db_path = tmp_path / "integration_test.db"
    results = process_offers(
        db_path=db_path, csv_path=csv_file,
        sender_email="test@example.com", dry_run=True,
    )
    assert len(results) == 3, f"Expected 3 results, got {len(results)}"
    assert all(r.dry_run for r in results), "All results must be dry-run"

    # Verify DB was created and populated
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM domain_offers")
    count = cursor.fetchone()[0]
    assert count == 3, f"Expected 3 DB records, got {count}"
    conn.close()


# ---------------------------------------------------------------------------
# Test 18: Process offers skips duplicates
# ---------------------------------------------------------------------------
def test_process_offers_skips_duplicates(tmp_path: Path, csv_file: Path) -> None:
    """Running process_offers twice skips already-inserted domains."""
    db_path = tmp_path / "dedup_test.db"

    results_1 = process_offers(
        db_path=db_path, csv_path=csv_file,
        sender_email="test@example.com", dry_run=True,
    )
    assert len(results_1) == 3

    results_2 = process_offers(
        db_path=db_path, csv_path=csv_file,
        sender_email="test@example.com", dry_run=True,
    )
    assert all(r.action == "skip" for r in results_2), "Second run must skip all domains"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM domain_offers")
    count = cursor.fetchone()[0]
    assert count == 3, "No duplicate rows should be inserted"
    conn.close()
