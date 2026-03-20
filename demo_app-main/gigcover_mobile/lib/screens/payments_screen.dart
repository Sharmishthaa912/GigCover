import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class PaymentsScreen extends StatefulWidget {
  const PaymentsScreen({super.key});

  @override
  State<PaymentsScreen> createState() => _PaymentsScreenState();
}

class _PaymentsScreenState extends State<PaymentsScreen> {
  bool loading = true;
  bool paying = false;
  String? error;
  Map<String, dynamic>? latestPayment;
  List<dynamic> history = [];

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final dashboard = await ApiService.dashboardData();
      final payments = await ApiService.paymentHistory();
      if (mounted) {
        setState(() {
          latestPayment = dashboard['premium_payment'] as Map<String, dynamic>?;
          history = payments;
          loading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.toString().replaceFirst('Exception: ', '');
        });
      }
    }
  }

  Future<void> pay() async {
    setState(() {
      paying = true;
      error = null;
    });

    try {
      final res = await ApiService.payWeeklyPremium();
      if (!mounted) return;
      setState(() {
        latestPayment = (res['payment'] as Map<String, dynamic>?);
      });
      await load();
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Weekly premium paid.')));
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => paying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Center(child: CircularProgressIndicator());
    }

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Payments', style: GoogleFonts.outfit(fontSize: 24, fontWeight: FontWeight.bold)),
        const SizedBox(height: 12),
        SoftCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Latest Payment', style: GoogleFonts.outfit(fontWeight: FontWeight.w700, fontSize: 18)),
              const SizedBox(height: 8),
              Text('Amount: Rs ${latestPayment?['amount'] ?? '-'}', style: GoogleFonts.poppins()),
              Text('Status: ${latestPayment?['status'] ?? 'Pending'}', style: GoogleFonts.poppins()),
              Text('Next Due Date: ${latestPayment?['next_due_date'] ?? 'N/A'}', style: GoogleFonts.poppins()),
            ],
          ),
        ),
        const SizedBox(height: 12),
        GradientButton(label: paying ? 'Processing...' : 'Pay Weekly Premium', onPressed: paying ? () {} : pay),
        if (error != null) ...[
          const SizedBox(height: 8),
          Text(error!, style: GoogleFonts.poppins(color: Colors.red.shade600)),
        ],
        const SizedBox(height: 14),
        Text('Payment History', style: GoogleFonts.outfit(fontWeight: FontWeight.w700, fontSize: 18)),
        const SizedBox(height: 8),
        ...history.map((item) {
          final payment = item as Map<String, dynamic>;
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: SoftCard(
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('Rs ${payment['amount']}', style: GoogleFonts.outfit(fontWeight: FontWeight.bold)),
                  Text(payment['paid_on']?.toString().split('T').first ?? '', style: GoogleFonts.poppins(fontSize: 12)),
                ],
              ),
            ),
          );
        }),
      ],
    );
  }
}
