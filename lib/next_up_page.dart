import 'package:http/http.dart' as http; // 📌 Make sure this is at the top
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:csv/csv.dart';
import 'package:intl/intl.dart';
import 'main.dart';
import 'dart:async';

class NextUpPage extends StatefulWidget {
  @override
  _NextUpPageState createState() => _NextUpPageState();
}

class _NextUpPageState extends State<NextUpPage> {
  List<Map<String, dynamic>> upcomingRaces = [];
  List<List<dynamic>> rows = [];
  List<String> headers = [];
  Timer? _ticker; // 🔔 1s ticker for live countdowns

  // 🔎 State filter
  static const List<String> _stateOptions = ['ALL', 'VIC', 'NSW', 'QLD', 'SA', 'WA', 'TAS'];
  String _selectedState = 'ALL';

  /*
  // 🎨 OPTIONAL: State -> Colour mapping (background + text)
  // To re-enable colours:
  // 1) Uncomment this block + the two helper methods below
  // 2) In the ElevatedButton, uncomment the style: ... block and remove defaults

  static const Map<String, Map<String, Color>> _stateColours = {
    'VIC': {'bg': Color(0xFF0D47A1), 'fg': Colors.white},   // dark blue / white
    'NSW': {'bg': Color(0xFF64B5F6), 'fg': Colors.black},   // light blue / black
    'QLD': {'bg': Color(0xFF800000), 'fg': Colors.yellow},  // maroon / yellow
    'WA' : {'bg': Colors.yellow,        'fg': Colors.black},// yellow / black
    'SA' : {'bg': Colors.red,           'fg': Colors.yellow},// red / yellow
    'TAS': {'bg': Colors.green,         'fg': Colors.black},// green / black
  };

  Color _bgForState(String? stateRaw) {
    final key = (stateRaw ?? '').toUpperCase().trim();
    return _stateColours[key]?['bg'] ?? Colors.grey.shade700;
  }

  Color _fgForState(String? stateRaw) {
    final key = (stateRaw ?? '').toUpperCase().trim();
    return _stateColours[key]?['fg'] ?? Colors.white;
  }
  */

  @override
  void initState() {
    super.initState();
    loadNextUpRaces();
    _ticker = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {}); // re-render to refresh mm:ss
    });
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  Future<void> loadNextUpRaces() async {
    final now = DateTime.now();

    // 🔗 Fetch CSV from GitHub raw link
    final response = await http.get(Uri.parse(
      'https://raw.githubusercontent.com/harnessapp/harness-csv-data/main/upcoming_fields.csv',
    ));

    if (response.statusCode != 200) {
      print('⚠️ Failed to load CSV: ${response.statusCode}');
      return;
    }

    final csvString = response.body;
    final List<List<dynamic>> csvTable = const CsvToListConverter().convert(csvString, eol: '\n');

    headers = csvTable[0].map((e) => e.toString()).toList();
    rows = csvTable.sublist(1);

    int? parseInt(dynamic v) {
      try {
        if (v == null) return null;
        final s = v.toString().trim();
        if (s.isEmpty) return null;
        // handle "1.0" or "1"
        return double.tryParse(s)?.toInt();
      } catch (_) {
        return null;
      }
    }

    DateTime? parseRaceDateTime(Map<String, dynamic> map) {
      final dateStr = (map['Date'] ?? '').toString().trim();

      // Prefer AEST if present, else fall back to Time
      final timeStr = (map['AEST'] != null && map['AEST'].toString().trim().isNotEmpty)
          ? map['AEST'].toString().trim()
          : (map['Time'] ?? '').toString().trim();

      if (dateStr.isEmpty || timeStr.isEmpty) return null;

      try {
        // Main expected format: "2025-08-10 5:32 PM"
        final raceDateTimeStr = '$dateStr $timeStr';

        // Parsing with DateFormat
        final raceTime = DateFormat('yyyy-MM-dd h:mm a').parseStrict(raceDateTimeStr);

        // We’re not shifting timezones here (already using AEST column when present)
        return raceTime;
      } catch (_) {
        try {
          // Fallback for formats with leading zeros in hour (hh:mm)
          return DateFormat('yyyy-MM-dd hh:mm a').parseStrict('$dateStr $timeStr');
        } catch (e) {
          print('⚠️ Failed to parse: date="$dateStr" time="$timeStr" – $e');
          return null;
        }
      }
    }

    // Build race maps, keeping the first runner only (Horse No == 1)
    final races = rows.map((row) {
      final map = <String, dynamic>{};
      for (int i = 0; i < headers.length; i++) {
        map[headers[i]] = row[i]?.toString() ?? '';
      }

      // Only keep the first runner per race
      final hn = parseInt(map['Horse No']);
      if (hn != 1) return null;

      final dt = parseRaceDateTime(map);
      if (dt == null) return null;

      map['RaceDateTime'] = dt;
      // Normalise State for filtering
      map['State'] = (map['State'] ?? '').toString().trim().toUpperCase();

      return map;
    }).where((m) =>
    m != null &&
        m['RaceDateTime'] is DateTime &&
        (m['RaceDateTime'] as DateTime).isAfter(now)
    ).cast<Map<String, dynamic>>().toList();

    races.sort((a, b) => a['RaceDateTime'].compareTo(b['RaceDateTime']));

    setState(() {
      upcomingRaces = races;
    });
  }

  // ⏱️ Format a Duration as mm:ss (clamps negatives to 0:00)
  String formatCountdown(Duration diff) {
    if (diff.isNegative) return "0sec";

    final days = diff.inDays;
    final hours = diff.inHours % 24;
    final minutes = diff.inMinutes % 60;
    final seconds = diff.inSeconds % 60;

    final parts = <String>[];
    if (days > 0) parts.add("${days}d");
    if (hours > 0 || days > 0) parts.add("${hours}hr");
    if (minutes > 0 || hours > 0 || days > 0) parts.add("${minutes}min");
    parts.add("${seconds.toString().padLeft(2, '0')}sec");

    return parts.join(' ');
  }


  List<Map<String, dynamic>> _filteredRaces() {
    if (_selectedState == 'ALL') {
      return upcomingRaces.take(10).toList(); // same for ALL
    }
    // Filter first, then take 10
    final filtered = upcomingRaces
        .where((r) => (r['State'] ?? '') == _selectedState)
        .take(10)
        .toList();
    return filtered;
  }


  @override
  Widget build(BuildContext context) {
    final filtered = _filteredRaces();

    return Scaffold(
      appBar: AppBar(title: const Text('Next Up')),
      body: upcomingRaces.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : Column(
        children: [
          // 🔘 State filter chips (compact, minimal layout change)
          SizedBox(
            height: 56,
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              child: Row(
                children: _stateOptions.map((s) {
                  final selected = _selectedState == s;
                  return Padding(
                    padding: const EdgeInsets.only(right: 8),
                    child: ChoiceChip(
                      label: Text(s),
                      selected: selected,
                      onSelected: (val) {
                        setState(() => _selectedState = s);
                      },
                    ),
                  );
                }).toList(),
              ),
            ),
          ),

          // 📋 Race list
          Expanded(
            child: filtered.isEmpty
                ? Center(
              child: Text(
                _selectedState == 'ALL'
                    ? 'No upcoming races.'
                    : 'No upcoming ${_selectedState} races.',
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w500),
              ),
            )
                : ListView.builder(
              itemCount: filtered.length,
              itemBuilder: (context, index) {
                final race = filtered[index];
                final venue = race['Venue'] ?? 'Unknown Venue';
                final raceNo = race['Race No'] ?? '?';
                final raceDateTime = race['RaceDateTime'] as DateTime;
                final timeStr = DateFormat.jm().format(raceDateTime);

                final diff = raceDateTime.difference(DateTime.now());
                final countdown = formatCountdown(diff);

                final label = '$venue – Race $raceNo – $timeStr ($countdown)';

                return Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                  child: ElevatedButton(
                    onPressed: () {
                      final matchingRaces = rows.where((row) {
                        final map = <String, dynamic>{};
                        for (int i = 0; i < headers.length; i++) {
                          map[headers[i]] = row[i].toString();
                        }
                        return map['Venue'] == race['Venue'] &&
                            map['Date'] == race['Date'];
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
                          racesInMeeting:
                          matchingRaces.map((r) => r.cast<String, String>()).toList(),
                        ),
                      ));
                    },
                    child: Text(
                      label,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                );
              },
            ),
          )

        ],
      ),
    );
  }
}
