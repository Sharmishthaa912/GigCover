import 'dart:convert';

import 'package:gigcover_mobile/services/location_service.dart';
import 'package:gigcover_mobile/services/weather_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

class CachedWeatherRiskSnapshot {
  final AppLocation location;
  final WeatherBundle weatherBundle;
  final String riskLevel;
  final double accidentProbability;
  final int weeklyPremium;
  final DateTime cachedAt;
  final Duration age;
  final bool isStale;

  const CachedWeatherRiskSnapshot({
    required this.location,
    required this.weatherBundle,
    required this.riskLevel,
    required this.accidentProbability,
    required this.weeklyPremium,
    required this.cachedAt,
    required this.age,
    required this.isStale,
  });
}

class WeatherCacheService {
  static const String _cacheKey = 'weather_risk_snapshot_v1';

  Future<void> saveSnapshot({
    required AppLocation location,
    required WeatherBundle weatherBundle,
    required String riskLevel,
    required double accidentProbability,
    required int weeklyPremium,
  }) async {
    final prefs = await SharedPreferences.getInstance();

    final payload = <String, dynamic>{
      'location': {
        'latitude': location.latitude,
        'longitude': location.longitude,
      },
      'riskLevel': riskLevel,
      'accidentProbability': accidentProbability,
      'weeklyPremium': weeklyPremium,
      'cachedAt': DateTime.now().toIso8601String(),
      'current': {
        'locationName': weatherBundle.current.locationName,
        'temperature': weatherBundle.current.temperature,
        'condition': weatherBundle.current.condition,
        'humidity': weatherBundle.current.humidity,
        'windSpeed': weatherBundle.current.windSpeed,
        'pressure': weatherBundle.current.pressure,
        'visibility': weatherBundle.current.visibility,
      },
      'forecast': weatherBundle.forecast
          .map(
            (day) => {
              'dayName': day.dayName,
              'temperature': day.temperature,
              'condition': day.condition,
              'rainProbability': day.rainProbability,
              'windSpeed': day.windSpeed,
            },
          )
          .toList(),
    };

    await prefs.setString(_cacheKey, jsonEncode(payload));
  }

  Future<CachedWeatherRiskSnapshot?> loadSnapshot({
    Duration staleAfter = const Duration(hours: 2),
    bool allowStale = true,
  }) async {
    final prefs = await SharedPreferences.getInstance();
    final raw = prefs.getString(_cacheKey);
    if (raw == null || raw.isEmpty) return null;

    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      final locationJson = json['location'] as Map<String, dynamic>?;
      final currentJson = json['current'] as Map<String, dynamic>?;
      final forecastJson = (json['forecast'] as List<dynamic>? ?? []);

      if (locationJson == null || currentJson == null) return null;

      final location = AppLocation(
        latitude: (locationJson['latitude'] as num?)?.toDouble() ?? 0,
        longitude: (locationJson['longitude'] as num?)?.toDouble() ?? 0,
      );

      final current = WeatherData(
        locationName: currentJson['locationName']?.toString() ?? 'Unknown location',
        temperature: (currentJson['temperature'] as num?)?.toDouble() ?? 0,
        condition: currentJson['condition']?.toString() ?? 'Unknown',
        humidity: (currentJson['humidity'] as num?)?.toInt() ?? 0,
        windSpeed: (currentJson['windSpeed'] as num?)?.toDouble() ?? 0,
        pressure: (currentJson['pressure'] as num?)?.toInt() ?? 0,
        visibility: (currentJson['visibility'] as num?)?.toInt() ?? 0,
      );

      final forecast = forecastJson.map((entry) {
        final item = entry as Map<String, dynamic>;
        return ForecastDay(
          dayName: item['dayName']?.toString() ?? 'Day',
          temperature: (item['temperature'] as num?)?.toDouble() ?? 0,
          condition: item['condition']?.toString() ?? 'Unknown',
          rainProbability: (item['rainProbability'] as num?)?.toDouble() ?? 0,
          windSpeed: (item['windSpeed'] as num?)?.toDouble() ?? 0,
        );
      }).toList();

      final weatherBundle = WeatherBundle(current: current, forecast: forecast);
      final cachedAt = DateTime.tryParse(json['cachedAt']?.toString() ?? '') ?? DateTime.now();
      final age = DateTime.now().difference(cachedAt);
      final isStale = age > staleAfter;

      if (!allowStale && isStale) {
        return null;
      }


      return CachedWeatherRiskSnapshot(
        location: location,
        weatherBundle: weatherBundle,
        riskLevel: json['riskLevel']?.toString() ?? 'MEDIUM',
        accidentProbability: (json['accidentProbability'] as num?)?.toDouble() ?? 0,
        weeklyPremium: (json['weeklyPremium'] as num?)?.toInt() ?? 130,
        cachedAt: cachedAt,
        age: age,
        isStale: isStale,
      );
    } catch (_) {
      return null;
    }
  }
}
