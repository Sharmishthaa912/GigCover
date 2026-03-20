import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/screens/login_screen.dart';

class SplashScreen extends StatefulWidget {
  const SplashScreen({super.key});

  @override
  State<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends State<SplashScreen> {
  @override
  void initState() {
    super.initState();
    Future<void>.delayed(const Duration(seconds: 2), () {
      if (!mounted) return;
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF8E1),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.asset('assets/images/app_hero.png', height: 180, fit: BoxFit.cover),
            ),
            const SizedBox(height: 10),
            Text('GigCover AI', style: GoogleFonts.outfit(fontSize: 30, fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('Smart Risk Protection', style: GoogleFonts.poppins(color: Colors.black54)),
            const SizedBox(height: 20),
            const CircularProgressIndicator(color: Color(0xFFFFC107)),
          ],
        ),
      ),
    );
  }
}
