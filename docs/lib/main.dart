import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:csv/csv.dart';
import 'next_up_page.dart';
import 'csv_utils.dart';


void main() {
  runApp(const HarnessApp());
}

class HarnessApp extends StatelessWidget {
  const HarnessApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Harness App',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const HomePage(),
    );
  }
}

class HomePage extends StatelessWidget {
  const HomePage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Harness App")),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton(
              onPressed: () {
                Navigator.of(context).push(MaterialPageRoute(
                  builder: (context) => const UpcomingFieldsPage(),
                ));
              },
              child: const Text("Upcoming Fields"),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                Navigator.of(context).push(MaterialPageRoute(
                  builder: (context) => NextUpPage(),
                ));
              },
              child: const Text("Next Up"),
            ),
          ],
        ),
      ),
    );
  }

}

class UpcomingFieldsPage extends StatefulWidget {
  const UpcomingFieldsPage({super.key});

  @override
  State<UpcomingFieldsPage> createState() => _UpcomingFieldsPageState();
}

class _UpcomingFieldsPageState extends State<UpcomingFieldsPage> {
  late Future<List<String>> _datesFuture;

  @override
  void initState() {
    super.initState();
    _datesFuture = loadUniqueDates();
  }

  Future<List<Map<String, String>>> loadCSV() async {
    return await loadCSVFromGitHub();




  }

  Future<List<String>> loadUniqueDates() async {
    final data = await loadCSV();
    final dateSet = <String>{};

    for (final row in data) {
      final dateStr = row['Date'] ?? '';
      if (dateStr.isNotEmpty) {
        dateSet.add(dateStr);
      }
    }

    final dates = dateSet.toList();

    dates.sort((a, b) {
      try {
        final aParts = a.split('/');
        final bParts = b.split('/');

        final aDate = DateTime(int.parse(aParts[2]), int.parse(aParts[1]), int.parse(aParts[0]));
        final bDate = DateTime(int.parse(bParts[2]), int.parse(bParts[1]), int.parse(bParts[0]));

        return bDate.compareTo(aDate); // newest first
      } catch (_) {
        return b.compareTo(a);
      }
    });

    return dates;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text("Upcoming Fields")),
      body: FutureBuilder<List<String>>(
        future: _datesFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          } else if (snapshot.hasError) {
            return Center(child: Text('Error: ${snapshot.error}'));
          } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(child: Text('No data available.'));
          }

          final dates = snapshot.data!;
          return ListView.builder(
            itemCount: dates.length,
            itemBuilder: (context, index) {
              final date = dates[index];
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                child: ElevatedButton(
                  onPressed: () {
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (context) => VenuesPage(selectedDate: date),
                    ));
                  },
                  child: Text(date),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class VenuesPage extends StatelessWidget {
  final String selectedDate;
  const VenuesPage({super.key, required this.selectedDate});

  Future<List<Map<String, String>>> loadCSV() async {
    return await loadCSVFromGitHub();

  }

  Future<List<String>> getVenuesForDate() async {
    final data = await loadCSV();
    final venueSet = <String>{};

    for (final row in data) {
      if (row['Date'] == selectedDate && row['Venue'] != null && row['Venue']!.isNotEmpty) {
        venueSet.add(row['Venue']!);
      }
    }

    final venues = venueSet.toList();
    venues.sort();
    return venues;
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("Venues on $selectedDate")),
      body: FutureBuilder<List<String>>(
        future: getVenuesForDate(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());

          final venues = snapshot.data!;
          return ListView.builder(
            itemCount: venues.length,
            itemBuilder: (context, index) {
              final venue = venues[index];
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                child: ElevatedButton(
                  onPressed: () {
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (context) => RacesPage(date: selectedDate, venue: venue),
                    ));
                  },
                  child: Text(venue),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class RacesPage extends StatelessWidget {
  final String date;
  final String venue;

  const RacesPage({super.key, required this.date, required this.venue});

  Future<List<Map<String, String>>> loadCSV() async {
    return await loadCSVFromGitHub();


  }

  Future<List<Map<String, String>>> getRaces() async {
    final data = await loadCSV();
    return data.where((row) => row['Date'] == date && row['Venue'] == venue).toList();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text("$venue Races")),
      body: FutureBuilder<List<Map<String, String>>>(
        future: getRaces(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) return const Center(child: CircularProgressIndicator());

          final races = snapshot.data!;
          final seenRaceNos = <String>{};
          final uniqueRaces = races.where((row) {
            final raceNo = row['Race No'] ?? '';
            if (seenRaceNos.contains(raceNo)) return false;
            seenRaceNos.add(raceNo);
            return true;
          }).toList();

          uniqueRaces.sort((a, b) {
            final aNum = int.tryParse(a['Race No'] ?? '');
            final bNum = int.tryParse(b['Race No'] ?? '');
            if (aNum == null || bNum == null) return 0;
            return aNum.compareTo(bNum);
          });


          return ListView.builder(
            itemCount: uniqueRaces.length,
            itemBuilder: (context, index) {
              final race = uniqueRaces[index];
              return Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                child: ElevatedButton(
                  onPressed: () {
                    Navigator.of(context).push(MaterialPageRoute(
                      builder: (context) => RaceDetailsPage(race: race, racesInMeeting: uniqueRaces),
                    ));
                  },
                  child: Text("Race ${race['Race No']}"),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

class RaceDetailsPage extends StatelessWidget {
  final Map<String, String> race;
  final List<Map<String, String>> racesInMeeting;

  const RaceDetailsPage({super.key, required this.race, required this.racesInMeeting});

  Future<List<Map<String, String>>> loadCSV() async {
    return await loadCSVFromGitHub();
  }

  String cleanDistance(String distance) {
    return distance.endsWith('.0') ? distance.replaceAll('.0', '') : distance;
  }

  String formatProper(String input) {
    if (input.isEmpty) return input;
    return input
        .toLowerCase()
        .split(' ')
        .map((word) => word.isNotEmpty ? word[0].toUpperCase() + word.substring(1) : '')
        .join(' ');
  }

  Widget buildSaddleCloth(String horseNo) {
    // This is just a basic example; you can add more cases based on the patterns you want.
    switch (horseNo) {
      case '1':
        return Container(
          decoration: BoxDecoration(
            color: Colors.red, // Background color
            borderRadius: BorderRadius.circular(4), // Rounded edges for the cloth
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        );
      case '2':
        return Container(
          decoration: BoxDecoration(
            color: Colors.black, // Background color
            borderRadius: BorderRadius.circular(4),
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        );
      case '3':
        return Container(
          decoration: BoxDecoration(
            color: Colors.white, // Background color
            borderRadius: BorderRadius.circular(4),
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      case '4':
        return Container(
          decoration: BoxDecoration(
            color: Colors.blue, // Background color
            borderRadius: BorderRadius.circular(4),
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      case '5':
        return Container(
          decoration: BoxDecoration(
            color: Colors.yellow, // Background color
            borderRadius: BorderRadius.circular(4),
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      case '6':
        return Container(
          decoration: BoxDecoration(
            color: Colors.green, // Background color
            borderRadius: BorderRadius.circular(4),
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      case '7':
        return Container(
          decoration: BoxDecoration(
            color: Colors.black, // Background color
            borderRadius: BorderRadius.circular(4),
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        );
      case '8':
        return Container(
          decoration: BoxDecoration(
            color: Colors.pink, // Background color
            borderRadius: BorderRadius.circular(4),
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
    // You can continue adding cases for other horse numbers as required.

      default:
        return Container(
          decoration: BoxDecoration(
            color: Colors.grey, // Default color if no match found
            borderRadius: BorderRadius.circular(4),
          ),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        );
    }
  }


  @override
  Widget build(BuildContext context) {
    final time = (race['Time'] ?? '')
        .replaceAll(' AM', 'am')
        .replaceAll(' PM', 'pm');
    final raceNo = race['Race No'] ?? '';
    final raceName = formatProper(race['Race Name'] ?? '');
    final distance = cleanDistance(race['Distance'] ?? '');
    final start = formatProper(race['Start'] ?? '');
    final gait = formatProper(race['Gait'] ?? '');

    final bmLT = race['BM LT'] ?? '';
    final bmQ1 = race['BM Q1'] ?? '';
    final bmQ2 = race['BM Q2'] ?? '';
    final bmQ3 = race['BM Q3'] ?? '';
    final bmQ4 = race['BM Q4'] ?? '';
    final sample = race['VenDistGaitStart Sample'] ?? '';

    final currentIndex = racesInMeeting.indexWhere((r) => r['Race No'] == raceNo);
    final hasPrevious = currentIndex > 0;
    final hasNext = currentIndex < racesInMeeting.length - 1;

    return Scaffold(
      appBar: AppBar(
        title: const Text("Race Details"),
        actions: [
          IconButton(
            icon: const Icon(Icons.chevron_left),
            onPressed: hasPrevious
                ? () {
              Navigator.of(context).pushReplacement(MaterialPageRoute(
                builder: (context) => RaceDetailsPage(
                  race: racesInMeeting[currentIndex - 1],
                  racesInMeeting: racesInMeeting,
                ),
              ));
            }
                : null,
          ),
          IconButton(
            icon: const Icon(Icons.chevron_right),
            onPressed: hasNext
                ? () {
              Navigator.of(context).pushReplacement(MaterialPageRoute(
                builder: (context) => RaceDetailsPage(
                  race: racesInMeeting[currentIndex + 1],
                  racesInMeeting: racesInMeeting,
                ),
              ));
            }
                : null,
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              "$time. Race $raceNo. $raceName. ${distance}m. $start. $gait.",
              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              "($sample) Benchmarks: $bmLT || $bmQ1 | $bmQ2 | $bmQ3 | $bmQ4",
              style: const TextStyle(fontSize: 14, color: Colors.grey),
            ),
            const SizedBox(height: 8),
            const Divider(thickness: 1, color: Colors.grey),
            const SizedBox(height: 12),
            Expanded(
              child: FutureBuilder<List<Map<String, String>>>(
                future: loadCSV(),
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  } else if (snapshot.hasError) {
                    return Center(child: Text('Error: ${snapshot.error}'));
                  }

                  final runners = snapshot.data!
                      .where((row) =>
                  (row['Race No']?.trim() ?? '') == raceNo &&
                      (row['Venue']?.trim() ?? '') == (race['Venue'] ?? '') &&
                      (row['Date']?.trim() ?? '') == (race['Date'] ?? ''))
                      .toList();


                  runners.sort((a, b) {
                    final aNum = int.tryParse(a['Horse No'] ?? '') ?? 0;
                    final bNum = int.tryParse(b['Horse No'] ?? '') ?? 0;
                    return aNum.compareTo(bNum);
                  });

                  return ListView.builder(
                    itemCount: runners.length,
                    itemBuilder: (context, index) {
                      final runner = runners[index];
                      final rawHorseNo = (runner['Horse No'] ?? '').trim();
                      final horseNo = rawHorseNo.endsWith('.0')
                          ? rawHorseNo.replaceAll('.0', '')
                          : rawHorseNo;
                      final barrier = (runner['Barrier'] ?? '').toLowerCase();
                      final ldPct = double.tryParse(runner['Ld %'] ?? '') ?? 0;
                      final dthPct = double.tryParse(runner['Dth %'] ?? '') ?? 0;
                      final rawBl = (runner['BL %'] ?? '').replaceAll('%', '').trim();
                      final showLead = barrier.contains('fr') && ldPct > 15;
                      final showDeath = dthPct > 15;
                      final blKey = runner.keys.firstWhere(
                            (key) => key.trim().contains('BL %'),
                        orElse: () => '',
                      );

                      final blPercent = double.tryParse(runner[blKey] ?? '') ?? 0.0;
                      final showBl = blPercent >= 15.0;
                      print('BL %: $blPercent → showBl: $showBl');



                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
                        child: Row(
                          children: [
                            // Horse No with custom saddlecloth style
                            SizedBox(
                              width: 40, // Adjust width to fit the saddlecloth
                              child: buildSaddleCloth(horseNo),
                            ),

                            // Barrier (Now wrapped in GestureDetector)
                            SizedBox(
                              width: 40, // Adjust width if needed
                              child: GestureDetector(
                                onTap: () {
                                  showDialog(
                                    context: context,
                                    builder: (_) => BarrierStatsPopup(runner: runner),  // Show BarrierStatsPopup
                                  );
                                },
                                child: Center( // Center-align the barrier value
                                  child: Text(
                                    barrier,
                                    textAlign: TextAlign.center,
                                    style: const TextStyle(
                                      decoration: TextDecoration.underline,  // Make the barrier clickable like a link
                                      color: Colors.blue,
                                    ),
                                  ),
                                ),
                              ),
                            ),



                            // Lead, BL, and Death Dots - each in their own column
                            SizedBox(
                              width: 16,
                              child: Center(
                                child: Icon(
                                  Icons.circle,
                                  size: 16,
                                  color: showLead ? Colors.green : Colors.transparent,
                                  shadows: showLead
                                      ? null
                                      : [const Shadow(color: Colors.black, offset: Offset(0, 0), blurRadius: 0)],
                                ),
                              ),
                            ),
                            SizedBox(
                              width: 16,
                              child: Center(
                                child: Icon(
                                  Icons.circle,
                                  size: 16,
                                  color: showBl ? Colors.orange : Colors.transparent,
                                  shadows: showBl
                                      ? null
                                      : [const Shadow(color: Colors.black, offset: Offset(0, 0), blurRadius: 0)],
                                ),
                              ),
                            ),
                            SizedBox(
                              width: 16,
                              child: Center(
                                child: Icon(
                                  Icons.circle,
                                  size: 16,
                                  color: showDeath ? Colors.red : Colors.transparent,
                                  shadows: showDeath
                                      ? null
                                      : [const Shadow(color: Colors.black, offset: Offset(0, 0), blurRadius: 0)],
                                ),
                              ),
                            ),

                            // Horse (fills the remaining space)
                            Expanded(
                              child: Text(
                                runner['Horse'] ?? '',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),

                            // Trainer
                            SizedBox(
                              width: 150,
                              child: GestureDetector(
                                onTap: () {
                                  showDialog(
                                    context: context,
                                    builder: (_) => TrainerStatsPopup(runner: runner),
                                  );
                                },
                                child: Text(
                                  runner['Trainer'] ?? '',
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    decoration: TextDecoration.underline,
                                    color: Colors.blue,
                                  ),
                                ),
                              ),
                            ),


                            // Driver (tap to open DriverStatsPopup)
                            SizedBox(
                              width: 150,
                              child: GestureDetector(
                                onTap: () {
                                  showDialog(
                                    context: context,
                                    builder: (_) => DriverStatsPopup(runner: runner),
                                  );
                                },
                                child: Text(
                                  runner['Driver'] ?? '',
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                    decoration: TextDecoration.underline,
                                    color: Colors.blue,
                                  ),
                                ),
                              ),
                            ),

                          ],
                        ),
                      );



                    },
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



// Helper to align the text in each data cell
Widget right(String? text, {Color? color}) {
  return Align(
    alignment: Alignment.centerRight,
    child: Text(
      text ?? '',
      style: TextStyle(fontSize: 12, color: color),
    ),
  );
}


class DriverStatsPopup extends StatefulWidget {
  final Map<String, String> runner; // Pass the driver data here

  const DriverStatsPopup({super.key, required this.runner});

  @override
  _DriverStatsPopupState createState() => _DriverStatsPopupState();
}

class _DriverStatsPopupState extends State<DriverStatsPopup> {
  // State for the selected period (30, 90, 180, 365, All)
  String selectedPeriod = '30';

  // Helper method to determine the color of ROI
  Color _getROIColor(String roi) {
    final roiValue = double.tryParse(roi) ?? 0;
    return roiValue > 0 ? Colors.green : Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    final driver = widget.runner;

    // Prepare rows: label, races, wins, win SR, pla, pla SR, ROI
    final rows = [
      {
        'label': '30d',
        'Races': driver['Dr 30 Sts'] ?? '0',
        'Wins': driver['Dr 30 Win'] ?? '0',
        'Win %': driver['Dr 30 Win %'] ?? '0',
        'Pla': driver['Dr 30 Pla'] ?? '0',
        'Pla %': driver['Dr 30 Pla %'] ?? '0',
        'ROI': driver['Dr 30 ROI %'] ?? '0',
      },
      {
        'label': '90d',
        'Races': driver['Dr 90 Sts'] ?? '0',
        'Wins': driver['Dr 90 Win'] ?? '0',
        'Win %': driver['Dr 90 Win %'] ?? '0',
        'Pla': driver['Dr 90 Pla'] ?? '0',
        'Pla %': driver['Dr 90 Pla %'] ?? '0',
        'ROI': driver['Dr 90 ROI %'] ?? '0',
      },
      {
        'label': '180d',
        'Races': driver['Dr 180 Sts'] ?? '0',
        'Wins': driver['Dr 180 Win'] ?? '0',
        'Win %': driver['Dr 180 Win %'] ?? '0',
        'Pla': driver['Dr 180 Pla'] ?? '0',
        'Pla %': driver['Dr 180 Pla %'] ?? '0',
        'ROI': driver['Dr 180 ROI %'] ?? '0',
      },
      {
        'label': '365d',
        'Races': driver['Dr 365 Sts'] ?? '0',
        'Wins': driver['Dr 365 Win'] ?? '0',
        'Win %': driver['Dr 365 Win %'] ?? '0',
        'Pla': driver['Dr 365 Pla'] ?? '0',
        'Pla %': driver['Dr 365 Pla %'] ?? '0',
        'ROI': driver['Dr 365 ROI %'] ?? '0',
      },
      {
        'label': 'All',
        'Races': driver['Dr All Sts'] ?? '0',
        'Wins': driver['Dr All Win'] ?? '0',
        'Win %': driver['Dr All Win %'] ?? '0',
        'Pla': driver['Dr All Pla'] ?? '0',
        'Pla %': driver['Dr All Pla %'] ?? '0',
        'ROI': driver['Dr All ROI %'] ?? '0',
      },
    ];

    return AlertDialog(
      title: Text('Driver Stats: ${driver['Driver'] ?? 'Unknown'}'),
      content: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTableTheme(
          data: DataTableThemeData(
            headingRowHeight: 24,
            dataRowMinHeight: 20,
            dataRowMaxHeight: 24,
          ),
          child: DataTable(
            headingRowColor: MaterialStateProperty.all(Colors.blue[50]),
            columns: [
              const DataColumn(
                label: Text('', style: TextStyle(fontSize: 12)),
              ),
              const DataColumn(
                label: Align(
                  alignment: Alignment.centerRight,
                  child: Text('Races', style: TextStyle(fontSize: 12)),
                ),
              ),
              const DataColumn(
                label: Align(
                  alignment: Alignment.centerRight,
                  child: Text('Wins (SR)', style: TextStyle(fontSize: 12)),
                ),
              ),
              const DataColumn(
                label: Align(
                  alignment: Alignment.centerRight,
                  child: Text('Pla (SR)', style: TextStyle(fontSize: 12)),
                ),
              ),
              const DataColumn(
                label: Align(
                  alignment: Alignment.centerRight,
                  child: Text('ROI', style: TextStyle(fontSize: 12)),
                ),
              ),
            ],
            rows: rows.map((row) {
              final roiValue = double.tryParse(row['ROI'] ?? '') ?? 0;
              final roiColor = roiValue >= 0 ? Colors.green : Colors.red;

              // Formatting the numbers for better readability
              String formatStat(String? raw, String? pct) {
                final intVal = double.tryParse(raw ?? '')?.toInt() ?? 0;
                final pctVal = double.tryParse(pct ?? '')?.toStringAsFixed(0) ?? '0';
                return '$intVal ($pctVal%)';
              }


              return DataRow(cells: [
                DataCell(Text(row['label'] ?? '', style: const TextStyle(fontSize: 12))),
                DataCell(right((double.tryParse(row['Races'] ?? '')?.toInt().toString()))),
                DataCell(right(formatStat(row['Wins'], row['Win %']))),
                DataCell(right(formatStat(row['Pla'], row['Pla %']))),
                DataCell(right('${roiValue.toStringAsFixed(1)}%', color: roiColor)),
              ]);
            }).toList(),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );







  }











  // Method to build period toggle buttons
  Widget _buildPeriodButton(String period) {
    return TextButton(
      onPressed: () {
        setState(() {
          selectedPeriod = period;
        });
      },
      child: Text(
        period,
        style: TextStyle(
          color: selectedPeriod == period ? Colors.blue : Colors.black,
          fontWeight: selectedPeriod == period ? FontWeight.bold : FontWeight.normal,
        ),
      ),
    );
  }
}




// 📊 TrainerStatsPopup
class TrainerStatsPopup extends StatelessWidget {
  final Map<String, String> runner;

  const TrainerStatsPopup({super.key, required this.runner});

  Color _getROIColor(String roi) {
    final roiValue = double.tryParse(roi) ?? 0;
    return roiValue > 0 ? Colors.green : Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    final trainer = runner;

    final rows = [
      {
        'label': '30d',
        'Races': trainer['Tr 30 Sts'] ?? '0',
        'Wins': trainer['Tr 30 Win'] ?? '0',
        'Win %': trainer['Tr 30 Win %'] ?? '0',
        'Pla': trainer['Tr 30 Pla'] ?? '0',
        'Pla %': trainer['Tr 30 Pla %'] ?? '0',
        'ROI': trainer['Tr 30 ROI %'] ?? '0',
      },
      {
        'label': '90d',
        'Races': trainer['Tr 90 Sts'] ?? '0',
        'Wins': trainer['Tr 90 Win'] ?? '0',
        'Win %': trainer['Tr 90 Win %'] ?? '0',
        'Pla': trainer['Tr 90 Pla'] ?? '0',
        'Pla %': trainer['Tr 90 Pla %'] ?? '0',
        'ROI': trainer['Tr 90 ROI %'] ?? '0',
      },
      {
        'label': '180d',
        'Races': trainer['Tr 180 Sts'] ?? '0',
        'Wins': trainer['Tr 180 Win'] ?? '0',
        'Win %': trainer['Tr 180 Win %'] ?? '0',
        'Pla': trainer['Tr 180 Pla'] ?? '0',
        'Pla %': trainer['Tr 180 Pla %'] ?? '0',
        'ROI': trainer['Tr 180 ROI %'] ?? '0',
      },
      {
        'label': '365d',
        'Races': trainer['Tr 365 Sts'] ?? '0',
        'Wins': trainer['Tr 365 Win'] ?? '0',
        'Win %': trainer['Tr 365 Win %'] ?? '0',
        'Pla': trainer['Tr 365 Pla'] ?? '0',
        'Pla %': trainer['Tr 365 Pla %'] ?? '0',
        'ROI': trainer['Tr 365 ROI %'] ?? '0',
      },
      {
        'label': 'All',
        'Races': trainer['Tr All Sts'] ?? '0',
        'Wins': trainer['Tr All Win'] ?? '0',
        'Win %': trainer['Tr All Win %'] ?? '0',
        'Pla': trainer['Tr All Pla'] ?? '0',
        'Pla %': trainer['Tr All Pla %'] ?? '0',
        'ROI': trainer['Tr All ROI %'] ?? '0',
      },
    ];

    return AlertDialog(
      title: Text('Trainer Stats: ${trainer['Trainer'] ?? 'Unknown'}'),
      content: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: DataTableTheme(
          data: const DataTableThemeData(
            headingRowHeight: 24,
            dataRowMinHeight: 20,
            dataRowMaxHeight: 24,
          ),
          child: DataTable(
            headingRowColor: MaterialStateProperty.all(Colors.blue[50]),
            columns: const [
              DataColumn(label: Text('', style: TextStyle(fontSize: 12))),
              DataColumn(label: Text('Races', style: TextStyle(fontSize: 12))),
              DataColumn(label: Text('Wins (SR)', style: TextStyle(fontSize: 12))),
              DataColumn(label: Text('Pla (SR)', style: TextStyle(fontSize: 12))),
              DataColumn(label: Text('ROI', style: TextStyle(fontSize: 12))),
            ],
            rows: rows.map((row) {
              final roiValue = double.tryParse(row['ROI'] ?? '') ?? 0;
              final roiColor = roiValue >= 0 ? Colors.green : Colors.red;

              String formatStat(String? raw, String? pct) {
                final intVal = double.tryParse(raw ?? '')?.toInt() ?? 0;
                final pctVal = double.tryParse(pct ?? '')?.toStringAsFixed(0) ?? '0';
                return '$intVal ($pctVal%)';
              }

              return DataRow(cells: [
                DataCell(Text(row['label'] ?? '', style: const TextStyle(fontSize: 12))),
                DataCell(right((double.tryParse(row['Races'] ?? '')?.toInt().toString()))),
                DataCell(right(formatStat(row['Wins'], row['Win %']))),
                DataCell(right(formatStat(row['Pla'], row['Pla %']))),
                DataCell(right('${roiValue.toStringAsFixed(1)}%', color: roiColor)),
              ]);
            }).toList(),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );
  }
}


class BarrierStatsPopup extends StatelessWidget {
  final Map<String, String> runner;

  const BarrierStatsPopup({super.key, required this.runner});

  Color _getROIColor(String roi) {
    final roiValue = double.tryParse(roi) ?? 0;
    return roiValue > 0 ? Colors.green : Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    final barrier = runner;

    final rows = [
      {
        'label': '30d',
        'Races': '<placeholder>',  // Placeholder for now
        'Wins': '<placeholder>',
        'Win %': '<placeholder>',
        'Pla': '<placeholder>',
        'Pla %': '<placeholder>',
        'ROI': '<placeholder>',
      },
      {
        'label': '90d',
        'Races': '<placeholder>',
        'Wins': '<placeholder>',
        'Win %': '<placeholder>',
        'Pla': '<placeholder>',
        'Pla %': '<placeholder>',
        'ROI': '<placeholder>',
      },
      {
        'label': '180d',
        'Races': '<placeholder>',
        'Wins': '<placeholder>',
        'Win %': '<placeholder>',
        'Pla': '<placeholder>',
        'Pla %': '<placeholder>',
        'ROI': '<placeholder>',
      },
      {
        'label': '365d',
        'Races': '<placeholder>',
        'Wins': '<placeholder>',
        'Win %': '<placeholder>',
        'Pla': '<placeholder>',
        'Pla %': '<placeholder>',
        'ROI': '<placeholder>',
      },
      {
        'label': 'All',
        'Races': barrier['Br Sts'] ?? '0',
        'Wins': barrier['Br Wins'] ?? '0',
        'Win %': barrier['Br Win %'] ?? '0',
        'Pla': barrier['Br Places'] ?? '0',
        'Pla %': barrier['Br Pla %'] ?? '0',
        'ROI': barrier['Br ROI %'] ?? '0',
      },
    ];

    return AlertDialog(
      title: Text('Barrier Stats: ${barrier['Barrier'] ?? 'Unknown'}'),
      content: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            DataTableTheme(
              data: const DataTableThemeData(
                headingRowHeight: 24,
                dataRowMinHeight: 20,
                dataRowMaxHeight: 24,
              ),
              child: DataTable(
                headingRowColor: MaterialStateProperty.all(Colors.blue[50]),
                columns: const [
                  DataColumn(label: Text('', style: TextStyle(fontSize: 12))),
                  DataColumn(label: Text('Races', style: TextStyle(fontSize: 12))),
                  DataColumn(label: Text('Wins (SR)', style: TextStyle(fontSize: 12))),
                  DataColumn(label: Text('Pla (SR)', style: TextStyle(fontSize: 12))),
                  DataColumn(label: Text('ROI', style: TextStyle(fontSize: 12))),
                ],
                rows: [
                  {
                    'label': '180d',
                    'Races': '<placeholder>',  // Placeholder for now
                    'Wins': '<placeholder>',
                    'Win %': '<placeholder>',
                    'Pla': '<placeholder>',
                    'Pla %': '<placeholder>',
                    'ROI': '<placeholder>',
                  },
                  {
                    'label': '365d',
                    'Races': '<placeholder>',
                    'Wins': '<placeholder>',
                    'Win %': '<placeholder>',
                    'Pla': '<placeholder>',
                    'Pla %': '<placeholder>',
                    'ROI': '<placeholder>',
                  },
                  {
                    'label': 'All',
                    'Races': barrier['Br Sts'] ?? '0',
                    'Wins': barrier['Br Wins'] ?? '0',
                    'Win %': barrier['Br Win %'] ?? '0',
                    'Pla': barrier['Br Places'] ?? '0',
                    'Pla %': barrier['Br Pla %'] ?? '0',
                    'ROI': barrier['Br ROI %'] ?? '0',
                  },
                ].map((row) {
                  final roiValue = double.tryParse(row['ROI'] ?? '') ?? 0;
                  final roiColor = roiValue >= 0 ? Colors.green : Colors.red;

                  String formatStat(String? raw, String? pct) {
                    final intVal = double.tryParse(raw ?? '')?.toInt() ?? 0;
                    final pctVal = double.tryParse(pct ?? '')?.toStringAsFixed(0) ?? '0';
                    return '$intVal ($pctVal%)';
                  }

                  return DataRow(cells: [
                    DataCell(Text(row['label'] ?? '', style: const TextStyle(fontSize: 12))),
                    DataCell(right((double.tryParse(row['Races'] ?? '')?.toInt().toString()))),
                    DataCell(right(formatStat(row['Wins'], row['Win %']))),
                    DataCell(right(formatStat(row['Pla'], row['Pla %']))),
                    DataCell(right('${roiValue.toStringAsFixed(1)}%', color: roiColor)),
                  ]);
                }).toList(),
              ),
            ),
            const SizedBox(height: 16),  // Add some space between the table and the text
            Text(
              'Statistics above relate only where Venue, Distance, Gait and Start Type matches',
              style: const TextStyle(fontSize: 12, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Close'),
        ),
      ],
    );




  }
}
