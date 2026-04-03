import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/screens/admin_dashboard_screen.dart';
import 'package:gigcover_mobile/screens/onboarding_screen.dart';
import 'package:gigcover_mobile/screens/signup_screen.dart';
import 'package:gigcover_mobile/screens/worker_home_shell.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  bool loading = false;
  String? error;

  Future<void> login() async {
    final email = emailController.text.trim().toLowerCase();
    final password = passwordController.text;
    final emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

    if (email.isEmpty || password.isEmpty) {
      setState(() => error = 'Email and password are required.');
      return;
    }
    if (!emailRegex.hasMatch(email)) {
      setState(() => error = 'Please enter a valid email address.');
      return;
    }

    setState(() {
      loading = true;
      error = null;
    });

    try {
      final data = await ApiService.login(email: email, password: password);
      debugPrint('Login response: $data');

      ApiService.setToken(data['token'] as String?);
      final user =
          (data['user'] as Map<String, dynamic>? ?? <String, dynamic>{});
      final role = user['role'] as String? ?? 'Employee';
      final onboardingFlag = user['onboarding_complete'];
      final onboardingCompleted = onboardingFlag == true || onboardingFlag == 1;

      if (!mounted) return;
      if (role == 'Admin') {
        Navigator.pushReplacement(context,
            MaterialPageRoute(builder: (_) => const AdminDashboardScreen()));
      } else {
        final completed = onboardingCompleted;
        Navigator.pushReplacement(
          context,
          MaterialPageRoute(
              builder: (_) => completed
                  ? const WorkerHomeShell()
                  : const OnboardingScreen()),
        );
      }
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(18),
          child: Center(
            child: SingleChildScrollView(
              child: SoftCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    ClipRRect(
                      borderRadius: BorderRadius.circular(14),
                      child: Image.asset('assets/images/app_hero.png',
                          height: 170, fit: BoxFit.cover),
                    ),
                    const SizedBox(height: 12),
                    Text('GigCover AI',
                        style: GoogleFonts.outfit(
                            fontSize: 32, fontWeight: FontWeight.bold)),
                    const SizedBox(height: 8),
                    Text('Login to continue',
                        style:
                            GoogleFonts.poppins(color: Colors.grey.shade600)),
                    const SizedBox(height: 18),
                    AppTextField(
                        label: 'Email',
                        controller: emailController,
                        keyboardType: TextInputType.emailAddress),
                    const SizedBox(height: 12),
                    AppTextField(
                        label: 'Password',
                        controller: passwordController,
                        obscure: true),
                    if (error != null) ...[
                      const SizedBox(height: 8),
                      Text(error!,
                          style:
                              GoogleFonts.poppins(color: Colors.red.shade600)),
                    ],
                    const SizedBox(height: 16),
                    GradientButton(
                        label: loading ? 'Logging in...' : 'Login',
                        onPressed: loading ? () {} : login),
                    const SizedBox(height: 10),
                    TextButton(
                      onPressed: () {
                        Navigator.push(
                            context,
                            MaterialPageRoute(
                                builder: (_) => const SignupScreen()));
                      },
                      child: Text('No account? Signup',
                          style: GoogleFonts.poppins()),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
