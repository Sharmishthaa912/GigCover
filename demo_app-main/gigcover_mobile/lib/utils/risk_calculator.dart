/// RiskCalculator contains weather-risk mapping and accident probability scoring.
class RiskCalculator {
  /// Maps weather condition to a discrete risk level.
  static String getRiskLevel(String weatherCondition) {
    final condition = weatherCondition.toLowerCase();

    if (condition == 'clear' || condition == 'clouds') {
      return 'LOW';
    }

    if (condition == 'mist' || condition == 'fog' || condition == 'haze' || condition == 'dust' || condition == 'smoke' || condition == 'squall') {
      return 'MEDIUM';
    }

    if (condition == 'rain' || condition == 'drizzle') {
      return 'HIGH';
    }

    if (condition == 'thunderstorm' || condition == 'snow') {
      return 'VERY_HIGH';
    }

    if (condition == 'tornado') {
      return 'EXTREME';
    }

    return 'MEDIUM';
  }

  /// Computes accident probability percentage (0 to 100) from live weather metrics.
  static double calculateAccidentProbability({
    required String weatherCondition,
    required double windSpeed,
    required int humidity,
    required int visibility,
  }) {
    final baseRisk = _baseRiskByCondition(weatherCondition);
    final weatherFactor = _weatherFactor(weatherCondition);
    final windFactor = (windSpeed * 2).clamp(0, 20).toDouble();
    final humidityFactor = ((humidity - 40) / 3).clamp(0, 15).toDouble();
    final visibilityFactor = _visibilityFactor(visibility);

    final score = baseRisk + weatherFactor + windFactor + humidityFactor + visibilityFactor;
    return score.clamp(0, 100).toDouble();
  }

  static double _baseRiskByCondition(String weatherCondition) {
    switch (weatherCondition.toLowerCase()) {
      case 'clear':
      case 'clouds':
        return 15;
      case 'mist':
      case 'fog':
      case 'haze':
      case 'dust':
      case 'smoke':
      case 'squall':
        return 30;
      case 'rain':
      case 'drizzle':
        return 45;
      case 'thunderstorm':
      case 'snow':
        return 60;
      case 'tornado':
        return 75;
      default:
        return 25;
    }
  }

  static double _weatherFactor(String weatherCondition) {
    switch (weatherCondition.toLowerCase()) {
      case 'clear':
      case 'clouds':
        return 5;
      case 'mist':
      case 'fog':
      case 'haze':
      case 'dust':
      case 'smoke':
      case 'squall':
        return 10;
      case 'rain':
      case 'drizzle':
        return 18;
      case 'thunderstorm':
      case 'snow':
        return 25;
      case 'tornado':
        return 35;
      default:
        return 8;
    }
  }

  static double _visibilityFactor(int visibilityMeters) {
    if (visibilityMeters < 1000) return 25;
    if (visibilityMeters < 3000) return 18;
    if (visibilityMeters < 5000) return 12;
    if (visibilityMeters < 8000) return 6;
    return 0;
  }
}
