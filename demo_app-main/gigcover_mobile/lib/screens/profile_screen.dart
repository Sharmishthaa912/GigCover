import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool loading = true;
  bool saving = false;
  String? error;

  final nameController = TextEditingController();
  final cityController = TextEditingController();
  final locationController = TextEditingController();

  Map<String, dynamic> policy = {};

  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final data = await ApiService.profile();
      final user = (data['user'] as Map<String, dynamic>?) ?? {};
      final worker = (data['worker'] as Map<String, dynamic>?) ?? {};
      policy = (data['policy'] as Map<String, dynamic>?) ?? {};

      nameController.text = user['name']?.toString() ?? '';
      cityController.text = worker['city']?.toString() ?? '';
      locationController.text = worker['location_text']?.toString() ?? '';

      if (mounted) setState(() => loading = false);
    } catch (e) {
      if (mounted) {
        setState(() {
          loading = false;
          error = e.toString().replaceFirst('Exception: ', '');
        });
      }
    }
  }

  Future<void> save() async {
    setState(() {
      saving = true;
      error = null;
    });

    try {
      await ApiService.updateProfile(
        name: nameController.text.trim(),
        city: cityController.text.trim(),
        locationText: locationController.text.trim(),
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Profile updated successfully.')));
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Center(child: CircularProgressIndicator());
    }

    return RefreshIndicator(
      onRefresh: load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('My Profile', style: GoogleFonts.outfit(fontSize: 24, fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          SoftCard(
            child: Column(
              children: [
                AppTextField(label: 'Name', controller: nameController),
                const SizedBox(height: 10),
                AppTextField(label: 'City', controller: cityController),
                const SizedBox(height: 10),
                AppTextField(label: 'Location', controller: locationController),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SoftCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Policy Details', style: GoogleFonts.outfit(fontWeight: FontWeight.w700, fontSize: 18)),
                const SizedBox(height: 8),
                Text('Status: ${policy['policy_status'] ?? 'Inactive'}', style: GoogleFonts.poppins()),
                Text('Premium: Rs ${policy['premium'] ?? 0}', style: GoogleFonts.poppins()),
                Text('Coverage: Rs ${policy['coverage_amount'] ?? 0}', style: GoogleFonts.poppins()),
              ],
            ),
          ),
          if (error != null) ...[
            const SizedBox(height: 10),
            Text(error!, style: GoogleFonts.poppins(color: Colors.red.shade600)),
          ],
          const SizedBox(height: 12),
          GradientButton(label: saving ? 'Saving...' : 'Save Profile', onPressed: saving ? () {} : save),
        ],
      ),
    );
  }
}
