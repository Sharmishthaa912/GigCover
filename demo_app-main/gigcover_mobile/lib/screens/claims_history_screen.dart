import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class ClaimsHistoryScreen extends StatefulWidget {
  const ClaimsHistoryScreen({super.key});

  @override
  State<ClaimsHistoryScreen> createState() => _ClaimsHistoryScreenState();
}

class _ClaimsHistoryScreenState extends State<ClaimsHistoryScreen> {
  bool loading = true;
  List<dynamic> claims = [];

  @override
  void initState() {
    super.initState();
    loadClaims();
  }

  Future<void> loadClaims() async {
    try {
      final result = await ApiService.getClaims();
      if (mounted) {
        setState(() {
          claims = result.isNotEmpty ? result : _dummyClaims();
          loading = false;
        });
      }
    } catch (_) {
      if (mounted)
        setState(() {
          claims = _dummyClaims();
          loading = false;
        });
    }
  }

  List<Map<String, dynamic>> _dummyClaims() {
    return [
      {
        'claim_id': 'CLM-1001',
        'trigger_type': 'Heavy Rain',
        'lost_hours': 4,
        'payout': 1150.0,
        'status': 'Approved',
        'created_at': '2026-04-01T10:22:00Z'
      },
      {
        'claim_id': 'CLM-1002',
        'trigger_type': 'Low Visibility',
        'lost_hours': 3,
        'payout': 850.0,
        'status': 'Pending',
        'created_at': '2026-04-03T07:30:00Z'
      }
    ];
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: Text('Claims History', style: GoogleFonts.outfit()),
          backgroundColor: Colors.transparent),
      body: loading
          ? const Center(child: CircularProgressIndicator())
          : ListView.separated(
              padding: const EdgeInsets.all(16),
              itemBuilder: (_, index) {
                final claim = claims[index] as Map<String, dynamic>;
                return SoftCard(
                  color: const Color(0xFFF5F3FF),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Claim ID: ${claim['claim_id'] ?? '-'}',
                          style:
                              GoogleFonts.outfit(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 4),
                      Text('Trigger Type: ${claim['trigger_type'] ?? '-'}',
                          style: GoogleFonts.poppins()),
                      Text('Lost Hours: ${claim['lost_hours'] ?? '-'}',
                          style: GoogleFonts.poppins()),
                      Text('Payout: Rs ${claim['payout'] ?? '-'}',
                          style: GoogleFonts.poppins()),
                      Text('Status: ${claim['status'] ?? '-'}',
                          style: GoogleFonts.poppins()),
                    ],
                  ),
                );
              },
              separatorBuilder: (_, __) => const SizedBox(height: 12),
              itemCount: claims.length,
            ),
    );
  }
}
