"""
analytics.py
Advanced analytics engine for GigCover AI Phase 3.
Features:
  - Real-time dashboard metrics
  - Risk trend analysis
  - Fraud pattern detection
  - Performance KPIs
  - Predictive insights
"""

import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics


class AnalyticsEngine:
    """Central analytics processing for dashboards and insights."""

    def __init__(self):
        self.cache = {}
        self.cache_timeout = 300  # 5 minutes

    def get_worker_analytics(self, db, user_id: int, days: int = 30) -> Dict:
        """Generate comprehensive worker analytics."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # Claims history
        claims = db.execute(
            "SELECT * FROM claims WHERE user_id = ? AND created_at >= ? ORDER BY created_at DESC",
            (user_id, cutoff_date.isoformat())
        ).fetchall()

        # Transactions
        transactions = db.execute(
            "SELECT * FROM transactions WHERE user_id = ? AND created_at >= ? ORDER BY created_at DESC",
            (user_id, cutoff_date.isoformat())
        ).fetchall()

        # Activity logs
        activities = db.execute(
            "SELECT * FROM activity_logs WHERE user_id = ? AND logged_at >= ? ORDER BY logged_at DESC LIMIT 1000",
            (user_id, cutoff_date.isoformat())
        ).fetchall()

        # Trigger events
        triggers = db.execute(
            "SELECT * FROM trigger_events WHERE affected_users LIKE ? AND triggered_at >= ? ORDER BY triggered_at DESC",
            (f'%{user_id}%', cutoff_date.isoformat())
        ).fetchall()

        return self._compute_worker_metrics(claims, transactions, activities, triggers, days)

    def get_admin_analytics(self, db, days: int = 30) -> Dict:
        """Generate comprehensive admin analytics."""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

        # System-wide metrics
        users = db.execute("SELECT COUNT(*) as total FROM users").fetchone()['total']
        active_users = db.execute(
            "SELECT COUNT(DISTINCT user_id) FROM claims WHERE created_at >= ?",
            (cutoff_date.isoformat(),)
        ).fetchone()[0]

        claims = db.execute(
            "SELECT * FROM claims WHERE created_at >= ? ORDER BY created_at DESC",
            (cutoff_date.isoformat(),)
        ).fetchall()

        transactions = db.execute(
            "SELECT * FROM transactions WHERE created_at >= ? ORDER BY created_at DESC",
            (cutoff_date.isoformat(),)
        ).fetchall()

        triggers = db.execute(
            "SELECT * FROM trigger_events WHERE triggered_at >= ? ORDER BY triggered_at DESC",
            (cutoff_date.isoformat(),)
        ).fetchall()

        return self._compute_admin_metrics(users, active_users, claims, transactions, triggers, days)

    def _compute_worker_metrics(self, claims: List, transactions: List, activities: List, triggers: List, days: int) -> Dict:
        """Compute detailed worker analytics."""
        now = datetime.now(timezone.utc)

        # Claims analysis
        total_claims = len(claims)
        approved_claims = len([c for c in claims if c['status'] == 'Approved'])
        total_payout = sum(c['payout'] for c in claims if c['status'] == 'Approved')

        # Transaction analysis
        premium_paid = sum(t['amount'] for t in transactions if t['txn_type'] == 'premium' and t['status'] == 'Success')
        payouts_received = sum(t['amount'] for t in transactions if t['txn_type'] == 'payout' and t['status'] == 'Success')

        # Activity analysis
        active_days = len(set(a['logged_at'][:10] for a in activities))  # Unique days
        avg_daily_activity = len(activities) / max(1, active_days)

        # Risk trend
        risk_scores = [c.get('fraud_score', 0) for c in claims if c.get('fraud_score') is not None]
        avg_risk_score = statistics.mean(risk_scores) if risk_scores else 0

        # Trigger participation
        trigger_participation = len(triggers)

        return {
            'period_days': days,
            'generated_at': now.isoformat(),
            'claims': {
                'total': total_claims,
                'approved': approved_claims,
                'approval_rate': round(approved_claims / max(1, total_claims) * 100, 2),
                'total_payout': round(total_payout, 2)
            },
            'transactions': {
                'premium_paid': round(premium_paid, 2),
                'payouts_received': round(payouts_received, 2),
                'net_position': round(payouts_received - premium_paid, 2)
            },
            'activity': {
                'active_days': active_days,
                'avg_daily_activity': round(avg_daily_activity, 2),
                'total_logs': len(activities)
            },
            'risk': {
                'avg_risk_score': round(avg_risk_score, 3),
                'risk_trend': self._calculate_trend(risk_scores)
            },
            'triggers': {
                'participation_count': trigger_participation,
                'recent_triggers': [dict(t) for t in triggers[:5]]
            }
        }

    def _compute_admin_metrics(self, total_users: int, active_users: int, claims: List, transactions: List, triggers: List, days: int) -> Dict:
        """Compute detailed admin analytics."""
        now = datetime.now(timezone.utc)

        # User metrics
        user_engagement = round(active_users / max(1, total_users) * 100, 2)

        # Claims metrics
        total_claims = len(claims)
        approved_claims = len([c for c in claims if c['status'] == 'Approved'])
        pending_claims = len([c for c in claims if c['status'] == 'Pending'])
        failed_claims = len([c for c in claims if c['status'] == 'Failed'])

        total_payout = sum(c['payout'] for c in claims if c['status'] == 'Approved')
        avg_payout = total_payout / max(1, approved_claims)

        # Transaction metrics
        total_transactions = len(transactions)
        successful_transactions = len([t for t in transactions if t['status'] == 'Success'])
        success_rate = round(successful_transactions / max(1, total_transactions) * 100, 2)

        # Revenue metrics
        premium_revenue = sum(t['amount'] for t in transactions if t['txn_type'] == 'premium' and t['status'] == 'Success')
        payout_expenses = sum(t['amount'] for t in transactions if t['txn_type'] == 'payout' and t['status'] == 'Success')
        net_revenue = premium_revenue - payout_expenses

        # Trigger metrics
        total_triggers = len(triggers)
        active_triggers = len([t for t in triggers if t['status'] == 'Active'])

        # Fraud metrics
        fraud_scores = [c.get('fraud_score', 0) for c in claims if c.get('fraud_score') is not None]
        high_fraud_claims = len([c for c in claims if c.get('fraud_score', 0) > 0.7])

        # Geographic distribution
        city_distribution = defaultdict(int)
        for c in claims:
            city = c.get('city', 'Unknown')
            city_distribution[city] += 1

        return {
            'period_days': days,
            'generated_at': now.isoformat(),
            'users': {
                'total': total_users,
                'active': active_users,
                'engagement_rate': user_engagement
            },
            'claims': {
                'total': total_claims,
                'approved': approved_claims,
                'pending': pending_claims,
                'failed': failed_claims,
                'approval_rate': round(approved_claims / max(1, total_claims) * 100, 2),
                'total_payout': round(total_payout, 2),
                'avg_payout': round(avg_payout, 2)
            },
            'transactions': {
                'total': total_transactions,
                'successful': successful_transactions,
                'success_rate': success_rate
            },
            'revenue': {
                'premium_revenue': round(premium_revenue, 2),
                'payout_expenses': round(payout_expenses, 2),
                'net_revenue': round(net_revenue, 2),
                'loss_ratio': round(payout_expenses / max(1, premium_revenue) * 100, 2)
            },
            'triggers': {
                'total': total_triggers,
                'active': active_triggers
            },
            'fraud': {
                'high_risk_claims': high_fraud_claims,
                'avg_fraud_score': round(statistics.mean(fraud_scores) if fraud_scores else 0, 3)
            },
            'geography': dict(city_distribution)
        }

    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from values."""
        if len(values) < 2:
            return 'stable'

        # Simple linear trend
        n = len(values)
        if n < 2:
            return 'stable'

        x = list(range(n))
        slope = statistics.linear_regression(x, values)[0]

        if slope > 0.01:
            return 'increasing'
        elif slope < -0.01:
            return 'decreasing'
        else:
            return 'stable'

    def get_predictive_insights(self, db, user_id: Optional[int] = None) -> Dict:
        """Generate predictive analytics and recommendations for next week's disruptions."""
        insights = {
            'predictions': [],
            'recommendations': [],
            'alerts': [],
            'next_week_forecast': {}
        }

        if user_id:
            # Worker-specific predictive insights
            worker = db.execute('SELECT * FROM workers WHERE user_id=?', (user_id,)).fetchone()
            if worker:
                worker_dict = dict(worker)

                # Analyze historical claims and weather patterns
                recent_claims = db.execute(
                    "SELECT trigger_type, created_at FROM claims WHERE user_id = ? AND status = 'Approved' AND created_at >= datetime('now','-30 days')",
                    (user_id,)
                ).fetchall()

                # Predict based on location and historical patterns
                city = worker_dict.get('city', 'Unknown')
                latitude = worker_dict.get('latitude', 0)
                longitude = worker_dict.get('longitude', 0)

                # Mock weather-based predictions (in real impl, use weather API forecasts)
                predictions = []

                # Rain prediction based on monsoon season and location
                if latitude > 8 and latitude < 37 and longitude > 68 and longitude < 97:  # Indian subcontinent
                    predictions.append({
                        'type': 'Heavy Rain',
                        'probability': 0.75,
                        'expected_impact': 'High disruption likelihood',
                        'timeframe': 'Next 7 days',
                        'recommended_action': 'Monitor weather alerts'
                    })

                # AQI prediction for urban areas
                if city in ['Mumbai', 'Delhi', 'Bangalore', 'Chennai', 'Kolkata']:
                    predictions.append({
                        'type': 'Poor Air Quality',
                        'probability': 0.60,
                        'expected_impact': 'Medium disruption risk',
                        'timeframe': 'Next 3-5 days',
                        'recommended_action': 'Check AQI forecasts'
                    })

                # Heatwave prediction for summer months
                current_month = datetime.now().month
                if current_month in [3, 4, 5, 6]:  # Summer months
                    predictions.append({
                        'type': 'Extreme Heat',
                        'probability': 0.45,
                        'expected_impact': 'Moderate temperature risk',
                        'timeframe': 'Next 7 days',
                        'recommended_action': 'Stay hydrated during work hours'
                    })

                insights['predictions'] = predictions

                # Personalized recommendations
                if len(recent_claims) > 3:
                    insights['recommendations'].append({
                        'type': 'Risk Assessment',
                        'message': 'High claim frequency detected. Consider premium adjustment for better coverage.',
                        'priority': 'medium'
                    })

                if worker_dict.get('daily_income', 0) > 800:
                    insights['recommendations'].append({
                        'type': 'Coverage Optimization',
                        'message': 'Higher income bracket - consider increased coverage limits.',
                        'priority': 'low'
                    })

        else:
            # System-wide predictive insights for admin
            total_workers = db.execute("SELECT COUNT(*) FROM workers WHERE onboarding_complete=1").fetchone()[0]
            active_policies = db.execute("SELECT COUNT(*) FROM policies WHERE policy_status='Active'").fetchone()[0]

            # Predict system load based on historical patterns
            recent_triggers = db.execute(
                "SELECT COUNT(*) FROM trigger_events WHERE created_at >= datetime('now','-7 days')"
            ).fetchone()[0]

            # Next week forecast
            insights['next_week_forecast'] = {
                'expected_triggers': max(5, int(recent_triggers * 1.2)),  # 20% increase baseline
                'high_risk_zones': ['Mumbai', 'Delhi', 'Bangalore'],
                'peak_disruption_hours': '10 AM - 2 PM',
                'weather_alert_level': 'Moderate',
                'system_load_prediction': 'Normal' if recent_triggers < 20 else 'High'
            }

            # System-wide alerts
            if recent_triggers > 50:
                insights['alerts'].append({
                    'type': 'High Activity',
                    'message': 'Unusually high trigger activity detected. Prepare for increased claim volume.',
                    'priority': 'high'
                })

            if active_policies / max(1, total_workers) < 0.7:
                insights['alerts'].append({
                    'type': 'Low Engagement',
                    'message': 'Policy activation rate below 70%. Consider marketing campaigns.',
                    'priority': 'medium'
                })

            # Predictive recommendations
            insights['recommendations'].append({
                'type': 'Capacity Planning',
                'message': f'Based on current trends, prepare for {insights["next_week_forecast"]["expected_triggers"]} triggers next week.',
                'priority': 'medium'
            })

        return insights


# Global analytics instance
analytics_engine = AnalyticsEngine()


def get_worker_analytics(db, user_id: int, days: int = 30) -> Dict:
    """Convenience function for worker analytics."""
    return analytics_engine.get_worker_analytics(db, user_id, days)


def get_admin_analytics(db, days: int = 30) -> Dict:
    """Convenience function for admin analytics."""
    return analytics_engine.get_admin_analytics(db, days)


def get_predictive_insights(db, user_id: Optional[int] = None) -> Dict:
    """Convenience function for predictive insights."""
    return analytics_engine.get_predictive_insights(db, user_id)