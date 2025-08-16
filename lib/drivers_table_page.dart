import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:csv/csv.dart';

class DriversTablePage extends StatefulWidget {
  final String title;
  final String csvAssetPath;

  const DriversTablePage({
    super.key,
    required this.title,
    required this.csvAssetPath,
  });

  @override
  State<DriversTablePage> createState() => _DriversTablePageState();
}

class _DriversTablePageState extends State<DriversTablePage> {
  late Future<List<Map<String, dynamic>>> _tableFuture;

  @override
  void initState() {
    super.initState();
    _tableFuture =
        _buildRowsWithUpcoming(widget.csvAssetPath, 'assets/upcoming_fields.csv');
  }

  // ---------- CSV LOADERS ----------
  Future<List<List<dynamic>>> _loadCsv(String assetPath) async {
    final contents = await rootBundle.loadString(assetPath);
    return const CsvToListConverter().convert(contents);
  }

  int _headerIndex(List<dynamic> header, List<String> names) {
    for (var i = 0; i < header.length; i++) {
      final h = '${header[i]}'.trim().toLowerCase();
      for (final n in names) {
        if (h == n.toLowerCase()) return i;
      }
    }
    return -1;
  }

  DateTime? _parseDateTime(String? dateStr, String? timeStr) {
    if (dateStr == null || dateStr.trim().isEmpty) return null;
    final d = dateStr.trim();
    final t = (timeStr ?? '').trim();

    final candidates = <String>[
      '$d $t',
      d,
    ];

    // Simple manual parsing to cover common patterns without intl package.
    for (final candidate in candidates) {
      try {
        final parts = candidate.split(' ');
        if (parts.isEmpty) continue;

        DateTime? date;
        final dm = RegExp(r'^(\d{1,2})/(\d{1,2})/(\d{4})$');       // dd/MM/yyyy
        final ym = RegExp(r'^(\d{4})-(\d{2})-(\d{2})$');           // yyyy-MM-dd
        if (dm.hasMatch(parts[0])) {
          final m = dm.firstMatch(parts[0])!;
          date = DateTime(int.parse(m.group(3)!), int.parse(m.group(2)!), int.parse(m.group(1)!));
        } else if (ym.hasMatch(parts[0])) {
          final m = ym.firstMatch(parts[0])!;
          date = DateTime(int.parse(m.group(1)!), int.parse(m.group(2)!), int.parse(m.group(3)!));
        }
        if (date == null) continue;

        int hh = 0, min = 0;
        if (parts.length >= 2 && parts[1].isNotEmpty) {
          var time = parts[1].toLowerCase();
          final hasAmPm = time.endsWith('am') || time.endsWith('pm');
          time = time.replaceAll('am', '').replaceAll('pm', '').trim();

          final tm = RegExp(r'^(\d{1,2}):(\d{2})$'); // H:MM
          if (tm.hasMatch(time)) {
            final m = tm.firstMatch(time)!;
            hh = int.parse(m.group(1)!);
            min = int.parse(m.group(2)!);
            if (hasAmPm && timeStr != null) {
              final isPM = timeStr.toLowerCase().contains('pm');
              if (isPM && hh < 12) hh += 12;
              if (!isPM && hh == 12) hh = 0;
            }
          } else {
            final hm = RegExp(r'^(\d{1,2})$'); // H only
            if (hm.hasMatch(time)) {
              hh = int.parse(hm.firstMatch(time)!.group(1)!);
              final isPM = (timeStr ?? '').toLowerCase().contains('pm');
              if (isPM && hh < 12) hh += 12;
              if (!isPM && hh == 12) hh = 0;
            }
          }
        }
        return DateTime(date.year, date.month, date.day, hh, min);
      } catch (_) {}
    }
    return null;
  }

  Future<List<Map<String, dynamic>>> _buildRowsWithUpcoming(
      String driversCsvAsset,
      String upcomingCsvAsset,
      ) async {
    // Load drivers
    final driversRaw = await _loadCsv(driversCsvAsset);
    if (driversRaw.isEmpty) return [];
    final driversBody =
    driversRaw.length > 1 ? driversRaw.sublist(1) : <List<dynamic>>[];

    final driversRows = driversBody.map<Map<String, dynamic>>((row) {
      return {
        'Driver': row.isNotEmpty ? row[0] : '',
        'Starts': row.length > 1 ? row[1] : 0,
        'Wins': row.length > 2 ? row[2] : 0,
        '2nds': row.length > 3 ? row[3] : 0,
        '3rds': row.length > 4 ? row[4] : 0,
        'Spend': row.length > 5 ? row[5] : 0,
        'P&L': row.length > 6 ? row[6] : 0,
        'ROI %': row.length > 7 ? row[7] : 0,
      };
    }).toList();

    // Load upcoming & build driver map
    List<List<dynamic>> upcomingRaw;
    try {
      upcomingRaw = await _loadCsv(upcomingCsvAsset);
    } catch (_) {
      return driversRows
          .take(50)
          .map((m) => {...m, 'Upcoming': 0, 'Next': ''}).toList();
    }
    if (upcomingRaw.isEmpty) {
      return driversRows
          .take(50)
          .map((m) => {...m, 'Upcoming': 0, 'Next': ''}).toList();
    }

    final header = upcomingRaw.first;
    final body =
    upcomingRaw.length > 1 ? upcomingRaw.sublist(1) : <List<dynamic>>[];

    final idxDriver = _headerIndex(header, ['Driver']);
    final idxDate = _headerIndex(header, ['Date']);
    final idxTime = _headerIndex(header, ['Time']);
    final idxVenue = _headerIndex(header, ['Venue', 'Track', 'Course']);
    final idxRaceNo = _headerIndex(header, ['Race No', 'Race', 'R']);
    final idxHorseNo = _headerIndex(header, ['Horse No', 'No', 'Number']);
    final idxHorse = _headerIndex(header, ['Horse', 'Runner', 'Name']);

    final Map<String, List<Map<String, dynamic>>> byDriver = {};
    for (final r in body) {
      final driver =
      (idxDriver >= 0 && idxDriver < r.length) ? '${r[idxDriver]}' : '';
      if (driver.isEmpty) continue;
      byDriver.putIfAbsent(driver, () => []).add({
        'Date': (idxDate >= 0 && idxDate < r.length) ? '${r[idxDate]}' : '',
        'Time': (idxTime >= 0 && idxTime < r.length) ? '${r[idxTime]}' : '',
        'Venue': (idxVenue >= 0 && idxVenue < r.length) ? '${r[idxVenue]}' : '',
        'RaceNo':
        (idxRaceNo >= 0 && idxRaceNo < r.length) ? '${r[idxRaceNo]}' : '',
        'HorseNo':
        (idxHorseNo >= 0 && idxHorseNo < r.length) ? '${r[idxHorseNo]}' : '',
        'Horse': (idxHorse >= 0 && idxHorse < r.length) ? '${r[idxHorse]}' : '',
      });
    }

    // Enrich with Upcoming + Next
    final enriched = <Map<String, dynamic>>[];
    for (final row in driversRows) {
      final name = '${row['Driver']}'.trim();
      final list = byDriver[name] ?? [];
      final upcomingCount = list.length;

      String nextStr = '';
      if (list.isNotEmpty) {
        // earliest by date/time
        list.sort((a, b) {
          final adt = _parseDateTime(a['Date'], a['Time']);
          final bdt = _parseDateTime(b['Date'], b['Time']);
          if (adt == null && bdt == null) return 0;
          if (adt == null) return 1;
          if (bdt == null) return -1;
          return adt.compareTo(bdt);
        });

        final n = list.first;
        final date = (n['Date'] ?? '').toString();
        final time = (n['Time'] ?? '').toString();
        final venue = (n['Venue'] ?? '').toString();
        final raceNo = (n['RaceNo'] ?? '').toString();
        final horseNo = (n['HorseNo'] ?? '').toString();
        final horse = (n['Horse'] ?? '').toString();

        // Format date/time (no am/pm)
        String formattedDate = date;
        String formattedTime = time;
        final parsedDT = _parseDateTime(date, time);
        if (parsedDT != null) {
          formattedDate = '${parsedDT.day}/${parsedDT.month}';
          formattedTime = '${parsedDT.hour}:${parsedDT.minute.toString().padLeft(2, '0')}';
        }

        // Venue short
        final shortVenue = venue.length > 4 ? venue.substring(0, 4) : venue;

        // Clean horse no (drop .0)
        String cleanHorseNo = horseNo;
        if (horseNo.isNotEmpty) {
          final num? parsed = num.tryParse(horseNo);
          if (parsed != null) {
            cleanHorseNo =
            (parsed % 1 == 0) ? parsed.toInt().toString() : parsed.toString();
          }
        }

        // Title-case horse
        final titleHorse = horse
            .split(' ')
            .map((w) => w.isEmpty ? '' : w[0].toUpperCase() + w.substring(1).toLowerCase())
            .join(' ');

        // Build formatted string and split so we can style the horse bold
        final beforeHorse = [
          if (formattedDate.isNotEmpty) '$formattedDate:',
          if (formattedTime.isNotEmpty) formattedTime + ',',
          if (shortVenue.isNotEmpty) shortVenue,
          if (raceNo.isNotEmpty || cleanHorseNo.isNotEmpty)
            'R${raceNo.isNotEmpty ? raceNo : ''}-${cleanHorseNo.isNotEmpty ? cleanHorseNo : ''}',
        ].join(' ').replaceAll(' ,', ',');

        nextStr = '$beforeHorse|||$titleHorse';
      }

      enriched.add({
        ...row,
        'Upcoming': upcomingCount,
        'Next': nextStr,
      });
    }

    return enriched.take(50).toList();
  }

  double _parseRoi(dynamic v) {
    if (v == null) return 0;
    if (v is num) return v.toDouble();
    if (v is String) {
      final s = v.replaceAll('%', '').trim();
      return double.tryParse(s) ?? 0;
    }
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final pillBg = Theme.of(context).colorScheme.primary.withOpacity(0.12);
    final pillFg = Theme.of(context).colorScheme.primary;

    return Scaffold(
      appBar: AppBar(title: Text(widget.title)),
      body: FutureBuilder<List<Map<String, dynamic>>>(
        future: _tableFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (!snapshot.hasData || snapshot.data!.isEmpty) {
            return const Center(child: Text('No data available'));
          }

          final rows = snapshot.data!;

          return Center(
            child: ConstrainedBox(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.55, // ~half width
              ),
              child: Column(
                children: [
                  // Header
                  Container(
                    padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 16.0),
                    color: Colors.grey[300],
                    child: const Row(
                      children: [
                        Expanded(flex: 3, child: Text('Driver', style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('ROI',     textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('Starts',  textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('Wins',    textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('2nds',    textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('3rds',    textAlign: TextAlign.right, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(child: Text('Upcoming', textAlign: TextAlign.center, style: TextStyle(fontWeight: FontWeight.bold))),
                        Expanded(flex: 4, child: Text('Next', textAlign: TextAlign.left, style: TextStyle(fontWeight: FontWeight.bold))),
                      ],
                    ),
                  ),

                  // Rows
                  Expanded(
                    child: ListView.builder(
                      itemCount: rows.length,
                      itemBuilder: (context, index) {
                        final d = rows[index];
                        final roi = _parseRoi(d['ROI %']);
                        final isEven = index % 2 == 0;
                        final baseColor = isEven ? Colors.grey[100] : Colors.white;
                        final highlight = roi > 0.1; // > 0.1%

                        return Container(
                          color: baseColor,
                          padding: const EdgeInsets.symmetric(vertical: 8.0, horizontal: 16.0),
                          child: Row(
                            children: [
                              // Driver
                              Expanded(flex: 3, child: Text('${d['Driver'] ?? 'Unknown'}')),

                              // ROI (green pill highlight when positive)
                              Expanded(
                                child: Container(
                                  padding: const EdgeInsets.symmetric(vertical: 2.0, horizontal: 4.0),
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

                              // Starts, Wins, 2nds, 3rds
                              Expanded(child: Text('${d['Starts']}', textAlign: TextAlign.right)),
                              Expanded(child: Text('${d['Wins']}',   textAlign: TextAlign.right)),
                              Expanded(child: Text('${d['2nds']}',   textAlign: TextAlign.right)),
                              Expanded(child: Text('${d['3rds']}',   textAlign: TextAlign.right)),

                              // Upcoming (pill style)
                              Expanded(
                                child: Center(
                                  child: Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                    decoration: BoxDecoration(
                                      color: pillBg,
                                      borderRadius: BorderRadius.circular(999),
                                      border: Border.all(color: pillFg.withOpacity(0.35), width: 1),
                                    ),
                                    child: Text(
                                      '${d['Upcoming']}',
                                      style: TextStyle(
                                        fontWeight: FontWeight.w600,
                                        color: pillFg,
                                      ),
                                    ),
                                  ),
                                ),
                              ),

                              // Next (wider, horse semibold)
                              Expanded(
                                flex: 4,
                                child: Builder(
                                  builder: (_) {
                                    final parts = (d['Next'] ?? '').split('|||');
                                    final beforeHorse = parts.isNotEmpty ? parts[0] : '';
                                    final horseName = parts.length > 1 ? parts[1] : '';

                                    return RichText(
                                      maxLines: 1,
                                      overflow: TextOverflow.ellipsis,
                                      text: TextSpan(
                                        style: DefaultTextStyle.of(context).style.copyWith(fontSize: 14),
                                        children: [
                                          TextSpan(text: beforeHorse.isNotEmpty ? '$beforeHorse ' : ''),
                                          if (horseName.isNotEmpty)
                                            TextSpan(
                                              text: horseName,
                                              style: const TextStyle(fontWeight: FontWeight.w600),
                                            ),
                                        ],
                                      ),
                                    );
                                  },
                                ),
                              ),
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
