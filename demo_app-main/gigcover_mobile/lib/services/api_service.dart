import 'dart:convert';
import 'dart:io';
import 'dart:async';

import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

const String _rawBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  // Physical device on WiFi: use laptop IP 10.158.14.220
  // Emulator: use 10.0.2.2
  defaultValue: 'http://10.158.14.220:5000',
);

const String _openWeatherApiKey =
    String.fromEnvironment('OPENWEATHER_API_KEY', defaultValue: '');

String get baseUrl {
  final fallback =
      _rawBaseUrl.trim().isEmpty ? 'http://127.0.0.1:5000' : _rawBaseUrl.trim();
  final value = fallback;
  final isSecure = value.startsWith('https://');
  final isLocalHttp = value.startsWith('http://10.') ||
      value.startsWith('http://192.168.') ||
      value.startsWith('http://127.0.0.1') ||
      value.startsWith('http://localhost') ||
      value.startsWith('http://10.0.2.2');

  if (isSecure || isLocalHttp) {
    return value;
  }

  throw Exception(
    'Invalid API_BASE_URL. Use HTTPS for mobile builds, or use local emulator/device host (10.0.2.2 / LAN IP).',
  );
}

class ApiService {
  static String? _token;

  static Future<void> hydrateToken() async {
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('gigcover_token');
  }

  static void setToken(String? token) {
    _token = token;
    SharedPreferences.getInstance().then((prefs) {
      if (token == null || token.trim().isEmpty) {
        prefs.remove('gigcover_token');
      } else {
        prefs.setString('gigcover_token', token);
      }
    });
  }

  static Map<String, String> _headers({bool auth = false}) {
    final headers = <String, String>{'Content-Type': 'application/json'};
    if (auth && _token != null) {
      headers['Authorization'] = 'Bearer $_token';
    }
    return headers;
  }

  static Future<Map<String, dynamic>> signup({
    required String name,
    required String email,
    required String password,
    required String role,
  }) async {
    debugPrint('Signup request => $baseUrl/signup, email=$email, role=$role');
    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/signup'),
            headers: _headers(),
            body: jsonEncode({
              'name': name,
              'email': email,
              'password': password,
              'role': role
            }),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> login({
    required String email,
    required String password,
  }) async {
    debugPrint('Login request => $baseUrl/login, email=$email');
    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/login'),
            headers: _headers(),
            body: jsonEncode({'email': email, 'password': password}),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> calculatePremium({
    required String fullName,
    required String city,
    required String deliveryPlatform,
    required String zoneType,
    required double dailyIncome,
    required double workingHours,
  }) async {
    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/calculate-premium'),
            headers: _headers(auth: true),
            body: jsonEncode({
              'full_name': fullName,
              'city': city,
              'delivery_platform': deliveryPlatform,
              'zone_type': zoneType,
              'daily_income': dailyIncome,
              'working_hours': workingHours,
            }),
          )
          .timeout(const Duration(seconds: 20));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> completeOnboarding({
    required String fullName,
    required int age,
    required String gender,
    required String email,
    required String workType,
    required String platformUsed,
    required double workingHours,
    required String workingShift,
    required int weeklyWorkingDays,
    required String city,
    required String manualLocation,
    required String locationText,
    required double latitude,
    required double longitude,
    required double dailyIncome,
    required String incomeDependency,
    required String workingEnvironment,
    required String zoneType,
  }) async {
    debugPrint(
        'Onboarding request => $baseUrl/onboarding, city=$city, lat=$latitude, lon=$longitude');
    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/onboarding'),
            headers: _headers(auth: true),
            body: jsonEncode({
              'full_name': fullName,
              'age': age,
              'gender': gender,
              'email': email,
              'work_type': workType,
              'platform_used': platformUsed,
              'working_hours': workingHours,
              'working_shift': workingShift,
              'weekly_working_days': weeklyWorkingDays,
              'city': city,
              'manual_location': manualLocation,
              'location_text': locationText,
              'latitude': latitude,
              'longitude': longitude,
              'daily_income': dailyIncome,
              'income_dependency': incomeDependency,
              'working_environment': workingEnvironment,
              'zone_type': zoneType,
            }),
          )
          .timeout(const Duration(seconds: 20));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> predictRisk({
    required double rainfall,
    required double aqi,
    required double traffic,
    required String zone,
    required double disruptions,
  }) async {
    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/predict-risk'),
            headers: _headers(auth: true),
            body: jsonEncode({
              'rainfall_level': rainfall,
              'AQI_level': aqi,
              'traffic_congestion': traffic,
              'zone_type': zone,
              'historical_disruptions': disruptions,
            }),
          )
          .timeout(const Duration(seconds: 20));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> simulateRainfall() async {
    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/simulate-rain'),
            headers: _headers(auth: true),
            body: jsonEncode({'rainfall': 120}),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> autoTrigger(
      {double? latitude, double? longitude, int? aqi}) async {
    final payload = <String, dynamic>{};
    if (latitude != null) payload['latitude'] = latitude;
    if (longitude != null) payload['longitude'] = longitude;
    if (aqi != null) payload['aqi'] = aqi;

    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/auto-trigger'),
            headers: _headers(auth: true),
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 20));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> claimPolicyNow({
    String? risk,
    double? riskScore,
  }) async {
    final payload = <String, dynamic>{
      'trigger_type': 'Weather Risk',
      'lost_hours': 3
    };
    if ((risk ?? '').trim().isNotEmpty) {
      payload['risk'] = risk!.trim().toLowerCase();
    }
    if (riskScore != null) {
      payload['risk_score'] = riskScore;
    }

    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/create-claim'),
            headers: _headers(auth: true),
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> dashboardData() async {
    final response = await _safeRequest(() {
      return http
          .get(
            Uri.parse('$baseUrl/dashboard-data'),
            headers: _headers(auth: true),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> adminOverview(
      {String? department, String? category}) async {
    final query = <String, String>{};
    if ((department ?? '').trim().isNotEmpty) {
      query['department'] = department!.trim();
    }
    if ((category ?? '').trim().isNotEmpty) {
      query['category'] = category!.trim();
    }

    final uri = Uri.parse('$baseUrl/admin/overview')
        .replace(queryParameters: query.isEmpty ? null : query);

    final response = await _safeRequest(() {
      return http
          .get(
            uri,
            headers: _headers(auth: true),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> weatherRisk({
    required double latitude,
    required double longitude,
  }) async {
    final weatherUri = Uri.parse('$baseUrl/weather').replace(
      queryParameters: {
        'lat': latitude.toString(),
        'lon': longitude.toString(),
      },
    );

    try {
      debugPrint('Weather URL: $weatherUri');
      debugPrint('Weather request source base URL: $baseUrl');
      final response = await http
          .get(weatherUri, headers: _headers())
          .timeout(const Duration(seconds: 10));
      debugPrint('Weather status: ${response.statusCode}');
      debugPrint(
          'Weather body: ${response.body.length > 600 ? response.body.substring(0, 600) : response.body}');

      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = jsonDecode(response.body);
        if (decoded is Map<String, dynamic>) {
          return decoded;
        }
        throw Exception('Invalid weather response format from server.');
      }

      // Fallback for authenticated legacy endpoint if /weather is unavailable.
      if (_token != null) {
        final fallback = await http
            .post(
              Uri.parse('$baseUrl/weather-risk'),
              headers: _headers(auth: true),
              body: jsonEncode({'latitude': latitude, 'longitude': longitude}),
            )
            .timeout(const Duration(seconds: 10));
        debugPrint('Weather fallback status: ${fallback.statusCode}');
        debugPrint(
            'Weather fallback body: ${fallback.body.length > 600 ? fallback.body.substring(0, 600) : fallback.body}');
        if (fallback.statusCode >= 200 && fallback.statusCode < 300) {
          return _parse(fallback);
        }
      }

      debugPrint(
          'Primary weather route failed, trying HTTPS OpenWeather direct fallback.');
      return await _weatherRiskFromOpenWeather(
          latitude: latitude, longitude: longitude);
    } on SocketException {
      debugPrint(
          'Socket exception on backend weather route, trying HTTPS OpenWeather direct fallback.');
      return await _weatherRiskFromOpenWeather(
          latitude: latitude, longitude: longitude);
    } on TimeoutException {
      debugPrint(
          'Timeout on backend weather route, trying HTTPS OpenWeather direct fallback.');
      return await _weatherRiskFromOpenWeather(
          latitude: latitude, longitude: longitude);
    } on FormatException {
      throw Exception('Invalid JSON received from weather API.');
    } catch (e) {
      debugPrint('Weather fetch error: $e');
      rethrow;
    }
  }

  static Future<Map<String, dynamic>> weatherForecast({
    required double latitude,
    required double longitude,
  }) async {
    final forecastUri = Uri.parse('$baseUrl/weather-forecast').replace(
      queryParameters: {
        'lat': latitude.toString(),
        'lon': longitude.toString(),
      },
    );

    final response = await _safeRequest(() {
      return http
          .get(forecastUri, headers: _headers())
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> _weatherRiskFromOpenWeather({
    required double latitude,
    required double longitude,
  }) async {
    if (_openWeatherApiKey.trim().isEmpty) {
      throw Exception(
          'Unable to fetch weather data. Configure OPENWEATHER_API_KEY for secure fallback.');
    }

    final uri = Uri.https('api.openweathermap.org', '/data/2.5/weather', {
      'lat': latitude.toString(),
      'lon': longitude.toString(),
      'appid': _openWeatherApiKey,
      'units': 'metric',
    });

    debugPrint('OpenWeather HTTPS URL: $uri');
    final response = await http
        .get(uri, headers: _headers())
        .timeout(const Duration(seconds: 12));
    debugPrint('OpenWeather HTTPS status: ${response.statusCode}');
    debugPrint(
        'OpenWeather HTTPS body: ${response.body.length > 600 ? response.body.substring(0, 600) : response.body}');

    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw Exception('Unable to fetch weather data');
    }

    final json = jsonDecode(response.body) as Map<String, dynamic>;
    final main = (json['main'] as Map<String, dynamic>? ?? <String, dynamic>{});
    final wind = (json['wind'] as Map<String, dynamic>? ?? <String, dynamic>{});
    final rain = (json['rain'] as Map<String, dynamic>? ?? <String, dynamic>{});
    final visibility = (json['visibility'] as num?)?.toInt() ?? 10000;
    final windSpeed = (wind['speed'] as num?)?.toDouble() ?? 0;
    final rainProb = ((rain['1h'] as num?)?.toDouble() ?? 0) * 30;
    final riskScore = (((rainProb / 100.0) * 0.45) +
            ((windSpeed / 20.0).clamp(0.0, 1.0) * 0.25) +
            (((10000 - visibility) / 10000.0).clamp(0.0, 1.0) * 0.30))
        .clamp(0.0, 1.0);

    String riskLabel;
    if (riskScore < 0.4) {
      riskLabel = 'Low';
    } else if (riskScore < 0.7) {
      riskLabel = 'Medium';
    } else {
      riskLabel = 'High';
    }

    return {
      'location': {
        'latitude': latitude,
        'longitude': longitude,
        'city': json['name']?.toString() ?? 'Unknown',
        'display_name': json['name']?.toString() ?? 'Unknown',
      },
      'weather': {
        'temperature': (main['temp'] as num?)?.toDouble() ?? 0,
        'humidity': (main['humidity'] as num?)?.toInt() ?? 0,
        'wind_speed': windSpeed,
        'visibility': visibility,
      },
      'risk': {
        'risk_score': double.parse(riskScore.toStringAsFixed(2)),
        'risk_level': riskLabel,
        'recommendation': riskLabel == 'Low'
            ? 'Claim not eligible due to low risk'
            : (riskLabel == 'Medium'
                ? 'Claim approved (moderate risk)'
                : 'Claim approved (high risk)'),
      },
    };
  }

  static Future<Map<String, dynamic>> payWeeklyPremium() async {
    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/pay-weekly-premium'),
            headers: _headers(auth: true),
            body: jsonEncode({}),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> profile() async {
    final response = await _safeRequest(() {
      return http
          .get(
            Uri.parse('$baseUrl/profile'),
            headers: _headers(auth: true),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> updateProfile({
    required String name,
    required String city,
    required String locationText,
  }) async {
    final response = await _safeRequest(() {
      return http
          .put(
            Uri.parse('$baseUrl/profile'),
            headers: _headers(auth: true),
            body: jsonEncode(
                {'name': name, 'city': city, 'location_text': locationText}),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<List<dynamic>> paymentHistory() async {
    final response = await _safeRequest(() {
      return http
          .get(
            Uri.parse('$baseUrl/payment-history'),
            headers: _headers(auth: true),
          )
          .timeout(const Duration(seconds: 15));
    });
    final data = _parse(response);
    return data['payments'] as List<dynamic>? ?? <dynamic>[];
  }

  static Future<List<dynamic>> getClaims() async {
    // Backend may not expose /claims in all builds, so fallback to /dashboard-data.
    final response = await _safeRequestOrNull(() {
      return http
          .get(
            Uri.parse('$baseUrl/claims'),
            headers: _headers(auth: true),
          )
          .timeout(const Duration(seconds: 15));
    });

    if (response != null &&
        response.statusCode >= 200 &&
        response.statusCode < 300) {
      final data = jsonDecode(response.body);
      if (data is List) return data;
      if (data is Map<String, dynamic> && data['claims'] is List)
        return data['claims'];
    }

    final dashboard = await dashboardData();
    return (dashboard['claims'] as List<dynamic>? ?? <dynamic>[]);
  }

  // ---------------------------------------------------------------------------
  // PARAMETRIC INSURANCE
  // ---------------------------------------------------------------------------

  static Future<Map<String, dynamic>> parametricTrigger({
    double? latitude,
    double? longitude,
  }) async {
    final payload = <String, dynamic>{};
    if (latitude != null) payload['latitude'] = latitude;
    if (longitude != null) payload['longitude'] = longitude;
    final response = await _safeRequest(() {
      return http
          .post(
            Uri.parse('$baseUrl/parametric/trigger'),
            headers: _headers(auth: true),
            body: jsonEncode(payload),
          )
          .timeout(const Duration(seconds: 25));
    });
    return _parse(response);
  }

  static Future<Map<String, dynamic>> parametricPremium() async {
    final response = await _safeRequest(() {
      return http
          .get(
            Uri.parse('$baseUrl/parametric/premium'),
            headers: _headers(auth: true),
          )
          .timeout(const Duration(seconds: 15));
    });
    return _parse(response);
  }

  static Future<List<dynamic>> parametricTransactions() async {
    final response = await _safeRequest(() {
      return http
          .get(
            Uri.parse('$baseUrl/parametric/transactions'),
            headers: _headers(auth: true),
          )
          .timeout(const Duration(seconds: 15));
    });
    final data = _parse(response);
    return data['transactions'] as List<dynamic>? ?? [];
  }

  static Future<List<dynamic>> parametricTriggerEvents() async {
    final response = await _safeRequest(() {
      return http
          .get(
            Uri.parse('$baseUrl/parametric/trigger-events'),
            headers: _headers(auth: true),
          )
          .timeout(const Duration(seconds: 15));
    });
    final data = _parse(response);
    return data['trigger_events'] as List<dynamic>? ?? [];
  }

  static Future<void> logActivity({
    required double latitude,
    required double longitude,
    double speedKmh = 0,
    bool platformActive = true,
  }) async {
    await _safeRequestOrNull(() {
      return http
          .post(
            Uri.parse('$baseUrl/parametric/log-activity'),
            headers: _headers(auth: true),
            body: jsonEncode({
              'latitude': latitude,
              'longitude': longitude,
              'speed_kmh': speedKmh,
              'platform_active': platformActive ? 1 : 0,
            }),
          )
          .timeout(const Duration(seconds: 10));
    });
  }

  static Map<String, dynamic> _parse(http.Response response) {
    final body = response.body.isNotEmpty ? jsonDecode(response.body) : {};
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (body is Map<String, dynamic>) return body;
      return {'data': body};
    }

    final message = body is Map<String, dynamic>
        ? (body['error'] ?? body['message'] ?? 'Request failed')
        : 'Request failed';
    throw Exception(message.toString());
  }

  static Future<http.Response> _safeRequest(
      Future<http.Response> Function() request) async {
    try {
      return await request();
    } on SocketException {
      throw Exception(
          'Unable to connect to server. Please check your internet connection and try again.');
    } on http.ClientException {
      throw Exception(
          'API server is unreachable at $baseUrl. Verify deployment status and API base URL.');
    } on TimeoutException {
      throw Exception(
          'Server is taking too long to respond. Please try again shortly.');
    } catch (_) {
      rethrow;
    }
  }

  static Future<http.Response?> _safeRequestOrNull(
      Future<http.Response> Function() request) async {
    try {
      return await request();
    } on SocketException {
      return null;
    } on TimeoutException {
      return null;
    } catch (_) {
      return null;
    }
  }
}
