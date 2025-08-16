import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:csv/csv.dart';

class DriversTablePage extends StatefulWidget {
  final String title;
  final String csvAssetPath; // e.g., 'assets/hot_drivers_30.csv'

  const DriversTablePage({
    super.key,
    required this.title,
    required this.csvAssetPath,
  });

  @override
  State<DriversTablePage> createState() => _DriversTablePageState();
}

class _DriversTablePageState extends State<DriversTablePage> {
  late Future<List<Map<String, dynamic>>> driversData;

  @override
  void initState() {
    super.initState();
    driversData = _loadCSVData(widget.csvAssetPath);
  }

  Future<List<Map<String, dynamic>>> _loadCSVData(String assetPath) async {
    try {
      final contents = await rootBundle.loadString(assetPath);
      List<List<dynamic>> csvTable = const CsvToListConverter().convert(contents);

      // Skip header
      if (csvTable.isNotEmpty) csvTable = csvTable.sublist(1);

      return csvTable.map<Map<String, dynamic>>((row) {
        return {
          'Driver': row[0],
          'Starts': row[1],
          'Wins': row[2],
          '2nds': row[3],
          '3rds': row[4],
          'Spend': row.length > 5 ? row[5] : null,
          'P&L':   row.length > 6 ? row[6] : null,
          'ROI %': row.length > 7 ? row[7] : 0,
        };
      }).take(50).toList(); // top 50
    } catch (e) {
      debugPrint('Error loading CSV asset ($assetPath): $e');
      return [];
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: driversData,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError || !snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(child: Text('No data available'));
          }

          final rows = snapshot.data!.take(50).toList(); // safety

          return Center(
            child: ConstrainedBox(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.55,
              ),
              child: Column(
                children: [
                  // Header
                  Container(
                    padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                    color: Colors.grey[300],
                    child: const Row(
                      children: [
                        Expanded(flex: 3, child: Text('Driver', style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('ROI',    textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('Starts', textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('Wins',   textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('2nds',   textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('3rds',   textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                      ],
                    ),
                  ),

                  // Rows
                  Expanded(
                    child: ListView.builder(
                      itemCount: rows.length,
                      itemBuilder: (context, index) {
                        final d = rows[index];

                        double parseRoi(dynamic v) {
                          if (v == null) return 0;
                          if (v is num) return v.toDouble();
                          if (v is String) {
                            final s = v.replaceAll('%', '').trim();
                            return double.tryParse(s) ?? 0;
                          }
                          return 0;
                        }

                        final roi = parseRoi(d['ROI %']);
                        final isEven = index % 2 == 0;
                        final baseColor = isEven ? Colors.grey[100] : Colors.white;
                        final highlight = roi > 0.1;

                        return Container(
                          color: baseColor,
                          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
                          child: Row(
                            children: [
                              Expanded(flex: 3, child: Text('${d['Driver'] ?? 'Unknown'}')),
                              Expanded(
                                child: Container(
                                  padding: const EdgeInsets.symmetric(vertical: 2, horizontal: 4),
                                  decoration: highlight
                                      ? BoxDecoration(
                                    color: Colors.green.withOpacity(0.15),
                                    borderRadius: BorderRadius.circular(4),
                                  )
                                      : null,
                                  child: Text(
                                    '${roi.toStringAsFixed(1)}%',
                                    textAlign: TextAlign.right,
                                    style: TextStyle(
                                      fontWeight: highlight ? FontWeight.bold : FontWeight.normal,
                                      color: highlight ? Colors.green[800] : Colors.black,
                                    ),
                                  ),
                                ),
                              ),
                              Expanded(child: Text('${d['Starts']}', textAlign: TextAlign.right)),
                              Expanded(child: Text('${d['Wins']}',   textAlign: TextAlign.right)),
                              Expanded(child: Text('${d['2nds']}',   textAlign: TextAlign.right)),
                              Expanded(child: Text('${d['3rds']}',   textAlign: TextAlign.right)),
                            ],
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
