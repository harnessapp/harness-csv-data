import 'package:http/http.dart' as http; // 📌 Make sure this is at the top
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:csv/csv.dart';
import 'package:intl/intl.dart';
import 'main.dart';

class NextUpPage extends StatefulWidget {
  @override
  _NextUpPageState createState() => _NextUpPageState();
}

class _NextUpPageState extends State<NextUpPage> {
  List<Map<String, dynamic>> upcomingRaces = [];
  List<List<dynamic>> rows = [];
  List<String> headers = [];

  @override
  void initState() {
    super.initState();
    loadNextUpRaces();
  }

  Future<void> loadNextUpRaces() async {
    final now = DateTime.now();

    // 🔗 Fetch CSV from GitHub raw link
    final response = await http.get(Uri.parse(
      'https://raw.githubusercontent.com/harnessapp/harness-csv-data/refs/heads/main/upcoming_fields.csv',
    ));

    if (response.statusCode != 200) {
      print('⚠️ Failed to load CSV: ${response.statusCode}');
      return;
    }

    final csvString = response.body;
    final List<List<dynamic>> csvTable = const CsvToListConverter().convert(csvString, eol: '\n');

    headers = csvTable[0].map((e) => e.toString()).toList();
    rows = csvTable.sublist(1);

    final races = rows.map((row) {
      final map = <String, dynamic>{};
      for (int i = 0; i < headers.length; i++) {
        map[headers[i]] = row[i].toString();
      }

      // Only keep one row per race
      if (map['Horse No'] != '1.0') return null;

      try {
        final dateStr = map['Date'];
        final timeStr = map['Time'];
        final fullDateTimeStr = '$dateStr $timeStr';

        final raceTime = DateFormat('yyyy-MM-dd h:mm a').parseStrict(fullDateTimeStr);
        map['RaceDateTime'] = raceTime;
        return map;
      } catch (e) {
        print('⚠️ Failed to parse row: $map – Error: $e');
        return null;
      }
    }).where((map) =>
    map != null &&
        map['RaceDateTime'] is DateTime &&
        map['RaceDateTime'].isAfter(now)).cast<Map<String, dynamic>>().toList();

    races.sort((a, b) => a['RaceDateTime'].compareTo(b['RaceDateTime']));

    setState(() {
      upcomingRaces = races.take(5).toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Next Up')),
      body: upcomingRaces.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : ListView.builder(
        itemCount: upcomingRaces.length,
        itemBuilder: (context, index) {
          final race = upcomingRaces[index];
          final venue = race['Venue'] ?? 'Unknown Venue';
          final raceNo = race['Race No'] ?? '?';
          final timeStr = DateFormat.jm().format(race['RaceDateTime']);
          final label = '$venue – Race $raceNo – $timeStr';

          return Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            child: ElevatedButton(
              onPressed: () {
                // Gather all races in same meeting
                final matchingRaces = rows.where((row) {
                  final map = <String, dynamic>{};
                  for (int i = 0; i < headers.length; i++) {
                    map[headers[i]] = row[i].toString();
                  }
                  return map['Venue'] == race['Venue'] && map['Date'] == race['Date'];
                }).map((row) {
                  final map = <String, dynamic>{};
                  for (int i = 0; i < headers.length; i++) {
                    map[headers[i]] = row[i].toString();
                  }
                  return map;
                }).toList();

                Navigator.of(context).push(MaterialPageRoute(
                  builder: (context) => RaceDetailsPage(
                    race: race.cast<String, String>(),
                    racesInMeeting: matchingRaces.map((r) => r.cast<String, String>()).toList(),
                  ),
                ));

              },
              child: Text(label),
            ),
          );
        },
      ),
    );
  }
}
