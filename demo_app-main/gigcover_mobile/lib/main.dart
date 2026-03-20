import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/screens/web_app_screen.dart';
import 'package:gigcover_mobile/services/api_service.dart';

void main() {
  runApp(const GigCoverApp());
}

class GigCoverApp extends StatelessWidget {
  const GigCoverApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'GigCover Mobile',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFFFFC107)),
        scaffoldBackgroundColor: const Color(0xFFF8F9FB),
        textTheme: GoogleFonts.poppinsTextTheme(),
        useMaterial3: true,
      ),
      home: const AppBootstrapScreen(),
    );
  }
}

class AppBootstrapScreen extends StatefulWidget {
  const AppBootstrapScreen({super.key});

  @override
  State<AppBootstrapScreen> createState() => _AppBootstrapScreenState();
}

class _AppBootstrapScreenState extends State<AppBootstrapScreen> {
  bool _ready = false;

  @override
  void initState() {
    super.initState();
    Future<void>(() async {
      await ApiService.hydrateToken();
      await Future<void>.delayed(const Duration(milliseconds: 1200));
      if (!mounted) return;
      setState(() => _ready = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_ready) {
      return const WebAppScreen();
    }

    return Scaffold(
      backgroundColor: const Color(0xFFFFF8E1),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.asset('assets/images/app_hero.png', height: 140, fit: BoxFit.cover),
            ),
            const SizedBox(height: 14),
            Text('GigCover AI', style: GoogleFonts.outfit(fontSize: 30, fontWeight: FontWeight.bold)),
            const SizedBox(height: 6),
            Text('Loading secure workspace...', style: GoogleFonts.poppins(color: Colors.black54)),
            const SizedBox(height: 18),
            const CircularProgressIndicator(color: Color(0xFFFFC107)),
          ],
        ),
      ),
    );
  }
}
