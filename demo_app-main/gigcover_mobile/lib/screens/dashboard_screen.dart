import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/screens/claim_simulation_screen.dart';
import 'package:gigcover_mobile/screens/claims_history_screen.dart';
import 'package:gigcover_mobile/screens/login_screen.dart';
import 'package:gigcover_mobile/screens/policy_details_screen.dart';
import 'package:gigcover_mobile/screens/weather_risk_screen.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool loading = true;
  Map<String, dynamic> data = {};
  Map<String, dynamic>? weatherRisk;
  bool claiming = false;

  @override
  void initState() {
    super.initState();
    fetchData();
  }

  Future<void> fetchData() async {
    try {
      final dashboard = await ApiService.dashboardData();
      final worker = (dashboard['worker'] as Map<String, dynamic>?) ?? {};

      Map<String, dynamic>? weatherPayload;
      final lat = (worker['latitude'] ?? 0) as num;
      final lon = (worker['longitude'] ?? 0) as num;
      if (lat != 0 && lon != 0) {
        try {
          weatherPayload = await ApiService.weatherRisk(latitude: lat.toDouble(), longitude: lon.toDouble());
        } catch (_) {
          weatherPayload = null;
        }
      }

      if (mounted) {
        setState(() {
          data = dashboard;
          weatherRisk = weatherPayload;
          loading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final worker = (data['worker'] as Map<String, dynamic>?) ?? {};
    final claims = (data['claims'] as List<dynamic>?) ?? [];
    final weather = (weatherRisk?['weather'] as Map<String, dynamic>?) ?? {};
    final risk = (weatherRisk?['risk'] as Map<String, dynamic>?) ?? {};
    final location = (weatherRisk?['location'] as Map<String, dynamic>?) ?? {};
    final riskLabel = (risk['risk']?.toString().toLowerCase() ?? risk['risk_level']?.toString().toLowerCase() ?? 'low').trim();
    final canClaim = riskLabel == 'medium' || riskLabel == 'high';

    String claimMessageFromRisk(String value) {
      if (value == 'medium') return 'Claim approved (moderate risk)';
      if (value == 'high') return 'Claim approved (high risk)';
      return 'Claim not eligible due to low risk';
    }

    return Scaffold(
      appBar: AppBar(
        title: Text('Worker Dashboard', style: GoogleFonts.outfit(fontWeight: FontWeight.w600)),
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
          : RefreshIndicator(
              onRefresh: fetchData,
              child: ListView(
                padding: const EdgeInsets.all(16),
                children: [
                  SoftCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Welcome, ${worker['full_name'] ?? 'Worker'}', style: GoogleFonts.outfit(fontSize: 22, fontWeight: FontWeight.w700)),
                        const SizedBox(height: 8),
                        Text('Location: ${location['display_name'] ?? worker['location_text'] ?? 'Not detected'}', style: GoogleFonts.poppins()),
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Expanded(child: _dashboardCard('Temperature', '${weather['temperature'] ?? '-'} C', const Color(0xFFFFF8E1))),
                            const SizedBox(width: 10),
                            Expanded(child: _dashboardCard('Humidity', '${weather['humidity'] ?? '-'}%', const Color(0xFFFFF8E1))),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Expanded(child: _dashboardCard('Wind Speed', '${weather['wind_speed'] ?? '-'} m/s', const Color(0xFFFFF8E1))),
                            const SizedBox(width: 10),
                            Expanded(child: _dashboardCard('Visibility', '${weather['visibility'] ?? '-'} m', const Color(0xFFFFF8E1))),
                          ],
                        ),
                        const SizedBox(height: 10),
                        Text('Risk Level: ${risk['risk_level'] ?? data['risk_category'] ?? 'Low'}', style: GoogleFonts.poppins(fontWeight: FontWeight.w600)),
                        Text('Weekly Premium: Rs ${(worker['weekly_premium'] ?? 0)}', style: GoogleFonts.poppins(fontWeight: FontWeight.w600)),
                        const SizedBox(height: 12),
                        GradientButton(
                          label: claiming ? 'Submitting...' : 'Claim Policy',
                          onPressed: (!canClaim || claiming)
                              ? () {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    SnackBar(content: Text(claimMessageFromRisk(riskLabel))),
                                  );
                                }
                              : () async {
                                  final messenger = ScaffoldMessenger.of(context);
                                  setState(() => claiming = true);
                                  try {
                                    final riskScore = (risk['risk_score'] as num?)?.toDouble();
                                    final claim = await ApiService.claimPolicyNow(risk: riskLabel, riskScore: riskScore);
                                    if (!mounted) return;
                                    final message = claim['message']?.toString() ?? claimMessageFromRisk(riskLabel);
                                    final claimStatus = claim['claim_status']?.toString() ?? '-';
                                    messenger.showSnackBar(
                                      SnackBar(content: Text('$message (Status: $claimStatus)')),
                                    );
                                    await fetchData();
                                  } catch (e) {
                                    if (!mounted) return;
                                    messenger.showSnackBar(
                                      SnackBar(content: Text(e.toString().replaceFirst('Exception: ', ''))),
                                    );
                                  } finally {
                                    if (mounted) setState(() => claiming = false);
                                  }
                                },
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(child: _dashboardCard('Worker Profile', worker['full_name']?.toString() ?? '-', const Color(0xFFC4B5FD))),
                      const SizedBox(width: 12),
                      Expanded(child: _dashboardCard('Risk Score', (worker['risk_score'] ?? 0).toString(), const Color(0xFFBFDBFE))),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Expanded(child: _dashboardCard('Weekly Premium', 'Rs ${(worker['weekly_premium'] ?? 0).toString()}', const Color(0xFFBBF7D0))),
                      const SizedBox(width: 12),
                      Expanded(child: _dashboardCard('Coverage Amount', 'Rs ${(worker['coverage_amount'] ?? 0).toString()}', const Color(0xFFC4B5FD))),
                    ],
                  ),
                  const SizedBox(height: 12),
                  SoftCard(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('Claims History', style: GoogleFonts.outfit(fontSize: 20, fontWeight: FontWeight.w600)),
                        const SizedBox(height: 8),
                        Text('Total Claims: ${claims.length}', style: GoogleFonts.poppins()),
                      ],
                    ),
                  ),
                  const SizedBox(height: 14),
                  GradientButton(
                    label: 'Policy Details',
                    onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const PolicyDetailsScreen())),
                  ),
                  const SizedBox(height: 10),
                  GradientButton(
                    label: 'Simulate Rainfall Claim',
                    onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ClaimSimulationScreen())),
                  ),
                  const SizedBox(height: 10),
                  GradientButton(
                    label: 'View Claims History',
                    onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const ClaimsHistoryScreen())),
                  ),
                  const SizedBox(height: 10),
                  GradientButton(
                    label: 'Weather Risk Detection',
                    onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => const WeatherRiskScreen())),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _dashboardCard(String title, String value, Color color) {
    return SoftCard(
      color: color,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: GoogleFonts.poppins(fontSize: 12, color: Colors.black54)),
          const SizedBox(height: 6),
          Text(value, style: GoogleFonts.outfit(fontSize: 20, fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
