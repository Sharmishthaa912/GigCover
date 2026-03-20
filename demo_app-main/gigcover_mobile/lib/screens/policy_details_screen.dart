import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class PolicyDetailsScreen extends StatefulWidget {
  const PolicyDetailsScreen({super.key});

  @override
  State<PolicyDetailsScreen> createState() => _PolicyDetailsScreenState();
}

class _PolicyDetailsScreenState extends State<PolicyDetailsScreen> {
  bool loading = true;
  Map<String, dynamic> worker = {};
  Map<String, dynamic> policy = {};

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await ApiService.dashboardData();
      if (mounted) {
        setState(() {
          worker = (data['worker'] as Map<String, dynamic>?) ?? {};
          policy = (data['policy'] as Map<String, dynamic>?) ?? {};
          loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Policy Details', style: GoogleFonts.outfit()), backgroundColor: Colors.transparent),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                SoftCard(child: _item('Risk Score', (worker['risk_score'] ?? 0).toString())),
                const SizedBox(height: 12),
                SoftCard(child: _item('Weekly Premium', 'Rs ${(policy['premium'] ?? worker['weekly_premium'] ?? 0)}')),
                const SizedBox(height: 12),
                SoftCard(child: _item('Coverage Amount', 'Rs ${(policy['coverage_amount'] ?? worker['coverage_amount'] ?? 0)}')),
                const SizedBox(height: 12),
                SoftCard(child: _item('Policy Status', (policy['policy_status'] ?? 'Inactive').toString())),
              ],
            ),
    );
  }

  Widget _item(String title, String value) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(title, style: GoogleFonts.poppins(fontWeight: FontWeight.w500)),
        Text(value, style: GoogleFonts.outfit(fontWeight: FontWeight.bold)),
      ],
    );
  }
}
