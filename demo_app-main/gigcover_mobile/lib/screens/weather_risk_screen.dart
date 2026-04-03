import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/services/location_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class WeatherRiskScreen extends StatefulWidget {
  const WeatherRiskScreen({super.key});

  @override
  State<WeatherRiskScreen> createState() => _WeatherRiskScreenState();
}

class _WeatherRiskScreenState extends State<WeatherRiskScreen> {
  bool loading = true;
  String? error;
  Map<String, dynamic>? result;

  final _locationService = LocationService();

  @override
  void initState() {
    super.initState();
    refresh();
  }

  Future<void> refresh() async {
    setState(() {
      loading = true;
      error = null;
    });

    try {
      final location = await _locationService.getCurrentLocation();
      debugPrint(
          'Weather screen location lat=${location.latitude}, lon=${location.longitude}');
      final data = await ApiService.weatherRisk(
        latitude: location.latitude,
        longitude: location.longitude,
      );
      debugPrint('Weather API payload keys: ${data.keys.toList()}');
      if (mounted) {
        setState(() {
          result = data;
          loading = false;
        });
      }
    } catch (e) {
      debugPrint('Weather fetch error: $e');
      if (mounted) {
        setState(() {
          final raw = e.toString().replaceFirst('Exception: ', '');
          debugPrint('Weather screen normalized error: $raw');
          if (raw.toLowerCase().contains('location')) {
            error = 'Enable location to fetch weather';
          } else if (raw.toLowerCase().contains('socket') ||
              raw.toLowerCase().contains('unreachable') ||
              raw.toLowerCase().contains('timeout')) {
            error =
                'Unable to fetch weather data. Check internet/backend connection.';
          } else {
            error = 'Unable to fetch weather data';
          }
          loading = false;
        });
      }
    }
  }

  String _claimMessageFromRisk(Map<String, dynamic> risk) {
    final label = (risk['risk']?.toString().toLowerCase() ??
        risk['risk_level']?.toString().toLowerCase() ??
        'low');
    if (label.contains('medium')) return 'Claim approved (moderate risk)';
    if (label.contains('high')) return 'Claim approved (high risk)';
    return 'Claim not eligible due to low risk';
  }

  @override
  Widget build(BuildContext context) {
    final location = (result?['location'] as Map<String, dynamic>?) ?? {};
    final weather = (result?['weather'] as Map<String, dynamic>?) ?? {};
    final risk = (result?['risk'] as Map<String, dynamic>?) ?? {};
    final reasons = (risk['reason'] as List<dynamic>? ?? [])
        .map((e) => e.toString())
        .toList();

    return Scaffold(
      appBar: AppBar(
        title: Text('Weather Risk',
            style: GoogleFonts.outfit(fontWeight: FontWeight.w600)),
        backgroundColor: Colors.transparent,
      ),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : error != null
              ? Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SoftCard(
                        color: const Color(0xFFFFF1F2),
                        child: Text(error!,
                            style: GoogleFonts.poppins(
                                color: Colors.red.shade700)),
                      ),
                      const SizedBox(height: 12),
                      GradientButton(label: 'Retry', onPressed: refresh),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: refresh,
                  child: ListView(
                    padding: const EdgeInsets.all(16),
                    children: [
                      SoftCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Current Location',
                                style: GoogleFonts.outfit(
                                    fontSize: 18, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            Text(location['display_name']?.toString() ?? '-',
                                style: GoogleFonts.poppins()),
                            Text(
                              'Lat: ${(location['latitude'] ?? 0).toString()} | Lon: ${(location['longitude'] ?? 0).toString()}',
                              style: GoogleFonts.poppins(
                                  fontSize: 12, color: Colors.black54),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      SoftCard(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Weather Details',
                                style: GoogleFonts.outfit(
                                    fontSize: 18, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            _line('Temperature',
                                '${weather['temperature'] ?? '-'} C'),
                            _line('Humidity', '${weather['humidity'] ?? '-'}%'),
                            _line('Wind Speed',
                                '${weather['wind_speed'] ?? '-'} m/s'),
                            _line('Visibility',
                                '${weather['visibility'] ?? '-'} m'),
                          ],
                        ),
                      ),
                      const SizedBox(height: 12),
                      SoftCard(
                        color: const Color(0xFFFFF8E1),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Risk Summary',
                                style: GoogleFonts.outfit(
                                    fontSize: 18, fontWeight: FontWeight.bold)),
                            const SizedBox(height: 8),
                            _line('Risk Score', '${risk['risk_score'] ?? '-'}'),
                            _line('Risk Level',
                                risk['risk_level']?.toString() ?? 'Low'),
                            const SizedBox(height: 8),
                            Text(
                              risk['recommendation']?.toString() ??
                                  'Keep monitoring weather conditions.',
                              style: GoogleFonts.poppins(),
                            ),
                            if (reasons.isNotEmpty) ...[
                              const SizedBox(height: 8),
                              ...reasons.map((reason) => Text('- $reason',
                                  style: GoogleFonts.poppins(fontSize: 13))),
                            ],
                            const SizedBox(height: 10),
                            Text(
                              _claimMessageFromRisk(risk),
                              style: GoogleFonts.poppins(
                                  fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
    );
  }

  Widget _line(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: GoogleFonts.poppins(fontWeight: FontWeight.w500)),
          Text(value, style: GoogleFonts.outfit(fontWeight: FontWeight.bold)),
        ],
      ),
    );
  }
}
