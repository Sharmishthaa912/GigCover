import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/screens/login_screen.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class SignupScreen extends StatefulWidget {
  const SignupScreen({super.key});

  @override
  State<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends State<SignupScreen> {
  final nameController = TextEditingController();
  final emailController = TextEditingController();
  final passwordController = TextEditingController();
  String role = 'Employee';
  bool loading = false;
  String? error;

  Future<void> signup() async {
    final name = nameController.text.trim();
    final email = emailController.text.trim().toLowerCase();
    final password = passwordController.text;
    final emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

    if (name.isEmpty || email.isEmpty || password.isEmpty) {
      setState(() => error = 'Name, email and password are required.');
      return;
    }
    if (!emailRegex.hasMatch(email)) {
      setState(() => error = 'Please enter a valid email address.');
      return;
    }
    if (password.length < 8) {
      setState(() => error = 'Password must be at least 8 characters long.');
      return;
    }

    setState(() {
      loading = true;
      error = null;
    });

    try {
      final data = await ApiService.signup(name: name, email: email, password: password, role: role);
      print('Signup response: $data');

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Signup successful. Please login to continue.')),
      );
      Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F3FF),
      appBar: AppBar(backgroundColor: Colors.transparent, elevation: 0),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: SingleChildScrollView(
          child: SoftCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text('Create Account', style: GoogleFonts.outfit(fontSize: 28, fontWeight: FontWeight.bold)),
                const SizedBox(height: 16),
                AppTextField(label: 'Name', controller: nameController),
                const SizedBox(height: 12),
                AppTextField(label: 'Email', controller: emailController, keyboardType: TextInputType.emailAddress),
                const SizedBox(height: 12),
                AppTextField(label: 'Password', controller: passwordController, obscure: true),
                const SizedBox(height: 12),
                DropdownButtonFormField<String>(
                  initialValue: role,
                  decoration: InputDecoration(
                    labelText: 'Role',
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
                  ),
                  items: const [
                    DropdownMenuItem(value: 'Employee', child: Text('Employee')),
                    DropdownMenuItem(value: 'Admin', child: Text('Admin')),
                  ],
                  onChanged: (value) => setState(() => role = value ?? 'Employee'),
                ),
                if (error != null) ...[
                  const SizedBox(height: 8),
                  Text(error!, style: GoogleFonts.poppins(color: Colors.red.shade600)),
                ],
                const SizedBox(height: 16),
                GradientButton(label: loading ? 'Creating account...' : 'Signup', onPressed: loading ? () {} : signup),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
