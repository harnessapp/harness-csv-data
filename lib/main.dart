import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:csv/csv.dart';
import 'next_up_page.dart';
import 'csv_utils.dart';
import 'runner_chip.dart';
import 'drivers_page.dart';  // Add this import for Drivers Page
// import 'trainers_page.dart';  // ← remove this (or leave if used elsewhere)
import 'drivers_menu_page.dart';
import 'trainers_menu_page.dart';  // ← add this



void main() {
  runApp(const HarnessApp());
}

class RunnerChipSafe extends StatelessWidget {
  final String runnerName;
  final num ldPercentage, blPercentage, dthPercentage;
  const RunnerChipSafe({
    super.key,
    required this.runnerName,
    required this.ldPercentage,
    required this.blPercentage,
    required this.dthPercentage,
  });

  String _fmt(num v) {
    final d = v.toDouble();
    if (!d.isFinite) return '0%';
    final clamped = d.clamp(0, 100);
    return '${clamped.round()}%';
  }

  Widget _pill(String label, Color bg) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: bg.withOpacity(0.15),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: bg.withOpacity(0.3)),
      ),
      child: Text(label, style: const TextStyle(fontSize: 12)),
    );
  }

  @override
  Widget build(BuildContext context) {
    // Row is min-sized and can wrap if the parent is tighter.
    return Wrap(
      spacing: 6,
      runSpacing: 4,
      alignment: WrapAlignment.end,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        _pill('Ld ${_fmt(ldPercentage)}', const Color(0xFF4CAF50)),
        _pill('BL ${_fmt(blPercentage)}', const Color(0xFFFFC107)),
        _pill('Dth ${_fmt(dthPercentage)}', const Color(0xFFF44336)),
      ],
    );
  }
}


class RunnerChipCompact extends StatelessWidget {
  final num ld, bl, dth;
  final double width;
  final double height;

  const RunnerChipCompact({
    super.key,
    required this.ld,
    required this.bl,
    required this.dth,
    this.width = 160,   // tweak 140–180 to taste
    this.height = 32,   // compact height
  });

  String _fmt(num v) {
    final d = v.toDouble();
    if (!d.isFinite) return '0%';
    return '${d.clamp(0, 100).round()}%';
  }

  Widget _cell(String label, String value, Color color) {
    return Expanded(
      child: Container(
        height: height,
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
        decoration: BoxDecoration(
          color: color.withOpacity(0.12),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: color.withOpacity(0.25)),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(label,
                style: TextStyle(fontSize: 10, color: color.withOpacity(0.9))),
            const SizedBox(height: 2),
            Text(value,
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                maxLines: 1,
                overflow: TextOverflow.clip),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: width,
      height: height,
      child: Row(
        children: [
          _cell('Ld',  _fmt(ld),  const Color(0xFF4CAF50)),
          const SizedBox(width: 6),
          _cell('BL',  _fmt(bl),  const Color(0xFFFFC107)),
          const SizedBox(width: 6),
          _cell('Dth', _fmt(dth), const Color(0xFFF44336)),
        ],
      ),
    );
  }
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
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(
                    builder: (context) => const DriversMenuPage(), // New menu with 4 driver options
                  ),
                );
              },

              child: const Text("Drivers"),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: () {
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const TrainersMenuPage()),
                );
              },
              child: const Text("Trainers"),
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

DateTime? _parseDateFlexibleGlobal(String s) {
  final t = s.trim();
  if (RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(t)) {
    return DateTime.tryParse(t);
  }
  final m = RegExp(r'^(\d{1,2})/(\d{1,2})/(\d{4})$').firstMatch(t);
  if (m != null) {
    final d = int.parse(m.group(1)!);
    final mo = int.parse(m.group(2)!);
    final y = int.parse(m.group(3)!);
    return DateTime(y, mo, d);
  }
  return null;
}

String _prettyDateLabelGlobal(String raw) {
  const w = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
  const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  final dt = _parseDateFlexibleGlobal(raw);
  if (dt == null) return raw;
  final today = DateTime.now();
  final justToday = DateTime(today.year, today.month, today.day);
  final justThat  = DateTime(dt.year, dt.month, dt.day);
  final diffDays = justThat.difference(justToday).inDays;
  String base = '${w[dt.weekday - 1]} ${dt.day} ${m[dt.month - 1]}';
  if (dt.year != justToday.year) base += ' ${dt.year}';
  if (diffDays == 0) return 'Today · $base';
  if (diffDays == 1) return 'Tomorrow · $base';
  if (diffDays == -1) return 'Yesterday · $base';
  return base;
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

        return aDate.compareTo(bDate); // oldest first
      } catch (_) {
        return a.compareTo(b);
      }
    });

    return dates;
  }

  DateTime? _parseDateFlexible(String s) {
    final t = s.trim();
    if (RegExp(r'^\d{4}-\d{2}-\d{2}$').hasMatch(t)) {
      return DateTime.tryParse(t);
    }
    final m = RegExp(r'^(\d{1,2})/(\d{1,2})/(\d{4})$').firstMatch(t);
    if (m != null) {
      final d = int.parse(m.group(1)!);
      final mo = int.parse(m.group(2)!);
      final y = int.parse(m.group(3)!);
      return DateTime(y, mo, d);
    }
    return null;
  }

  String _prettyDateLabel(String raw) {
    const w = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
    const m = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];

    final dt = _parseDateFlexible(raw);
    if (dt == null) return raw;

    final today = DateTime.now();
    final justToday = DateTime(today.year, today.month, today.day);
    final justThat  = DateTime(dt.year, dt.month, dt.day);
    final diffDays = justThat.difference(justToday).inDays;

    String base = '${w[dt.weekday - 1]} ${dt.day} ${m[dt.month - 1]}';
    if (dt.year != justToday.year) base += ' ${dt.year}';

    if (diffDays == 0) return 'Today · $base';
    if (diffDays == 1) return 'Tomorrow · $base';
    if (diffDays == -1) return 'Yesterday · $base';
    return base;
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
                  child: Text(_prettyDateLabel(date)),
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
      appBar: AppBar(title: Text("Venues on ${_prettyDateLabelGlobal(selectedDate)}")),
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
      appBar: AppBar(title: Text("$venue • ${_prettyDateLabelGlobal(date)}")),
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

  // Chips
  Widget _pctChip(String label, double value, Color color) {
    final v = value.isFinite ? value : 0.0;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withOpacity(0.08),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withOpacity(0.25)),
      ),
      child: Text(
        '$label ${v.toStringAsFixed(0)}%',
        style: TextStyle(fontSize: 12, color: color, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _roiChip(String label, double roi) {
    final isPos = roi > 0;
    final base = isPos ? Colors.green : Colors.black87;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: isPos ? Colors.green.withOpacity(0.09) : Colors.grey.withOpacity(0.06),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: (isPos ? Colors.green : Colors.grey).withOpacity(0.30)),
      ),
      child: Text(
        '$label ${roi.toStringAsFixed(1)}%',
        style: TextStyle(fontSize: 12, color: base, fontWeight: FontWeight.w600),
      ),
    );
  }

  Widget _vSep() => Container(width: 1, height: 28, color: Colors.grey.withOpacity(0.28));


  // Saddlecloths
  Widget buildSaddleCloth(String horseNo) {
    switch (horseNo) {
      case '1':
        return Container(
          decoration: BoxDecoration(color: Colors.red, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        );
      case '2':
        return Container(
          decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        );
      case '3':
        return Container(
          decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      case '4':
        return Container(
          decoration: BoxDecoration(color: Colors.blue, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      case '5':
        return Container(
          decoration: BoxDecoration(color: Colors.yellow, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      case '6':
        return Container(
          decoration: BoxDecoration(color: Colors.green, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      case '7':
        return Container(
          decoration: BoxDecoration(color: Colors.black, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        );
      case '8':
        return Container(
          decoration: BoxDecoration(color: Colors.pink, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold))),
        );
      default:
        return Container(
          decoration: BoxDecoration(color: Colors.grey, borderRadius: BorderRadius.circular(4)),
          child: Center(child: Text(horseNo, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold))),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    final time = (race['Time'] ?? '').replaceAll(' AM', 'am').replaceAll(' PM', 'pm');
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

    return DefaultTabController(
      length: 5,
      initialIndex: 1, // default to Leaders
      child: Scaffold(
        appBar: AppBar(
          title: Text(
            "${race['Venue'] ?? ''} R$raceNo • ${_prettyDateLabelGlobal(race['Date'] ?? '')}",
          ),
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
          child: SingleChildScrollView(
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

                // Runners list (non-scrollable, sizes to content)
                FutureBuilder<List<Map<String, String>>>(
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
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      itemCount: runners.length + 1,
                      itemBuilder: (context, index) {
                        if (index < runners.length) {
                          final runner = runners[index];
                          final rawHorseNo = (runner['Horse No'] ?? '').trim();
                          final horseNo = rawHorseNo.endsWith('.0')
                              ? rawHorseNo.replaceAll('.0', '')
                              : rawHorseNo;

// ↓ make barrier lower-case once and detect scratching
                          final barrierRaw = (runner['Barrier'] ?? '').trim();
                          final barrier = barrierRaw.toLowerCase();
                          final bool isScratched = barrier.contains('scr');

                          double _pctParse(String? s) =>
                              double.tryParse((s ?? '').toString().replaceAll('%', '').trim()) ?? 0.0;

                          final ldPct = _pctParse(runner['Ld %']);
                          final dthPct = _pctParse(runner['Dth %']);
                          final blKey = runner.keys.firstWhere(
                                (key) => key.trim().toLowerCase().contains('bl %'),
                            orElse: () => 'BL %',
                          );
                          final blPercent = _pctParse(runner[blKey]);

// ↓ lights completely disabled if scratched
                          final showLead = !isScratched && barrier.contains('fr') && ldPct > 15;
                          final showBl   = !isScratched && blPercent >= 15.0;
                          final showDeath= !isScratched && dthPct > 15;

// ↓ common strike-through style (dimmed a touch)
                          const strikeColor = Colors.grey;
                          final TextStyle strike = const TextStyle(
                            decoration: TextDecoration.lineThrough,
                            color: strikeColor,
                          );

                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 8),
                            child: Row(
                              children: [
                                SizedBox(width: 40, child: buildSaddleCloth(horseNo)),

                                // Barrier (clickable). Keep underline, add strike if scratched.
                                SizedBox(
                                  width: 40,
                                  child: GestureDetector(
                                    onTap: () {
                                      showDialog(
                                        context: context,
                                        builder: (_) => BarrierStatsPopup(runner: runner),
                                      );
                                    },
                                    child: Center(
                                      child: Text(
                                        barrierRaw, // show original case
                                        textAlign: TextAlign.center,
                                        style: isScratched
                                            ? TextStyle(
                                          decoration: TextDecoration.combine(
                                            [TextDecoration.underline, TextDecoration.lineThrough],
                                          ),
                                          color: strikeColor,
                                        )
                                            : const TextStyle(
                                          decoration: TextDecoration.underline,
                                          color: Colors.blue,
                                        ),
                                      ),
                                    ),
                                  ),
                                ),

                                // Traffic lights — disappear when scratched
                                SizedBox(
                                  width: 16,
                                  child: Center(
                                    child: Icon(Icons.circle,
                                        size: 16,
                                        color: showLead ? Colors.green : Colors.transparent),
                                  ),
                                ),
                                SizedBox(
                                  width: 16,
                                  child: Center(
                                    child: Icon(Icons.circle,
                                        size: 16,
                                        color: showBl ? Colors.orange : Colors.transparent),
                                  ),
                                ),
                                SizedBox(
                                  width: 16,
                                  child: Center(
                                    child: Icon(Icons.circle,
                                        size: 16,
                                        color: showDeath ? Colors.red : Colors.transparent),
                                  ),
                                ),

                                // Horse name
                                Expanded(
                                  child: Text(
                                    runner['Horse'] ?? '',
                                    overflow: TextOverflow.ellipsis,
                                    style: isScratched ? strike : null,
                                  ),
                                ),

                                // Trainer (clickable)
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
                                      style: isScratched
                                          ? TextStyle(
                                        decoration: TextDecoration.combine(
                                          [TextDecoration.underline, TextDecoration.lineThrough],
                                        ),
                                        color: strikeColor,
                                      )
                                          : const TextStyle(
                                        decoration: TextDecoration.underline,
                                        color: Colors.blue,
                                      ),
                                    ),
                                  ),
                                ),

                                // Driver (clickable)
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
                                      style: isScratched
                                          ? TextStyle(
                                        decoration: TextDecoration.combine(
                                          [TextDecoration.underline, TextDecoration.lineThrough],
                                        ),
                                        color: strikeColor,
                                      )
                                          : const TextStyle(
                                        decoration: TextDecoration.underline,
                                        color: Colors.blue,
                                      ),
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          );

                        } else {
                          return const Padding(
                            padding: EdgeInsets.only(top: 2, bottom: 2),
                            child: Divider(thickness: 1, color: Colors.grey),
                          );
                        }
                      },
                    );
                  },
                ),

                // --- RACE-LEVEL TABS -------------------------------------------------
                const SizedBox(height: 4),
                const TabBar(
                  isScrollable: true,
                  tabs: [
                    Tab(text: 'Summary'),
                    Tab(text: 'Bell'),
                    Tab(text: 'Stats'),
                    Tab(text: 'Signals'),
                    Tab(text: 'Notes'),
                  ],
                ),
                const SizedBox(height: 6),

                SizedBox(
                  height: 750,
                  child: TabBarView(
                    children: [
                      // SUMMARY
                      const Center(child: Text('Summary placeholder')),

                      // BELL (front-row only, horse no order, triple Ld% bar)
                      FutureBuilder<List<Map<String, String>>>(
                        future: loadCSV(),
                        builder: (context, snap) {
                          if (snap.connectionState == ConnectionState.waiting) {
                            return const Center(child: CircularProgressIndicator());
                          }
                          if (snap.hasError) {
                            return Center(child: Text('Error: ${snap.error}'));
                          }

                          final rows = (snap.data ?? [])
                              .where((row) =>
                          (row['Race No']?.trim() ?? '') == raceNo &&
                              (row['Venue']?.trim() ?? '') == (race['Venue'] ?? '') &&
                              (row['Date']?.trim() ?? '') == (race['Date'] ?? ''))
                              .toList();

                          double pct(String? s) {
                            final raw = (s ?? '').replaceAll('%', '').trim();
                            final v = double.tryParse(raw);
                            if (v == null || v.isNaN || v.isInfinite) return 0.0;
                            return v.clamp(0.0, 100.0);
                          }

                          String tidyNo(String s) =>
                              s.trim().endsWith('.0') ? s.trim().replaceAll('.0', '') : s.trim();

                          int horseNoNum(Map<String, String> r) =>
                              int.tryParse(tidyNo(r['Horse No'] ?? '')) ?? 9999;

                          final front = rows
                              .where((r) => (r['Barrier'] ?? '').toLowerCase().contains('fr'))
                              .toList()
                            ..sort((a, b) => horseNoNum(a).compareTo(horseNoNum(b)));

                          if (front.isEmpty) {
                            return const Center(child: Text('No front-row runners found.'));
                          }

                          double frac(num v) {
                            final d = v.toDouble();
                            if (!d.isFinite) return 0.0;
                            return (d / 100.0).clamp(0.0, 1.0);
                          }

                          double toAlignX(double f) => (-1.0 + 2.0 * f).clamp(-1.0, 1.0);
                          Widget marker(Color c) => Container(
                            width: 3, height: 10,
                            decoration: BoxDecoration(color: c.withOpacity(0.55), borderRadius: BorderRadius.circular(1)),
                          );

                          return CustomScrollView(
                            slivers: [
                              SliverList(
                                delegate: SliverChildBuilderDelegate(
                                      (context, i) {
                                    final r = front[i];
                                    final cloth = tidyNo(r['Horse No'] ?? '');
                                    final horse = (r['Horse'] ?? '').trim();
                                    final barrier = (r['Barrier'] ?? '').trim();

                                    final ld = pct(r['Ld %']);
                                    final blKey = r.keys.firstWhere(
                                          (k) => k.trim().toLowerCase().contains('bl %'),
                                      orElse: () => 'BL %',
                                    );
                                    final bl = pct(r[blKey]);
                                    final dth = pct(r['Dth %']);

                                    final triple = (frac(ld) * 2.5).clamp(0.0, 1.0);
                                    final blFrac = (frac(bl) * 2.5).clamp(0.0, 1.0);
                                    final dthFrac = (frac(dth) * 2.5).clamp(0.0, 1.0);


                                    return Padding(
                                      padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 8),
                                      child: Column(
                                        children: [
                                          // ROW: enforce safe space for the chip
                                          // ... inside the SliverChildBuilderDelegate -> return Padding(... Column(children: [ ... ]))
                                          LayoutBuilder(
                                            builder: (context, constraints) {
                                              // Fixed bits
                                              const clothW = 36.0;
                                              const clothH = 24.0;
                                              const gapLeft = 8.0;   // between cloth and text
                                              const gapMid  = 8.0;   // between text and chip
                                              final totalW  = constraints.maxWidth;

                                              // Reserve a safe slice for the chip (cannot overflow)
                                              final chipW = (totalW * 0.34).clamp(120.0, 200.0);

                                              // Whatever remains is for the left (cloth + text)
                                              final leftW = (totalW - chipW - gapMid).clamp(0.0, totalW);

                                              // Inside the left, cloth is fixed; text gets the remainder:
                                              final textW = (leftW - clothW - gapLeft).clamp(0.0, leftW);

                                              return Row(
                                                crossAxisAlignment: CrossAxisAlignment.center,
                                                children: [
                                                  // LEFT: fixed area
                                                  SizedBox(
                                                    width: leftW,
                                                    child: Row(
                                                      children: [
                                                        SizedBox(width: clothW, height: clothH, child: buildSaddleCloth(cloth)),
                                                        const SizedBox(width: gapLeft),
                                                        SizedBox(
                                                          width: textW,
                                                          child: Column(
                                                            crossAxisAlignment: CrossAxisAlignment.start,
                                                            children: [
                                                              Text(horse, maxLines: 1, overflow: TextOverflow.ellipsis),
                                                              Text(
                                                                barrier,
                                                                maxLines: 1,
                                                                overflow: TextOverflow.ellipsis,
                                                                style: const TextStyle(fontSize: 12, color: Colors.grey),
                                                              ),
                                                            ],
                                                          ),
                                                        ),
                                                      ],
                                                    ),
                                                  ),

                                                  const SizedBox(width: gapMid),

                                                  // --- RIGHT: chip area (hard width; cannot overflow) ---
                                                  SizedBox(
                                                    width: 200, // safe fixed width; tune 140–200 if you like
                                                    child: Align(
                                                      alignment: Alignment.centerRight,
                                                      child: RunnerChipSafe(
                                                        runnerName: horse,
                                                        ldPercentage: ld,
                                                        blPercentage: bl,
                                                        dthPercentage: dth,
                                                      ),
                                                    ),
                                                  ),

                                                ],
                                              );
                                            },
                                          ),


                                          const SizedBox(height: 6),

                                          // BAR: clipped, fraction-based markers (cannot overflow)
                                          ClipRRect(
                                            borderRadius: BorderRadius.circular(6),
                                            child: Stack(
                                              children: [
                                                LinearProgressIndicator(
                                                  value: triple,
                                                  minHeight: 10,
                                                  backgroundColor: Colors.grey.withOpacity(0.18),
                                                  valueColor: const AlwaysStoppedAnimation<Color>(Colors.green),
                                                ),
                                                Positioned.fill(
                                                  child: Align(
                                                    alignment: Alignment(toAlignX(blFrac), 0),
                                                    child: IgnorePointer(child: marker(Colors.orange)),
                                                  ),
                                                ),
                                                Positioned.fill(
                                                  child: Align(
                                                    alignment: Alignment(toAlignX(dthFrac), 0),
                                                    child: IgnorePointer(child: marker(Colors.red)),
                                                  ),
                                                ),
                                              ],
                                            ),
                                          ),
                                        ],
                                      ),
                                    );
                                  },
                                  childCount: front.length,
                                ),
                              ),
                            ],
                          );
                        },
                      )
                      ,







                      // STATS TABLE: Barrier ROI + Trainer ROI + Driver ROI (compact with headings)
                      FutureBuilder<List<Map<String, String>>>(
                        future: loadCSV(),
                        builder: (context, snap) {
                          if (snap.connectionState == ConnectionState.waiting) {
                            return const Center(child: CircularProgressIndicator());
                          }
                          if (snap.hasError) {
                            return Center(child: Text('Error: ${snap.error}'));
                          }

                          final rows = (snap.data ?? [])
                              .where((row) =>
                          (row['Race No']?.trim() ?? '') == raceNo &&
                              (row['Venue']?.trim() ?? '') == (race['Venue'] ?? '') &&
                              (row['Date']?.trim() ?? '') == (race['Date'] ?? ''))
                              .toList();

                          double roi(String? s) =>
                              double.tryParse((s ?? '').replaceAll('%', '').trim()) ?? 0.0;
                          String tidyNo(String s) =>
                              s.trim().endsWith('.0') ? s.trim().replaceAll('.0', '') : s.trim();
                          int horseNoNum(Map<String, String> r) =>
                              int.tryParse(tidyNo(r['Horse No'] ?? '')) ?? 9999;

                          rows.sort((a, b) => horseNoNum(a).compareTo(horseNoNum(b)));

                          if (rows.isEmpty) {
                            return const Center(child: Text('No runners found for this race.'));
                          }

                          Color roiColor(double val) => val > 0 ? Colors.green : Colors.black87;
                          Text pctCell(double val) => Text(
                            '${val.toStringAsFixed(0)}%',
                            style: TextStyle(color: roiColor(val)),
                          );
                          Widget rightCell(Widget w) =>
                              Align(alignment: Alignment.centerRight, child: w);

                          return SingleChildScrollView(
                            scrollDirection: Axis.horizontal,
                            child: SingleChildScrollView(
                              scrollDirection: Axis.vertical,
                              child: DataTable(
                                columnSpacing: 16,
                                headingRowHeight: 32,
                                dataRowMinHeight: 28,
                                dataRowMaxHeight: 32,
                                headingRowColor:
                                MaterialStateColor.resolveWith((_) => Colors.grey.shade200),
                                columns: const [
                                  DataColumn(label: Text('No')),
                                  DataColumn(label: Text('Horse')),
                                  DataColumn(label: Text('Barrier')),
                                  DataColumn(label: Text('Br ROI')),
                                  DataColumn(label: Text('Tr 30d')),
                                  DataColumn(label: Text('Tr 90d')),
                                  DataColumn(label: Text('Tr 365d')),
                                  DataColumn(label: Text('Tr All')),
                                  DataColumn(label: Text('Dr 30d')),
                                  DataColumn(label: Text('Dr 90d')),
                                  DataColumn(label: Text('Dr 365d')),
                                  DataColumn(label: Text('Dr All')),
                                ],
                                rows: rows.map((r) {
                                  final no = tidyNo(r['Horse No'] ?? '');
                                  final horse = (r['Horse'] ?? '').trim();
                                  final barrierTxt = (r['Barrier'] ?? '').trim();

                                  final br = roi(r['Br ROI %']);

                                  final tr30 = roi(r['Tr 30 ROI %']);
                                  final tr90 = roi(r['Tr 90 ROI %']);
                                  final tr365 = roi(r['Tr 365 ROI %']);
                                  final trAll = roi(r['Tr All ROI %']);

                                  final dr30 = roi(r['Dr 30 ROI %']);
                                  final dr90 = roi(r['Dr 90 ROI %']);
                                  final dr365 = roi(r['Dr 365 ROI %']);
                                  final drAll = roi(r['Dr All ROI %']);

                                  return DataRow(cells: [
                                    DataCell(Text(no)),
                                    DataCell(Text(horse, overflow: TextOverflow.ellipsis)),
                                    DataCell(Text(barrierTxt)),
                                    DataCell(rightCell(pctCell(br))),
                                    DataCell(rightCell(pctCell(tr30))),
                                    DataCell(rightCell(pctCell(tr90))),
                                    DataCell(rightCell(pctCell(tr365))),
                                    DataCell(rightCell(pctCell(trAll))),
                                    DataCell(rightCell(pctCell(dr30))),
                                    DataCell(rightCell(pctCell(dr90))),
                                    DataCell(rightCell(pctCell(dr365))),
                                    DataCell(rightCell(pctCell(drAll))),
                                  ]);
                                }).toList(),
                              ),
                            ),
                          );
                        },
                      ),



                      const Center(child: Text('Signals placeholder')),
                      const Center(child: Text('Notes placeholder')),
                    ],
                  ),
                ),
                // -------------------------------------------------------------------
              ],
            ),
          ),
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
  final Map<String, String> runner;

  const DriverStatsPopup({super.key, required this.runner});

  @override
  _DriverStatsPopupState createState() => _DriverStatsPopupState();
}

class _DriverStatsPopupState extends State<DriverStatsPopup> {
  String selectedPeriod = '30';

  Color _getROIColor(String roi) {
    final roiValue = double.tryParse(roi) ?? 0;
    return roiValue > 0 ? Colors.green : Colors.red;
  }

  @override
  Widget build(BuildContext context) {
    final driver = widget.runner;

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
            columns: const [
              DataColumn(label: Text('', style: TextStyle(fontSize: 12))),
              DataColumn(label: Align(alignment: Alignment.centerRight, child: Text('Races', style: TextStyle(fontSize: 12)))),
              DataColumn(label: Align(alignment: Alignment.centerRight, child: Text('Wins (SR)', style: TextStyle(fontSize: 12)))),
              DataColumn(label: Align(alignment: Alignment.centerRight, child: Text('Pla (SR)', style: TextStyle(fontSize: 12)))),
              DataColumn(label: Align(alignment: Alignment.centerRight, child: Text('ROI', style: TextStyle(fontSize: 12)))),
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
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
      ],
    );
  }

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
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
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
        'Races': '<placeholder>',
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
            const SizedBox(height: 16),
            const Text(
              'Statistics above relate only where Venue, Distance, Gait and Start Type matches',
              style: TextStyle(fontSize: 12, color: Colors.grey),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
      ],
    );
  }
}
