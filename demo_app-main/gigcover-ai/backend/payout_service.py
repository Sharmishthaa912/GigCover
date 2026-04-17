"""
payout_service.py
Advanced payout processing for GigCover AI Phase 3.
Features:
  - Multi-channel settlement (UPI, IMPS, Razorpay)
  - Fraud-aware payouts with rollback
  - Real-time status tracking
  - Reconciliation and reporting
"""

import uuid
import time
import random
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple

# Import fraud detection for payout validation
from fraud_detection import compute_fraud_score, progressive_verification


class PayoutService:
    """Centralized payout processing service."""

    def __init__(self):
        self.channels = {
            'UPI': self._upi_transfer,
            'IMPS': self._imps_transfer,
            'Razorpay': self._razorpay_sandbox_transfer
        }

    def _upi_transfer(self, amount: float, worker_upi: str, ref: str) -> Dict:
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

    def _imps_transfer(self, amount: float, worker_upi: str, ref: str) -> Dict:
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

    def _razorpay_sandbox_transfer(self, amount: float, ref: str) -> Dict:
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

    def process_payout(
        self,
        user_id: int,
        claim_id: str,
        amount: float,
        worker_upi: str = '',
        preferred_method: str = 'UPI',
        fraud_check: bool = True,
        activity_logs: Optional[List[Dict]] = None,
        trigger_time: Optional[datetime] = None
    ) -> Dict:
        """
        Full payout processing with fraud validation and multi-channel settlement.

        Args:
            user_id: Worker user ID
            claim_id: Claim identifier
            amount: Payout amount
            worker_upi: UPI ID for transfers
            preferred_method: Preferred payment method
            fraud_check: Whether to perform fraud validation
            activity_logs: Worker activity logs for fraud scoring
            trigger_time: When the trigger occurred

        Returns:
            Payout result dict with status, fraud analysis, and settlement details
        """
        if amount <= 0:
            raise ValueError('Payout amount must be positive')

        ref = f'GC-{uuid.uuid4().hex[:12].upper()}'
        now = datetime.now(timezone.utc)
        attempts = []

        # Fraud check if enabled
        fraud_analysis = None
        if fraud_check and activity_logs and trigger_time:
            # Mock worker data for fraud scoring
            worker_mock = {'user_id': user_id}
            fraud_analysis = compute_fraud_score(worker_mock, activity_logs, trigger_time)
            verification = progressive_verification(fraud_analysis['fraud_score'], fraud_analysis['flags'])

            if verification['tier'] == 'block':
                return {
                    'status': 'Blocked',
                    'reason': verification['reason'],
                    'fraud_analysis': fraud_analysis,
                    'verification': verification,
                    'gateway_ref': ref,
                    'amount': round(amount, 2),
                    'settled_at': None
                }

        # Channel priority: UPI -> IMPS -> Razorpay
        channels_to_try = []
        if preferred_method == 'UPI':
            channels_to_try = ['UPI', 'IMPS', 'Razorpay']
        elif preferred_method == 'IMPS':
            channels_to_try = ['IMPS', 'UPI', 'Razorpay']
        else:
            channels_to_try = ['Razorpay', 'UPI', 'IMPS']

        for channel in channels_to_try:
            if channel not in self.channels:
                continue

            transfer_func = self.channels[channel]
            if channel in ['UPI', 'IMPS']:
                res = transfer_func(amount, worker_upi, ref)
            else:
                res = transfer_func(amount, ref)

            attempts.append({'channel': channel, **res})

            if res['ok']:
                return {
                    'status': 'Success',
                    'method_used': channel,
                    'gateway_ref': ref,
                    'utr': res.get('utr') or res.get('razorpay_payout_id', ''),
                    'amount': round(amount, 2),
                    'attempts': attempts,
                    'settled_at': now.isoformat(),
                    'fraud_analysis': fraud_analysis,
                    'note': f'Sandbox payout via {channel}. Replace with real SDK in production.'
                }

        # All channels failed
        return {
            'status': 'Failed',
            'method_used': None,
            'gateway_ref': ref,
            'utr': '',
            'amount': round(amount, 2),
            'attempts': attempts,
            'settled_at': None,
            'fraud_analysis': fraud_analysis,
            'note': 'All payment channels failed. No money moved.'
        }

    def get_payout_status(self, gateway_ref: str) -> Dict:
        """
        Check payout status by gateway reference.
        In production, query actual payment gateway APIs.
        """
        # Mock status check - in real impl, call gateway APIs
        return {
            'gateway_ref': gateway_ref,
            'status': 'Success',  # Mock successful
            'last_checked': datetime.now(timezone.utc).isoformat(),
            'details': 'Status verified via gateway API'
        }

    def rollback_payout(self, gateway_ref: str, reason: str) -> Dict:
        """
        Rollback a payout if it was initiated but needs to be reversed.
        In production, call gateway reversal APIs.
        """
        return {
            'gateway_ref': gateway_ref,
            'rollback_status': 'Success',
            'reason': reason,
            'rolled_back_at': datetime.now(timezone.utc).isoformat(),
            'note': 'Sandbox rollback - no real money movement'
        }


# Global service instance
payout_service = PayoutService()


def process_payout(
    user_id: int,
    claim_id: str,
    amount: float,
    worker_upi: str = '',
    preferred_method: str = 'UPI',
    fraud_check: bool = True,
    activity_logs: Optional[List[Dict]] = None,
    trigger_time: Optional[datetime] = None
) -> Dict:
    """
    Convenience function for backward compatibility.
    """
    return payout_service.process_payout(
        user_id, claim_id, amount, worker_upi, preferred_method,
        fraud_check, activity_logs, trigger_time
    )


def reconcile_pending(db, stale_minutes: int = 10) -> Dict:
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


def daily_reconciliation_report(db) -> Dict:
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
          SUM(amount) AS total_amount
        FROM transactions
        WHERE created_at >= date('now', '-1 day')
        GROUP BY txn_type, method, status
        """,
    ).fetchall()

    report = {
        'date': datetime.now(timezone.utc).date().isoformat(),
        'summary': {},
        'details': []
    }

    for row in rows:
        key = f"{row['txn_type']}_{row['method']}_{row['status']}"
        report['summary'][key] = {
            'count': row['count'],
            'total_amount': round(row['total_amount'] or 0, 2)
        }
        report['details'].append(dict(row))

    return report