import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';

class WeatherForecastScreen extends StatefulWidget {
  const WeatherForecastScreen({super.key});

  @override
  State<WeatherForecastScreen> createState() => _WeatherForecastScreenState();
}

class _WeatherForecastScreenState extends State<WeatherForecastScreen> {
  List<dynamic> _forecast = [];
  bool _isLoading = false;
  String? _error;
  final TextEditingController _latController = TextEditingController();
  final TextEditingController _lonController = TextEditingController();

  @override
  void dispose() {
    _latController.dispose();
    _lonController.dispose();
    super.dispose();
  }

  Future<void> _fetchForecast(double latitude, double longitude) async {
    setState(() {
      _isLoading = true;
      _error = null;
      _forecast = [];
    });

    try {
      final data = await ApiService.weatherForecast(
        latitude: latitude,
        longitude: longitude,
      );

      setState(() {
        _forecast = data['forecast'] ?? [];
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
        _isLoading = false;
      });
    }
  }

  void _searchByManualLocation() {
    final latText = _latController.text.trim();
    final lonText = _lonController.text.trim();

    if (latText.isEmpty || lonText.isEmpty) {
      setState(() {
        _error = 'Please enter both latitude and longitude values.';
      });
      return;
    }

    final latitude = double.tryParse(latText);
    final longitude = double.tryParse(lonText);

    if (latitude == null || longitude == null) {
      setState(() {
        _error = 'Latitude and longitude must be valid numbers.';
      });
      return;
    }

    _fetchForecast(latitude, longitude);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Weather Forecast'),
        backgroundColor: Colors.blueAccent,
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _searchByManualLocation,
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              controller: _latController,
              keyboardType: TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Latitude',
                border: OutlineInputBorder(),
                hintText: 'e.g. 12.9716',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _lonController,
              keyboardType: TextInputType.numberWithOptions(decimal: true),
              decoration: const InputDecoration(
                labelText: 'Longitude',
                border: OutlineInputBorder(),
                hintText: 'e.g. 77.5946',
              ),
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: _searchByManualLocation,
                    child: const Text('Fetch Forecast'),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            if (_isLoading) ...[
              const Center(child: CircularProgressIndicator()),
              const SizedBox(height: 16),
            ],
            if (_error != null) ...[
              Row(
                children: [
                  const Icon(Icons.error, color: Colors.red),
                  const SizedBox(width: 8),
                  Expanded(child: Text('Error: $_error')),
                ],
              ),
              const SizedBox(height: 12),
              ElevatedButton(
                onPressed: _searchByManualLocation,
                child: const Text('Retry with entered location'),
              ),
              const SizedBox(height: 16),
            ],
            Expanded(
              child: _forecast.isEmpty
                  ? const Center(child: Text('No forecast data available'))
                  : ListView.builder(
                      padding: const EdgeInsets.only(bottom: 16),
                      itemCount: _forecast.length,
                      itemBuilder: (context, index) {
                        final item = _forecast[index];
                        final dt = DateTime.parse(item['datetime']);
                        final time = DateFormat('HH:mm').format(dt);
                        final day = DateFormat('EEE').format(dt);

                        return Card(
                          margin: const EdgeInsets.only(bottom: 12),
                          child: Padding(
                            padding: const EdgeInsets.all(16),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        '$day $time',
                                        style: const TextStyle(
                                          fontSize: 16,
                                          fontWeight: FontWeight.bold,
                                        ),
                                      ),
                                      const SizedBox(height: 8),
                                      Text(
                                        item['description'] ?? 'No description',
                                        style: TextStyle(
                                          color: Colors.grey[600],
                                        ),
                                      ),
                                    ],
                                  ),
                                ),
                                Column(
                                  crossAxisAlignment: CrossAxisAlignment.end,
                                  children: [
                                    Text(
                                      '${item['temperature']}°C',
                                      style: const TextStyle(
                                        fontSize: 20,
                                        fontWeight: FontWeight.bold,
                                      ),
                                    ),
                                    Text(
                                      '${item['humidity']}%',
                                      style: TextStyle(
                                        color: Colors.grey[600],
                                      ),
                                    ),
                                    Text(
                                      '${item['rain_probability']}%',
                                      style: TextStyle(
                                        color: item['rain_probability'] > 50
                                            ? Colors.blue
                                            : Colors.grey[600],
                                      ),
                                    ),
                                  ],
                                ),
                              ],
                            ),
                          ),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}
