/// PremiumCalculator maps risk levels to weekly premium amounts.
class PremiumCalculator {
  /// Returns weekly premium in INR based on risk level.
  static int calculateWeeklyPremium(String riskLevel) {
    switch (riskLevel) {
      case 'LOW':
        return 100;
      case 'MEDIUM':
        return 130;
      case 'HIGH':
        return 170;
      case 'VERY_HIGH':
        return 220;
      case 'EXTREME':
        return 300;
      default:
        return 130;
    }
  }
}
