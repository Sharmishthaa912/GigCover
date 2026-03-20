import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class ClaimSimulationScreen extends StatefulWidget {
  const ClaimSimulationScreen({super.key});

  @override
  State<ClaimSimulationScreen> createState() => _ClaimSimulationScreenState();
}

class _ClaimSimulationScreenState extends State<ClaimSimulationScreen> {
  bool loading = false;
  Map<String, dynamic>? claim;
  String? message;

  Future<void> simulate() async {
    setState(() {
      loading = true;
      message = null;
    });

    try {
      final data = await ApiService.simulateRainfall();
      setState(() {
        claim = (data['claim'] as Map<String, dynamic>?);
        message = data['message']?.toString();
      });
    } catch (e) {
      setState(() {
        message = e.toString().replaceFirst('Exception: ', '');
      });
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Claim Simulation', style: GoogleFonts.outfit()), backgroundColor: Colors.transparent),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: ListView(
          children: [
            GradientButton(label: loading ? 'Simulating...' : 'Simulate Rainfall', onPressed: loading ? () {} : simulate),
            const SizedBox(height: 16),
            if (message != null)
              SoftCard(
                color: const Color(0xFFEFF6FF),
                child: Text(message!, style: GoogleFonts.poppins(fontWeight: FontWeight.w600)),
              ),
            const SizedBox(height: 12),
            if (claim != null)
              SoftCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Claim ID: ${claim!['claim_id'] ?? '-'}', style: GoogleFonts.poppins()),
                    Text('Lost Hours: ${claim!['lost_hours'] ?? '-'}', style: GoogleFonts.poppins()),
                    Text('Payout Amount: Rs ${claim!['payout'] ?? '-'}', style: GoogleFonts.poppins()),
                    Text('Status: ${claim!['status'] ?? '-'}', style: GoogleFonts.poppins()),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
