import 'dart:async';

import 'package:geocoding/geocoding.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart';

class AppLocation {
  final double latitude;
  final double longitude;

  const AppLocation({required this.latitude, required this.longitude});
}

class LocationService {
  Future<void> _ensureRuntimePermission() async {
    final current = await Permission.locationWhenInUse.status;
    if (current.isGranted) return;

    final requested = await Permission.locationWhenInUse.request();
    if (requested.isGranted) return;

    if (requested.isPermanentlyDenied) {
      await openAppSettings();
      throw Exception('Enable location to fetch weather. Permission is permanently denied in app settings.');
    }

    throw Exception('Enable location to fetch weather. Location permission is required.');
  }

  /// Requests runtime location access and returns the latest GPS coordinate.
  Future<AppLocation> getCurrentLocation() async {
    // Geolocator permission flow first (plugin-native), then permission_handler fallback.
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    if (permission == LocationPermission.deniedForever) {
      await Geolocator.openAppSettings();
      throw Exception('Enable location to fetch weather. Permission is permanently denied in app settings.');
    }
    if (permission == LocationPermission.denied || permission == LocationPermission.unableToDetermine) {
      await _ensureRuntimePermission();
    }

    // Fail fast if device-level location services are turned off.
    var serviceEnabled = await Geolocator.isLocationServiceEnabled();
    if (!serviceEnabled) {
      await Geolocator.openLocationSettings();
      await Future<void>.delayed(const Duration(seconds: 2));
      serviceEnabled = await Geolocator.isLocationServiceEnabled();
    }
    if (!serviceEnabled) {
      throw Exception('Location services are disabled. Please enable GPS and try again.');
    }

    permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied || permission == LocationPermission.deniedForever || permission == LocationPermission.unableToDetermine) {
      throw Exception('Enable location to fetch weather. Location permission is required.');
    }

    try {
      const preciseSettings = LocationSettings(
        accuracy: LocationAccuracy.high,
        timeLimit: Duration(seconds: 15),
      );
      final position = await Geolocator.getCurrentPosition(locationSettings: preciseSettings);

      // Debug aid for device-specific location issues.
      print('Location lat=${position.latitude}, lon=${position.longitude}');

      return AppLocation(latitude: position.latitude, longitude: position.longitude);
    } on TimeoutException {
      print('Current position timed out, attempting last known location fallback.');
      final lastKnown = await Geolocator.getLastKnownPosition();
      if (lastKnown != null) {
        print('Using last-known location lat=${lastKnown.latitude}, lon=${lastKnown.longitude}');
        return AppLocation(latitude: lastKnown.latitude, longitude: lastKnown.longitude);
      }
      throw Exception('Unable to get your location in time. Please move to open sky and retry.');
    } on PermissionDeniedException {
      throw Exception('Enable location to fetch weather. Location permission denied.');
    } on LocationServiceDisabledException {
      throw Exception('Enable location to fetch weather. Location services are off.');
    } catch (e) {
      final message = e.toString().toLowerCase();
      if (message.contains('location service')) {
        throw Exception('Enable location to fetch weather. Location services are off.');
      }
      throw Exception('Enable location to fetch weather. Could not fetch current location.');
    }
  }

  Future<Map<String, String>> reverseGeocode(double latitude, double longitude) async {
    try {
      final placemarks = await placemarkFromCoordinates(latitude, longitude);
      if (placemarks.isEmpty) {
        return {'city': '', 'displayName': ''};
      }

      final place = placemarks.first;
      final city = place.locality ?? place.subAdministrativeArea ?? place.administrativeArea ?? '';
      final state = place.administrativeArea ?? place.country ?? '';
      final displayName = [city, state].where((part) => part.trim().isNotEmpty).join(', ');
      return {'city': city, 'displayName': displayName};
    } catch (_) {
      return {'city': '', 'displayName': ''};
    }
  }
}
