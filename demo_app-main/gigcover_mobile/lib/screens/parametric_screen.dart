import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/location_service.dart';

class ParametricScreen extends StatefulWidget {
  const ParametricScreen({super.key});

  @override
  State<ParametricScreen> createState() => _ParametricScreenState();
}

class _ParametricScreenState extends State<ParametricScreen> {
  bool _loading = false;
  Map<String, dynamic>? _result;
  List<dynamic> _transactions = [];
  List<dynamic> _triggerEvents = [];
  String? _error;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory() async {
    try {
      final txns = await ApiService.parametricTransactions();
      final evts = await ApiService.parametricTriggerEvents();
      if (mounted)
        setState(() {
          _transactions = txns.isNotEmpty ? txns : _dummyTransactions();
          _triggerEvents = evts;
        });
    } catch (_) {
      if (mounted)
        setState(() {
          _transactions = _dummyTransactions();
          _triggerEvents = [];
        });
    }
  }

  List<Map<String, dynamic>> _dummyTransactions() {
    return [
      {
        'txn_type': 'premium',
        'amount': 220.0,
        'method': 'UPI',
        'status': 'Success',
        'gateway_ref': 'UPI-9BXY123',
        'created_at': '2026-04-01T11:00:00Z'
      },
      {
        'txn_type': 'payout',
        'amount': 1150.0,
        'method': 'IMPS',
        'status': 'Success',
        'gateway_ref': 'IMPS-2LMN987',
        'created_at': '2026-04-02T15:30:00Z'
      }
    ];
  }

  Future<void> _runTrigger() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      double? lat, lon;
      try {
        final pos = await LocationService().getCurrentLocation();
        lat = pos.latitude;
        lon = pos.longitude;
        await ApiService.logActivity(
            latitude: lat, longitude: lon, platformActive: true);
      } catch (_) {}

      final data =
          await ApiService.parametricTrigger(latitude: lat, longitude: lon);
      setState(() {
        _result = data;
      });

      if (!mounted) return;
      if (data['triggered'] != true) {
        _showSnack('No parametric thresholds breached right now.', Colors.blue);
      } else if (data['eligible'] == false) {
        _showSnack(data['reason'] ?? 'Not eligible for payout.', Colors.orange);
      } else {
        final results = (data['results'] as List? ?? []);
        final approved =
            results.where((r) => r['decision'] == 'Approved').toList();
        if (approved.isNotEmpty) {
          final total = approved.fold<double>(
              0, (s, r) => s + (r['payout'] as num).toDouble());
          _showSnack(
              '${approved.length} trigger(s) fired. Payout ₹${total.toStringAsFixed(2)} initiated!',
              Colors.green);
        } else {
          _showSnack('Triggers evaluated. Check results below.', Colors.orange);
        }
      }
      await _loadHistory();
    } catch (e) {
      setState(() {
        _error = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted)
        setState(() {
          _loading = false;
        });
    }
  }

  void _showSnack(String msg, Color color) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
          content: Text(msg),
          backgroundColor: color,
          duration: const Duration(seconds: 4)),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: const Text('Parametric Insurance'),
          backgroundColor: const Color(0xFFFFC107)),
      body: RefreshIndicator(
        onRefresh: _loadHistory,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _TriggerCard(loading: _loading, onTap: _runTrigger),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                    color: Colors.red.shade50,
                    borderRadius: BorderRadius.circular(12)),
                child: Text(_error!, style: const TextStyle(color: Colors.red)),
              ),
            ],
            if (_result != null) ...[
              const SizedBox(height: 16),
              _ResultCard(result: _result!),
            ],
            if (_triggerEvents.isNotEmpty) ...[
              const SizedBox(height: 16),
              _SectionHeader('Recent Trigger Events'),
              ..._triggerEvents.take(5).map((e) => _TriggerEventTile(event: e)),
            ],
            if (_transactions.isNotEmpty) ...[
              const SizedBox(height: 16),
              _SectionHeader('Transaction History'),
              ..._transactions.take(10).map((t) => _TransactionTile(txn: t)),
            ],
          ],
        ),
      ),
    );
  }
}

class _TriggerCard extends StatelessWidget {
  final bool loading;
  final VoidCallback onTap;
  const _TriggerCard({required this.loading, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Zero-Touch Parametric Payout',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const SizedBox(height: 6),
          const Text(
            'System checks live AQI, rain, wind, and visibility against your policy thresholds. '
            'If breached, payout is auto-processed — no manual claim needed.',
            style: TextStyle(fontSize: 13, color: Colors.black54),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: loading ? null : onTap,
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFFFC107),
                foregroundColor: Colors.black,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12)),
              ),
              child: loading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.black))
                  : const Text('Run Parametric Trigger Check',
                      style: TextStyle(fontWeight: FontWeight.bold)),
            ),
          ),
        ]),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  final Map<String, dynamic> result;
  const _ResultCard({required this.result});

  @override
  Widget build(BuildContext context) {
    final results = (result['results'] as List? ?? []);
    final bcr = result['bcr'] as Map? ?? {};
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Trigger Results',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 8),
          _InfoRow('Triggered', result['triggered'] == true ? 'Yes' : 'No'),
          _InfoRow('Eligible', result['eligible'] == false ? 'No' : 'Yes'),
          if (result['aqi'] != null) _InfoRow('AQI', '${result['aqi']}'),
          if (result['fraud_score'] != null)
            _InfoRow('Fraud Score', '${result['fraud_score']}'),
          if (bcr['bcr'] != null)
            _InfoRow('BCR', '${bcr['bcr']} (${bcr['status'] ?? ''})'),
          if ((result['fraud_flags'] as List? ?? []).isNotEmpty) ...[
            const SizedBox(height: 6),
            Container(
              padding: const EdgeInsets.all(8),
              decoration: BoxDecoration(
                  color: Colors.red.shade50,
                  borderRadius: BorderRadius.circular(8)),
              child: Text(
                  'Fraud flags: ${(result['fraud_flags'] as List).join(', ')}',
                  style: const TextStyle(color: Colors.red, fontSize: 12)),
            ),
          ],
          if (results.isNotEmpty) ...[
            const SizedBox(height: 12),
            ...results
                .map((r) => _TriggerResultTile(r: r as Map<String, dynamic>)),
          ],
          if (result['reason'] != null) ...[
            const SizedBox(height: 8),
            Text(result['reason'],
                style: const TextStyle(color: Colors.orange, fontSize: 13)),
          ],
        ]),
      ),
    );
  }
}

class _TriggerResultTile extends StatelessWidget {
  final Map<String, dynamic> r;
  const _TriggerResultTile({required this.r});

  @override
  Widget build(BuildContext context) {
    final decision = r['decision'] as String? ?? '';
    final color = decision == 'Approved'
        ? Colors.green.shade50
        : decision == 'Blocked'
            ? Colors.red.shade50
            : Colors.grey.shade100;
    final textColor = decision == 'Approved'
        ? Colors.green.shade800
        : decision == 'Blocked'
            ? Colors.red.shade800
            : Colors.grey.shade700;
    return Container(
      margin: const EdgeInsets.only(top: 8),
      padding: const EdgeInsets.all(10),
      decoration:
          BoxDecoration(color: color, borderRadius: BorderRadius.circular(10)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('${r['trigger_type']} — $decision',
            style: TextStyle(fontWeight: FontWeight.bold, color: textColor)),
        if (r['claim_id'] != null)
          Text(
              'Claim: ${r['claim_id']}  |  Payout: ₹${(r['payout'] as num?)?.toStringAsFixed(2) ?? '0'}',
              style: const TextStyle(fontSize: 12)),
        if (r['transaction'] != null &&
            (r['transaction'] as Map)['gateway_ref'] != null)
          Text('Ref: ${(r['transaction'] as Map)['gateway_ref']}',
              style: const TextStyle(fontSize: 11, color: Colors.black45)),
        if (r['reason'] != null)
          Text(r['reason'],
              style: const TextStyle(fontSize: 12, color: Colors.black54)),
      ]),
    );
  }
}

class _TriggerEventTile extends StatelessWidget {
  final dynamic event;
  const _TriggerEventTile({required this.event});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      dense: true,
      leading: const Icon(Icons.bolt, color: Color(0xFFFFC107)),
      title: Text('${event['trigger_type']} — ${event['status']}'),
      subtitle: Text(
          'Observed: ${event['observed_value']}  Threshold: ${event['threshold_value']}'),
      trailing: Text((event['triggered_at'] as String? ?? '').substring(0, 10),
          style: const TextStyle(fontSize: 11, color: Colors.black45)),
    );
  }
}

class _TransactionTile extends StatelessWidget {
  final dynamic txn;
  const _TransactionTile({required this.txn});

  @override
  Widget build(BuildContext context) {
    final status = txn['status'] as String? ?? '';
    final color = status == 'Success'
        ? Colors.green
        : status == 'Failed'
            ? Colors.red
            : Colors.grey;
    return ListTile(
      dense: true,
      leading: Icon(
          txn['txn_type'] == 'payout' ? Icons.payments : Icons.receipt_long,
          color: color),
      title: Text(
          '${txn['txn_type']?.toString().toUpperCase() ?? ''} — ₹${(txn['amount'] as num?)?.toStringAsFixed(2) ?? '0'}'),
      subtitle: Text('${txn['method']}  ${txn['gateway_ref'] ?? ''}'),
      trailing: Text(status,
          style: TextStyle(
              color: color, fontWeight: FontWeight.bold, fontSize: 12)),
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  const _SectionHeader(this.title);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(title,
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
      );
}

class _InfoRow extends StatelessWidget {
  final String label, value;
  const _InfoRow(this.label, this.value);

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Row(children: [
          Text('$label: ',
              style: const TextStyle(color: Colors.black54, fontSize: 13)),
          Text(value,
              style:
                  const TextStyle(fontWeight: FontWeight.w600, fontSize: 13)),
        ]),
      );
}
