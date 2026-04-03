"""
tests/test_settlement.py
Run with: pytest tests/test_settlement.py -v
"""
import sys, os, sqlite3, random
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from settlement import settle_payout, reconcile_pending, daily_reconciliation_report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, claim_id TEXT, txn_type TEXT,
            amount REAL, method TEXT, status TEXT,
            gateway_ref TEXT DEFAULT '', utr TEXT DEFAULT '',
            rollback_reason TEXT DEFAULT '', attempts TEXT DEFAULT '[]',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP, settled_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id TEXT, status TEXT
        )
    """)
    db.commit()
    return db


# ---------------------------------------------------------------------------
# settle_payout – UPI primary
# ---------------------------------------------------------------------------

def test_upi_success():
    random.seed(42)
    r = settle_payout(1, 'CLM001', 500.0, preferred_method='UPI')
    assert r['status'] == 'Success'
    assert r['method_used'] in ('UPI', 'IMPS')
    assert r['gateway_ref'].startswith('GC-')
    assert r['amount'] == 500.0
    assert r['settled_at'] is not None
    assert isinstance(r['attempts'], list)
    assert len(r['attempts']) >= 1


def test_upi_fallback_to_imps():
    """Force UPI to fail by using a very high random seed that triggers 8% failure."""
    # Patch random to always return 0.01 (< 0.08 threshold) for first call only
    original = random.random
    calls = [0]
    def patched():
        calls[0] += 1
        return 0.01 if calls[0] == 1 else 0.99  # UPI fails, IMPS succeeds
    random.random = patched
    try:
        r = settle_payout(1, 'CLM002', 300.0, preferred_method='UPI')
        assert r['status'] == 'Success'
        assert r['method_used'] == 'IMPS'
        assert any(a['channel'] == 'UPI' for a in r['attempts'])
        assert any(a['channel'] == 'IMPS' for a in r['attempts'])
    finally:
        random.random = original


def test_both_channels_fail_rollback():
    """Force both UPI and IMPS to fail → Rolled_Back."""
    original = random.random
    random.random = lambda: 0.01  # always < failure threshold
    try:
        r = settle_payout(1, 'CLM003', 400.0, preferred_method='UPI')
        assert r['status'] == 'Rolled_Back'
        assert r['settled_at'] is None
        assert r['rollback_reason'] is not None
        assert r['method_used'] is None
    finally:
        random.random = original


def test_amount_exceeds_limit_rollback():
    r = settle_payout(1, 'CLM004', 150000.0)
    assert r['status'] == 'Rolled_Back'
    assert 'limit' in r['rollback_reason'].lower() or 'All' in r['rollback_reason']


def test_zero_amount_raises():
    raised = False
    try:
        settle_payout(1, 'CLM005', 0.0)
    except ValueError:
        raised = True
    assert raised


def test_negative_amount_raises():
    raised = False
    try:
        settle_payout(1, 'CLM006', -100.0)
    except ValueError:
        raised = True
    assert raised


# ---------------------------------------------------------------------------
# settle_payout – IMPS direct
# ---------------------------------------------------------------------------

def test_imps_direct_success():
    random.seed(0)
    r = settle_payout(1, 'CLM007', 200.0, preferred_method='IMPS')
    assert r['status'] == 'Success'
    assert r['method_used'] == 'IMPS'
    assert r['utr'].startswith('IMPS')


# ---------------------------------------------------------------------------
# settle_payout – Razorpay sandbox
# ---------------------------------------------------------------------------

def test_razorpay_sandbox_success():
    r = settle_payout(1, 'CLM008', 1000.0, use_razorpay_sandbox=True)
    assert r['status'] == 'Success'
    assert r['method_used'] == 'Razorpay'
    assert 'razorpay_payout_id' in r['utr'] or r['utr'].startswith('pout_')


def test_razorpay_sandbox_limit():
    r = settle_payout(1, 'CLM009', 60000.0, use_razorpay_sandbox=True)
    assert r['status'] == 'Rolled_Back'
    assert 'sandbox' in r['rollback_reason'].lower() or 'limit' in r['rollback_reason'].lower()


# ---------------------------------------------------------------------------
# Result structure
# ---------------------------------------------------------------------------

def test_result_has_all_keys():
    random.seed(5)
    r = settle_payout(1, 'CLM010', 750.0)
    for key in ('status', 'method_used', 'gateway_ref', 'utr', 'amount', 'attempts', 'settled_at', 'rollback_reason'):
        assert key in r, f'Missing key: {key}'


def test_attempts_logged_per_channel():
    random.seed(42)
    r = settle_payout(1, 'CLM011', 500.0, preferred_method='UPI')
    assert all('channel' in a for a in r['attempts'])
    assert all('ok' in a for a in r['attempts'])


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

def test_reconcile_pending_resolves_stale():
    db = _make_db()
    # Insert a stale Pending transaction (created 20 minutes ago)
    db.execute(
        "INSERT INTO transactions(user_id,claim_id,txn_type,amount,method,status,created_at) VALUES(1,'CLM099','payout',500,'UPI','Pending',datetime('now','-20 minutes'))"
    )
    db.execute("INSERT INTO claims(claim_id,status) VALUES('CLM099','Processing')")
    db.commit()

    result = reconcile_pending(db, stale_minutes=10)
    assert result['stale_resolved'] == 1

    row = db.execute("SELECT status FROM transactions WHERE claim_id='CLM099'").fetchone()
    assert row['status'] == 'Failed'
    claim = db.execute("SELECT status FROM claims WHERE claim_id='CLM099'").fetchone()
    assert claim['status'] == 'Failed'


def test_reconcile_skips_fresh_pending():
    db = _make_db()
    db.execute(
        "INSERT INTO transactions(user_id,claim_id,txn_type,amount,method,status,created_at) VALUES(1,'CLM098','payout',300,'UPI','Pending',datetime('now','-2 minutes'))"
    )
    db.commit()
    result = reconcile_pending(db, stale_minutes=10)
    assert result['stale_resolved'] == 0


def test_reconcile_ignores_non_pending():
    db = _make_db()
    db.execute(
        "INSERT INTO transactions(user_id,claim_id,txn_type,amount,method,status,created_at) VALUES(1,'CLM097','payout',400,'UPI','Success',datetime('now','-30 minutes'))"
    )
    db.commit()
    result = reconcile_pending(db, stale_minutes=10)
    assert result['stale_resolved'] == 0


# ---------------------------------------------------------------------------
# Daily reconciliation report
# ---------------------------------------------------------------------------

def test_daily_report_structure():
    db = _make_db()
    db.execute("INSERT INTO transactions(user_id,txn_type,amount,method,status) VALUES(1,'payout',500,'UPI','Success')")
    db.execute("INSERT INTO transactions(user_id,txn_type,amount,method,status) VALUES(1,'payout',300,'IMPS','Failed')")
    db.execute("INSERT INTO transactions(user_id,txn_type,amount,method,status) VALUES(1,'premium',50,'UPI','Success')")
    db.commit()

    report = daily_reconciliation_report(db)
    assert 'payout_totals' in report
    assert 'channel_breakdown' in report
    assert 'summary' in report
    assert 'generated_at' in report
    assert report['payout_totals']['total_settled'] == 500.0
    assert report['payout_totals']['total_failed'] == 300.0
    assert report['payout_totals']['total_transactions'] == 2


def test_daily_report_empty_db():
    db = _make_db()
    report = daily_reconciliation_report(db)
    assert report['payout_totals']['total_transactions'] == 0
    assert report['payout_totals']['total_settled'] == 0.0
