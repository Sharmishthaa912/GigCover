"""
settlement.py
Full parametric insurance settlement engine.

Channels (in priority order):
  1. UPI   – instant, preferred
  2. IMPS  – fallback if UPI fails
  3. Razorpay sandbox – demo/testing

Flow per payout:
  reserve → fraud_check → initiate → confirm → settle → log
  On any failure after initiation → rollback → log Rolled_Back

Reconciliation:
  reconcile_pending()  – re-checks all Pending txns older than N minutes
  daily_reconciliation_report() – totals by status/channel
"""

import uuid
import time
import random
from datetime import datetime, timezone, timedelta


# ---------------------------------------------------------------------------
# Channel simulators
# (Replace _upi_transfer / _imps_transfer bodies with real SDK calls)
# ---------------------------------------------------------------------------

def _upi_transfer(amount: float, worker_upi: str, ref: str) -> dict:
    """
    Sandbox UPI transfer.
    Real impl: call Razorpay Payout API with mode='UPI'.
    Simulates ~92% success rate.
    """
    time.sleep(0.05)
    if amount > 100000:
        return {'ok': False, 'code': 'LIMIT_EXCEEDED', 'msg': 'UPI daily limit exceeded'}
    if random.random() < 0.08:
        return {'ok': False, 'code': 'UPI_TIMEOUT', 'msg': 'UPI gateway timeout'}
    return {'ok': True, 'code': 'SUCCESS', 'utr': f'UPI{ref[-8:].upper()}', 'msg': 'UPI transfer successful'}


def _imps_transfer(amount: float, worker_upi: str, ref: str) -> dict:
    """
    Sandbox IMPS transfer (fallback).
    Real impl: call Razorpay Payout API with mode='IMPS'.
    Simulates ~97% success rate.
    """
    time.sleep(0.05)
    if amount > 100000:
        return {'ok': False, 'code': 'LIMIT_EXCEEDED', 'msg': 'IMPS daily limit exceeded'}
    if random.random() < 0.03:
        return {'ok': False, 'code': 'IMPS_FAILED', 'msg': 'IMPS transfer failed'}
    return {'ok': True, 'code': 'SUCCESS', 'utr': f'IMPS{ref[-8:].upper()}', 'msg': 'IMPS transfer successful'}


def _razorpay_sandbox_transfer(amount: float, ref: str) -> dict:
    """
    Razorpay sandbox payout (demo mode).
    Real impl: razorpay.payouts.create({...})
    Always succeeds in sandbox unless amount > 50000.
    """
    if amount > 50000:
        return {'ok': False, 'code': 'SANDBOX_LIMIT', 'msg': 'Razorpay sandbox limit ₹50,000'}
    return {
        'ok': True,
        'code': 'SUCCESS',
        'razorpay_payout_id': f'pout_{uuid.uuid4().hex[:14]}',
        'msg': 'Razorpay sandbox payout created',
    }


# ---------------------------------------------------------------------------
# Core settlement function
# ---------------------------------------------------------------------------

def settle_payout(
    user_id: int,
    claim_id: str,
    amount: float,
    worker_upi: str = '',
    preferred_method: str = 'UPI',
    use_razorpay_sandbox: bool = False,
) -> dict:
    """
    Full settlement pipeline with channel fallback and rollback.

    Returns a settlement_result dict:
      status        : 'Success' | 'Failed' | 'Rolled_Back'
      method_used   : 'UPI' | 'IMPS' | 'Razorpay'
      gateway_ref   : unique reference
      utr           : bank UTR (if available)
      amount        : settled amount
      attempts      : list of attempt dicts (for audit)
      settled_at    : ISO timestamp or None
      rollback_reason: set if Rolled_Back
    """
    if amount <= 0:
        raise ValueError('Settlement amount must be positive')

    ref = f'GC-{uuid.uuid4().hex[:12].upper()}'
    now = datetime.now(timezone.utc)
    attempts = []

    # ── Step 1: Reserve (mark as Pending in caller's DB before transfer) ──
    # Caller must INSERT transaction with status='Pending' before calling this.

    # ── Step 2: Razorpay sandbox path (demo/testing) ──
    if use_razorpay_sandbox:
        res = _razorpay_sandbox_transfer(amount, ref)
        attempts.append({'channel': 'Razorpay', **res})
        if res['ok']:
            return _success_result(ref, 'Razorpay', amount, res, now, attempts)
        return _rollback_result(ref, amount, attempts, res['msg'])

    # ── Step 3: UPI primary ──
    if preferred_method == 'UPI' or not preferred_method:
        res = _upi_transfer(amount, worker_upi, ref)
        attempts.append({'channel': 'UPI', **res})
        if res['ok']:
            return _success_result(ref, 'UPI', amount, res, now, attempts)
        # UPI failed → fall through to IMPS

    # ── Step 4: IMPS fallback ──
    res = _imps_transfer(amount, worker_upi, ref)
    attempts.append({'channel': 'IMPS', **res})
    if res['ok']:
        return _success_result(ref, 'IMPS', amount, res, now, attempts)

    # ── Step 5: Both channels failed → rollback ──
    return _rollback_result(ref, amount, attempts, 'All payment channels failed')


def _success_result(ref, method, amount, res, now, attempts):
    return {
        'status': 'Success',
        'method_used': method,
        'gateway_ref': ref,
        'utr': res.get('utr') or res.get('razorpay_payout_id', ''),
        'amount': round(amount, 2),
        'attempts': attempts,
        'settled_at': now.isoformat(),
        'rollback_reason': None,
        'note': f'Sandbox settlement via {method}. Replace channel functions with real SDK in production.',
    }


def _rollback_result(ref, amount, attempts, reason):
    return {
        'status': 'Rolled_Back',
        'method_used': None,
        'gateway_ref': ref,
        'utr': '',
        'amount': round(amount, 2),
        'attempts': attempts,
        'settled_at': None,
        'rollback_reason': reason,
        'note': 'All channels exhausted. Transaction rolled back. No money moved.',
    }


# ---------------------------------------------------------------------------
# Reconciliation helpers (called by background job or admin endpoint)
# ---------------------------------------------------------------------------

def reconcile_pending(db, stale_minutes: int = 10) -> dict:
    """
    Re-check all transactions stuck in 'Pending' for > stale_minutes.
    In production: query gateway API for each gateway_ref.
    Sandbox: mark as Failed (simulate timeout).
    Returns counts of resolved transactions.
    """
    stale = db.execute(
        "SELECT id, user_id, claim_id, amount, method, gateway_ref FROM transactions "
        "WHERE status='Pending' AND created_at <= datetime('now', ? || ' minutes')",
        (f'-{stale_minutes}',),
    ).fetchall()

    resolved_failed = 0
    for row in stale:
        db.execute("UPDATE transactions SET status='Failed' WHERE id=?", (row['id'],))
        if row['claim_id']:
            db.execute("UPDATE claims SET status='Failed' WHERE claim_id=?", (row['claim_id'],))
        resolved_failed += 1

    db.commit()
    return {'stale_resolved': resolved_failed, 'cutoff_minutes': stale_minutes}


def daily_reconciliation_report(db) -> dict:
    """
    Aggregate transaction totals by status and channel.
    Used for admin reconciliation dashboard.
    """
    rows = db.execute(
        """
        SELECT
          txn_type,
          method,
          status,
          COUNT(*) AS count,
          COALESCE(SUM(amount), 0) AS total_amount
        FROM transactions
        GROUP BY txn_type, method, status
        ORDER BY txn_type, method, status
        """
    ).fetchall()

    summary = [dict(r) for r in rows]

    totals = db.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN status='Success' THEN amount ELSE 0 END), 0) AS total_settled,
          COALESCE(SUM(CASE WHEN status='Failed'  THEN amount ELSE 0 END), 0) AS total_failed,
          COALESCE(SUM(CASE WHEN status='Rolled_Back' THEN amount ELSE 0 END), 0) AS total_rolled_back,
          COALESCE(SUM(CASE WHEN status='Pending' THEN amount ELSE 0 END), 0) AS total_pending,
          COUNT(*) AS total_transactions
        FROM transactions
        WHERE txn_type='payout'
        """
    ).fetchone()

    channel_breakdown = db.execute(
        """
        SELECT method, COUNT(*) AS count,
               COALESCE(SUM(CASE WHEN status='Success' THEN amount ELSE 0 END),0) AS settled
        FROM transactions WHERE txn_type='payout'
        GROUP BY method
        """
    ).fetchall()

    return {
        'summary': summary,
        'payout_totals': {
            'total_settled':     round(float(totals['total_settled']), 2),
            'total_failed':      round(float(totals['total_failed']), 2),
            'total_rolled_back': round(float(totals['total_rolled_back']), 2),
            'total_pending':     round(float(totals['total_pending']), 2),
            'total_transactions': int(totals['total_transactions']),
        },
        'channel_breakdown': [dict(r) for r in channel_breakdown],
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }
