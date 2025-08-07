import 'package:http/http.dart' as http;
import 'package:csv/csv.dart';

Future<List<Map<String, String>>> loadCSVFromGitHub() async {
  final url = 'https://raw.githubusercontent.com/harnessapp/harness-csv-data/refs/heads/main/upcoming_fields.csv';
  final response = await http.get(Uri.parse(url));

  if (response.statusCode != 200) {
    throw Exception('Failed to load CSV from GitHub (code ${response.statusCode})');
  }

  final csvString = response.body;
  final rows = const CsvToListConverter(eol: '\n').convert(csvString);
  final headers = rows.first.cast<String>();

  return rows.skip(1).map((row) {
    final Map<String, String> rowMap = {};
    for (int i = 0; i < headers.length; i++) {
      rowMap[headers[i]] = row[i]?.toString() ?? '';
    }
    return rowMap;
  }).toList();
}
