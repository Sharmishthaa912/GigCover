import 'package:flutter/material.dart';
import 'package:gigcover_mobile/screens/dashboard_screen.dart';
import 'package:gigcover_mobile/screens/parametric_screen.dart';
import 'package:gigcover_mobile/screens/payments_screen.dart';
import 'package:gigcover_mobile/screens/profile_screen.dart';
import 'package:gigcover_mobile/screens/weather_risk_screen.dart';

class WorkerHomeShell extends StatefulWidget {
  const WorkerHomeShell({super.key});

  @override
  State<WorkerHomeShell> createState() => _WorkerHomeShellState();
}

class _WorkerHomeShellState extends State<WorkerHomeShell> {
  int _index = 0;

  final _screens = const [
    DashboardScreen(),
    ParametricScreen(),
    WeatherRiskScreen(),
    PaymentsScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(index: _index, children: _screens),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (value) => setState(() => _index = value),
        destinations: const [
          NavigationDestination(icon: Icon(Icons.dashboard_rounded), label: 'Dashboard'),
          NavigationDestination(icon: Icon(Icons.bolt_rounded), label: 'Parametric'),
          NavigationDestination(icon: Icon(Icons.cloud_rounded), label: 'Weather'),
          NavigationDestination(icon: Icon(Icons.payments_rounded), label: 'Payments'),
          NavigationDestination(icon: Icon(Icons.person_rounded), label: 'Profile'),
        ],
      ),
    );
  }
}
