import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

class WeatherData {
  final String locationName;
  final double temperature;
  final String condition;
  final int humidity;
  final double windSpeed;
  final int pressure;
  final int visibility;

  const WeatherData({
    required this.locationName,
    required this.temperature,
    required this.condition,
    required this.humidity,
    required this.windSpeed,
    required this.pressure,
    required this.visibility,
  });
}

class ForecastDay {
  final String dayName;
  final double temperature;
  final String condition;
  final double rainProbability;
  final double windSpeed;

  const ForecastDay({
    required this.dayName,
    required this.temperature,
    required this.condition,
    required this.rainProbability,
    required this.windSpeed,
  });
}

class WeatherBundle {
  final WeatherData current;
  final List<ForecastDay> forecast;

  const WeatherBundle({required this.current, required this.forecast});
}

class WeatherService {
  static const String _apiKey = String.fromEnvironment('OPENWEATHER_API_KEY', defaultValue: '');
  static const String _baseUrl = 'https://api.openweathermap.org/data/2.5';
  static const String _oneCallBaseUrl = 'https://api.openweathermap.org/data/3.0';
  static const String _openMeteoBaseUrl = 'https://api.open-meteo.com/v1/forecast';

  /// Fetches current weather + 7-day forecast in one call flow.
  Future<WeatherBundle> fetchWeatherAndForecast({
    required double latitude,
    required double longitude,
  }) async {
    if (_apiKey.isEmpty) {
      return _fetchOpenMeteoBundle(latitude: latitude, longitude: longitude);
    }

    final current = await fetchCurrentWeather(latitude: latitude, longitude: longitude);
    final forecast = await fetch7DayForecast(latitude: latitude, longitude: longitude);
    return WeatherBundle(current: current, forecast: forecast);
  }

  /// Fetches current weather for a coordinate.
  Future<WeatherData> fetchCurrentWeather({
    required double latitude,
    required double longitude,
  }) async {
    if (_apiKey.isEmpty) {
      throw Exception('OpenWeather API key missing. Pass --dart-define=OPENWEATHER_API_KEY=YOUR_KEY');
    }

    try {
      final currentUri = Uri.parse(
        '$_baseUrl/weather?lat=$latitude&lon=$longitude&appid=$_apiKey&units=metric',
      );
      final currentResponse = await http.get(currentUri).timeout(const Duration(seconds: 20));

      if (currentResponse.statusCode != 200) {
        throw Exception('Failed to fetch current weather (${currentResponse.statusCode}).');
      }

      final currentJson = jsonDecode(currentResponse.body) as Map<String, dynamic>;
      return _parseCurrentWeather(currentJson);
    } on SocketException {
      throw Exception('No internet connection. Please check your network and retry.');
    } on HttpException {
      throw Exception('Weather service is currently unreachable. Please try again later.');
    } on FormatException {
      throw Exception('Received invalid weather data. Please try again.');
    }
  }

  /// Fetches 7-day daily forecast for a coordinate.
  Future<List<ForecastDay>> fetch7DayForecast({
    required double latitude,
    required double longitude,
  }) async {
    if (_apiKey.isEmpty) {
      throw Exception('OpenWeather API key missing. Pass --dart-define=OPENWEATHER_API_KEY=YOUR_KEY');
    }

    try {
      final forecastUri = Uri.parse(
        '$_oneCallBaseUrl/onecall?lat=$latitude&lon=$longitude&appid=$_apiKey&units=metric&exclude=current,minutely,hourly,alerts',
      );
      final forecastResponse = await http.get(forecastUri).timeout(const Duration(seconds: 20));

      if (forecastResponse.statusCode != 200) {
        throw Exception('Failed to fetch weekly forecast (${forecastResponse.statusCode}).');
      }

      final forecastJson = jsonDecode(forecastResponse.body) as Map<String, dynamic>;
      final forecast = _parseWeeklyForecast(forecastJson);
      if (forecast.isEmpty) {
        throw Exception('Weather forecast data unavailable right now. Please try again shortly.');
      }

      return forecast;
    } on SocketException {
      throw Exception('No internet connection. Please check your network and retry.');
    } on HttpException {
      throw Exception('Weather service is currently unreachable. Please try again later.');
    } on FormatException {
      throw Exception('Received invalid weather data. Please try again.');
    }
  }

  WeatherData _parseCurrentWeather(Map<String, dynamic> json) {
    final weatherList = (json['weather'] as List<dynamic>? ?? []);
    final weatherMain = weatherList.isNotEmpty
        ? (weatherList.first as Map<String, dynamic>)['main']?.toString() ?? 'Unknown'
        : 'Unknown';

    final main = (json['main'] as Map<String, dynamic>? ?? {});
    final wind = (json['wind'] as Map<String, dynamic>? ?? {});

    return WeatherData(
      locationName: json['name']?.toString() ?? 'Unknown location',
      temperature: (main['temp'] as num?)?.toDouble() ?? 0,
      condition: weatherMain,
      humidity: (main['humidity'] as num?)?.toInt() ?? 0,
      windSpeed: (wind['speed'] as num?)?.toDouble() ?? 0,
      pressure: (main['pressure'] as num?)?.toInt() ?? 0,
      visibility: (json['visibility'] as num?)?.toInt() ?? 0,
    );
  }

  List<ForecastDay> _parseWeeklyForecast(Map<String, dynamic> json) {
    final daily = (json['daily'] as List<dynamic>? ?? []);
    final limitedDays = daily.take(7).toList();

    return limitedDays.map((item) {
      final day = item as Map<String, dynamic>;
      final dt = DateTime.fromMillisecondsSinceEpoch(((day['dt'] as num?)?.toInt() ?? 0) * 1000);
      final temp = (day['temp'] as Map<String, dynamic>? ?? {});
      final weatherList = (day['weather'] as List<dynamic>? ?? []);
      final weatherMain = weatherList.isNotEmpty
          ? (weatherList.first as Map<String, dynamic>)['main']?.toString() ?? 'Unknown'
          : 'Unknown';

      return ForecastDay(
        dayName: _dayName(dt.weekday),
        temperature: (temp['day'] as num?)?.toDouble() ?? 0,
        condition: weatherMain,
        rainProbability: ((day['pop'] as num?)?.toDouble() ?? 0) * 100,
        windSpeed: (day['wind_speed'] as num?)?.toDouble() ?? 0,
      );
    }).toList();
  }

  String _dayName(int weekday) {
    const names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
    final index = weekday - 1;
    if (index < 0 || index >= names.length) return 'Day';
    return names[index];
  }

  Future<WeatherBundle> _fetchOpenMeteoBundle({
    required double latitude,
    required double longitude,
  }) async {
    try {
      final uri = Uri.parse(
        '$_openMeteoBaseUrl?latitude=$latitude&longitude=$longitude'
        '&current=temperature_2m,relative_humidity_2m,weather_code,surface_pressure,wind_speed_10m,visibility'
        '&daily=weather_code,temperature_2m_max,precipitation_probability_max,wind_speed_10m_max'
        '&forecast_days=7&timezone=auto',
      );

      final response = await http.get(uri).timeout(const Duration(seconds: 20));
      if (response.statusCode != 200) {
        throw Exception('Failed to fetch weather (${response.statusCode}).');
      }

      final data = jsonDecode(response.body) as Map<String, dynamic>;
      final current = _parseOpenMeteoCurrent(data);
      final forecast = _parseOpenMeteoForecast(data);
      if (forecast.isEmpty) {
        throw Exception('Weather forecast data unavailable right now. Please try again shortly.');
      }

      return WeatherBundle(current: current, forecast: forecast);
    } on SocketException {
      throw Exception('No internet connection. Please check your network and retry.');
    } on FormatException {
      throw Exception('Received invalid weather data. Please try again.');
    }
  }

  WeatherData _parseOpenMeteoCurrent(Map<String, dynamic> json) {
    final current = (json['current'] as Map<String, dynamic>? ?? {});
    return WeatherData(
      locationName: 'Current location',
      temperature: (current['temperature_2m'] as num?)?.toDouble() ?? 0,
      condition: _conditionFromWeatherCode((current['weather_code'] as num?)?.toInt()),
      humidity: (current['relative_humidity_2m'] as num?)?.toInt() ?? 0,
      windSpeed: ((current['wind_speed_10m'] as num?)?.toDouble() ?? 0) / 3.6,
      pressure: (current['surface_pressure'] as num?)?.toInt() ?? 0,
      visibility: (current['visibility'] as num?)?.toInt() ?? 10000,
    );
  }

  List<ForecastDay> _parseOpenMeteoForecast(Map<String, dynamic> json) {
    final daily = (json['daily'] as Map<String, dynamic>? ?? {});
    final times = (daily['time'] as List<dynamic>? ?? const []);
    final codes = (daily['weather_code'] as List<dynamic>? ?? const []);
    final temps = (daily['temperature_2m_max'] as List<dynamic>? ?? const []);
    final pops = (daily['precipitation_probability_max'] as List<dynamic>? ?? const []);
    final winds = (daily['wind_speed_10m_max'] as List<dynamic>? ?? const []);

    final length = [times.length, codes.length, temps.length, pops.length, winds.length].reduce(
      (a, b) => a < b ? a : b,
    );

    return List.generate(length > 7 ? 7 : length, (index) {
      final dt = DateTime.tryParse(times[index].toString()) ?? DateTime.now();
      return ForecastDay(
        dayName: _dayName(dt.weekday),
        temperature: (temps[index] as num?)?.toDouble() ?? 0,
        condition: _conditionFromWeatherCode((codes[index] as num?)?.toInt()),
        rainProbability: (pops[index] as num?)?.toDouble() ?? 0,
        windSpeed: ((winds[index] as num?)?.toDouble() ?? 0) / 3.6,
      );
    });
  }

  String _conditionFromWeatherCode(int? code) {
    switch (code) {
      case 0:
        return 'Clear';
      case 1:
      case 2:
      case 3:
        return 'Clouds';
      case 45:
      case 48:
        return 'Fog';
      case 51:
      case 53:
      case 55:
      case 56:
      case 57:
        return 'Drizzle';
      case 61:
      case 63:
      case 65:
      case 66:
      case 67:
      case 80:
      case 81:
      case 82:
        return 'Rain';
      case 71:
      case 73:
      case 75:
      case 77:
      case 85:
      case 86:
        return 'Snow';
      case 95:
      case 96:
      case 99:
        return 'Thunderstorm';
      default:
        return 'Unknown';
    }
  }
}
