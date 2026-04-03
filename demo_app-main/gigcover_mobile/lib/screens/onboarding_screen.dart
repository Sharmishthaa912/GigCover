import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:gigcover_mobile/screens/worker_home_shell.dart';
import 'package:gigcover_mobile/services/api_service.dart';
import 'package:gigcover_mobile/services/location_service.dart';
import 'package:gigcover_mobile/widgets/app_widgets.dart';

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key});

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  bool loading = false;
  String? error;

  final fullNameController = TextEditingController();
  final ageController = TextEditingController(text: '25');
  final emailController = TextEditingController();
  final cityController = TextEditingController();
  final manualLocationController = TextEditingController();
  final locationTextController = TextEditingController();
  final dailyIncomeController = TextEditingController(text: '500');
  final workingHoursController = TextEditingController(text: '8');
  final weeklyWorkingDaysController = TextEditingController(text: '6');

  String gender = 'Male';
  String workType = 'Delivery';
  String platformUsed = 'Swiggy';
  String workingShift = 'Day';
  String incomeDependency = 'Medium';
  String workingEnvironment = 'Outdoor';
  String zoneType = 'Urban';

  double latitude = 0;
  double longitude = 0;

  final _locationService = LocationService();

  Future<void> detectLocation() async {
    setState(() => error = null);
    try {
      final location = await _locationService.getCurrentLocation();
      latitude = location.latitude;
      longitude = location.longitude;

      final place = await _locationService.reverseGeocode(latitude, longitude);
      if ((place['city'] ?? '').isNotEmpty) {
        cityController.text = place['city'] ?? cityController.text;
      }
      if ((place['displayName'] ?? '').isNotEmpty) {
        locationTextController.text =
            place['displayName'] ?? locationTextController.text;
      }

      final weather = await ApiService.weatherRisk(
          latitude: latitude, longitude: longitude);
      final locationData = (weather['location'] as Map<String, dynamic>?) ?? {};
      cityController.text =
          locationData['city']?.toString() ?? cityController.text;
      locationTextController.text = locationData['display_name']?.toString() ??
          locationTextController.text;
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Location detected successfully.')));
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    }
  }

  Future<void> submit() async {
    final fullName = fullNameController.text.trim();
    final age = int.tryParse(ageController.text) ?? 0;
    final email = emailController.text.trim().toLowerCase();
    final city = cityController.text.trim();
    final manualLocation = manualLocationController.text.trim();
    final locationText = locationTextController.text.trim();
    final dailyIncome = double.tryParse(dailyIncomeController.text) ?? 0;
    final workingHours = double.tryParse(workingHoursController.text) ?? 0;
    final weeklyWorkingDays =
        int.tryParse(weeklyWorkingDaysController.text) ?? 0;
    final emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

    if (fullName.isEmpty || age <= 0 || dailyIncome <= 0) {
      setState(
          () => error = 'Please fill full name, valid age, and daily income.');
      return;
    }
    if (email.isNotEmpty && !emailRegex.hasMatch(email)) {
      setState(() => error = 'Please enter a valid email address.');
      return;
    }
    if (workingHours <= 0 || workingHours > 24) {
      setState(() => error = 'Working hours must be between 1 and 24.');
      return;
    }
    if (weeklyWorkingDays <= 0 || weeklyWorkingDays > 7) {
      setState(() => error = 'Weekly working days must be between 1 and 7.');
      return;
    }

    setState(() {
      loading = true;
      error = null;
    });

    try {
      final data = await ApiService.completeOnboarding(
        fullName: fullName,
        age: age,
        gender: gender,
        email: email,
        workType: workType,
        platformUsed: platformUsed,
        workingHours: workingHours,
        workingShift: workingShift,
        weeklyWorkingDays: weeklyWorkingDays,
        city: city,
        manualLocation: manualLocation,
        locationText: locationText,
        latitude: latitude,
        longitude: longitude,
        dailyIncome: dailyIncome,
        incomeDependency: incomeDependency,
        workingEnvironment: workingEnvironment,
        zoneType: zoneType,
      );
      debugPrint('Onboarding response: $data');

      if (!mounted) return;
      Navigator.pushAndRemoveUntil(
          context,
          MaterialPageRoute(builder: (_) => const WorkerHomeShell()),
          (_) => false);
    } catch (e) {
      setState(() => error = e.toString().replaceFirst('Exception: ', ''));
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
          title: Text('Onboarding Form', style: GoogleFonts.outfit()),
          backgroundColor: Colors.transparent),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            SoftCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Personal Info',
                      style: GoogleFonts.outfit(
                          fontWeight: FontWeight.bold, fontSize: 20)),
                  const SizedBox(height: 12),
                  AppTextField(
                      label: 'Full Name', controller: fullNameController),
                  const SizedBox(height: 10),
                  AppTextField(
                      label: 'Age',
                      controller: ageController,
                      keyboardType: TextInputType.number),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    initialValue: gender,
                    decoration: _fieldDecoration('Gender'),
                    items: const [
                      DropdownMenuItem(value: 'Male', child: Text('Male')),
                      DropdownMenuItem(value: 'Female', child: Text('Female')),
                      DropdownMenuItem(value: 'Other', child: Text('Other')),
                    ],
                    onChanged: (value) =>
                        setState(() => gender = value ?? 'Male'),
                  ),
                  const SizedBox(height: 10),
                  AppTextField(
                      label: 'Email',
                      controller: emailController,
                      keyboardType: TextInputType.emailAddress),
                ],
              ),
            ),
            const SizedBox(height: 12),
            SoftCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Work Details',
                      style: GoogleFonts.outfit(
                          fontWeight: FontWeight.bold, fontSize: 20)),
                  const SizedBox(height: 10),
                  _dropdown(
                      'Type of Work',
                      workType,
                      ['Delivery', 'Driver', 'Freelancer', 'Field Agent'],
                      (v) => workType = v),
                  const SizedBox(height: 10),
                  _dropdown(
                      'Platform Used',
                      platformUsed,
                      ['Swiggy', 'Zomato', 'Uber', 'Blinkit', 'Zepto'],
                      (v) => platformUsed = v),
                  const SizedBox(height: 10),
                  AppTextField(
                      label: 'Working Hours per Day',
                      controller: workingHoursController,
                      keyboardType: TextInputType.number),
                  const SizedBox(height: 10),
                  _dropdown('Working Shift', workingShift, ['Day', 'Night'],
                      (v) => workingShift = v),
                  const SizedBox(height: 10),
                  AppTextField(
                      label: 'Weekly Working Days',
                      controller: weeklyWorkingDaysController,
                      keyboardType: TextInputType.number),
                  const SizedBox(height: 10),
                  _dropdown('Working Environment', workingEnvironment,
                      ['Outdoor', 'Indoor'], (v) => workingEnvironment = v),
                ],
              ),
            ),
            const SizedBox(height: 12),
            SoftCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Location & Income',
                      style: GoogleFonts.outfit(
                          fontWeight: FontWeight.bold, fontSize: 20)),
                  const SizedBox(height: 10),
                  GradientButton(
                      label: 'Auto Detect Location', onPressed: detectLocation),
                  const SizedBox(height: 10),
                  AppTextField(label: 'City', controller: cityController),
                  const SizedBox(height: 10),
                  AppTextField(
                      label: 'Manual Location Input',
                      controller: manualLocationController),
                  const SizedBox(height: 10),
                  AppTextField(
                      label: 'Detected Place Name',
                      controller: locationTextController),
                  const SizedBox(height: 10),
                  AppTextField(
                      label: 'Average Daily Income',
                      controller: dailyIncomeController,
                      keyboardType: TextInputType.number),
                  const SizedBox(height: 10),
                  _dropdown('Dependency on Daily Income', incomeDependency,
                      ['Low', 'Medium', 'High'], (v) => incomeDependency = v),
                  const SizedBox(height: 10),
                  _dropdown('Zone Type', zoneType, ['Urban', 'Semi-Urban'],
                      (v) => zoneType = v),
                ],
              ),
            ),
            if (error != null) ...[
              const SizedBox(height: 8),
              Text(error!,
                  style: GoogleFonts.poppins(color: Colors.red.shade600)),
            ],
            const SizedBox(height: 14),
            GradientButton(
                label: loading ? 'Saving...' : 'Complete Onboarding',
                onPressed: loading ? () {} : submit),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }

  Widget _dropdown(String label, String value, List<String> options,
      void Function(String) onChanged) {
    return DropdownButtonFormField<String>(
      initialValue: value,
      decoration: _fieldDecoration(label),
      items: options
          .map((option) => DropdownMenuItem(value: option, child: Text(option)))
          .toList(),
      onChanged: (newValue) => setState(() => onChanged(newValue ?? value)),
    );
  }

  InputDecoration _fieldDecoration(String label) {
    return InputDecoration(
      labelText: label,
      filled: true,
      fillColor: Colors.white,
      border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14), borderSide: BorderSide.none),
    );
  }
}
