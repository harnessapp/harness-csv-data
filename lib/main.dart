import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:csv/csv.dart';

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
        child: ElevatedButton(
          onPressed: () {
            Navigator.of(context).push(MaterialPageRoute(
              builder: (context) => const UpcomingFieldsPage(),
            ));
          },
          child: const Text("Upcoming Fields"),
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
    final csvString = await rootBundle.loadString('assets/upcoming_fields.csv');
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
    final csvString = await rootBundle.loadString('assets/upcoming_fields.csv');
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
    final csvString = await rootBundle.loadString('assets/upcoming_fields.csv');
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
    final csvString = await rootBundle.loadString('assets/upcoming_fields.csv');
    final rows = const CsvToListConverter(eol: '\n').convert(csvString);
    final headers = rows.first.cast<String>();
    print('Headers:');
    for (var header in headers) {
      print('→ "$header"');
    }


    return rows.skip(1).map((row) {
      final Map<String, String> rowMap = {};
      for (int i = 0; i < headers.length; i++) {
        rowMap[headers[i]] = row[i]?.toString() ?? '';
      }
      return rowMap;
    }).toList();
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
              "($sample) Benchmarks: $bmLT | $bmQ1 | $bmQ2 | $bmQ3 | $bmQ4",
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

                            // Barrier
                            SizedBox(
                              width: 40, // Adjust width if needed
                              child: Center( // Center-align the barrier value
                                child: Text(barrier, textAlign: TextAlign.center), // Ensure text is center-aligned
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
                              child: Text(
                                runner['Trainer'] ?? '',
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),

                            // Driver
                            SizedBox(
                              width: 150,
                              child: Text(
                                runner['Driver'] ?? '',
                                overflow: TextOverflow.ellipsis,
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



