import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/screens/login_screen.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  bool loading = true;
  Map<String, dynamic> analytics = {};
  List<dynamic> claims = [];
  List<dynamic> users = [];
  List<dynamic> policies = [];
  final departmentController = TextEditingController();
  final categoryController = TextEditingController();

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await ApiService.dashboardData();
      final overview = await ApiService.adminOverview(
        department: departmentController.text,
        category: categoryController.text,
      );
      if (mounted) {
        setState(() {
          analytics = (data['analytics'] as Map<String, dynamic>?) ?? {};
          claims = (data['claims'] as List<dynamic>?) ?? [];
          users = (overview['users'] as List<dynamic>?) ?? [];
          policies = (overview['policies'] as List<dynamic>?) ?? [];
          loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final totalUsers = analytics['total_users'] ?? 0;
    final totalClaims = analytics['total_claims'] ?? 0;
    final totalPayouts = analytics['total_payouts'] ?? 0;
    final totalPremiums = (totalUsers is num ? totalUsers.toDouble() : 0) * 32;

    return Scaffold(
      appBar: AppBar(
        title: Text('Admin Dashboard', style: GoogleFonts.outfit(fontWeight: FontWeight.w600)),
        backgroundColor: Colors.transparent,
        actions: [
          IconButton(
            onPressed: () {
              ApiService.setToken(null);
              Navigator.pushAndRemoveUntil(context, MaterialPageRoute(builder: (_) => const LoginScreen()), (_) => false);
            },
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Row(
                  children: [
                    Expanded(child: _metric('Total Users', '$totalUsers', const Color(0xFFC4B5FD))),
                    const SizedBox(width: 10),
                    Expanded(child: _metric('Total Claims', '$totalClaims', const Color(0xFFBFDBFE))),
                  ],
                ),
                const SizedBox(height: 10),
                Row(
                  children: [
                    Expanded(child: _metric('Total Premiums', 'Rs ${totalPremiums.toStringAsFixed(2)}', const Color(0xFFBBF7D0))),
                    const SizedBox(width: 10),
                    Expanded(child: _metric('Total Payouts', 'Rs $totalPayouts', const Color(0xFFA7F3D0))),
                  ],
                ),
                const SizedBox(height: 16),
                SoftCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Filters', style: GoogleFonts.outfit(fontSize: 18, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                      TextField(
                        controller: departmentController,
                        decoration: const InputDecoration(labelText: 'Department / Zone', border: OutlineInputBorder()),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: categoryController,
                        decoration: const InputDecoration(labelText: 'Platform Category', border: OutlineInputBorder()),
                      ),
                      const SizedBox(height: 8),
                      GradientButton(label: 'Apply Filters', onPressed: load),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                SoftCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Analytics', style: GoogleFonts.outfit(fontSize: 20, fontWeight: FontWeight.w700)),
                      const SizedBox(height: 16),
                      SizedBox(
                        height: 220,
                        child: BarChart(
                          BarChartData(
                            borderData: FlBorderData(show: false),
                            gridData: const FlGridData(show: false),
                            titlesData: const FlTitlesData(show: true),
                            barGroups: [
                              _bar(0, (totalUsers as num).toDouble(), const Color(0xFFA78BFA)),
                              _bar(1, (totalClaims as num).toDouble(), const Color(0xFF93C5FD)),
                              _bar(2, (totalPayouts as num).toDouble() / 100, const Color(0xFF86EFAC)),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                SoftCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Employees (Platform / Risk / Claim Status)', style: GoogleFonts.outfit(fontSize: 18, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 10),
                      ...users.take(20).map((u) {
                        final user = u as Map<String, dynamic>;
                        final policy = policies.cast<Map<String, dynamic>?>().firstWhere(
                              (p) => p != null && p['user_id'] == user['id'],
                              orElse: () => null,
                            );
                        final userClaims = claims.where((c) => (c as Map<String, dynamic>)['user_id'] == user['id']).toList();
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 5),
                          child: Text(
                            '${user['name']} | Platform: ${policy?['delivery_platform'] ?? '-'} | Risk: ${policy?['zone_type'] ?? '-'} | Claim: ${userClaims.isNotEmpty ? 'Yes' : 'No'}',
                            style: GoogleFonts.poppins(fontSize: 13),
                          ),
                        );
                      }),
                    ],
                  ),
                ),
                const SizedBox(height: 16),
                SoftCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Recent Claims', style: GoogleFonts.outfit(fontSize: 18, fontWeight: FontWeight.w600)),
                      const SizedBox(height: 10),
                      ...claims.take(5).map((c) {
                        final claim = c as Map<String, dynamic>;
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 4),
                          child: Text(
                            '${claim['claim_id']} | ${claim['trigger_type']} | Rs ${claim['payout']}',
                            style: GoogleFonts.poppins(fontSize: 13),
                          ),
                        );
                      }),
                    ],
                  ),
                ),
              ],
            ),
    );
  }

  Widget _metric(String title, String value, Color color) {
    return SoftCard(
      color: color,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: GoogleFonts.poppins(fontSize: 12)),
          const SizedBox(height: 4),
          Text(value, style: GoogleFonts.outfit(fontSize: 18, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }

  BarChartGroupData _bar(int x, double value, Color color) {
    return BarChartGroupData(
      x: x,
      barRods: [
        BarChartRodData(toY: value, width: 20, borderRadius: BorderRadius.circular(6), color: color),
      ],
    );
  }
}
