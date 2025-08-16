import 'package:flutter/material.dart';
import 'trainers_table_page.dart';

class TrainersMenuPage extends StatelessWidget {
  const TrainersMenuPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Trainers')),
      body: ListView(
        children: [
          _MenuItem(
            title: 'Hot Trainers 30 days',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const TrainersTablePage(
                  title: 'Hot Trainers 30 Days',
                  csvAssetPath: 'assets/Hot Trainers 30.csv',
                ),
              ),
            ),
          ),
          _MenuItem(
            title: 'Hot Trainers last 100',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const TrainersTablePage(
                  title: 'Hot Trainers – Last 100',
                  csvAssetPath: 'assets/Hot Trainers.csv',
                ),
              ),
            ),
          ),
          _MenuItem(
            title: 'Cold Trainers 30 days',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const TrainersTablePage(
                  title: 'Cold Trainers 30 Days',
                  csvAssetPath: 'assets/Cold Trainers 30.csv',
                ),
              ),
            ),
          ),
          _MenuItem(
            title: 'Cold Trainers last 100',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const TrainersTablePage(
                  title: 'Cold Trainers – Last 100',
                  csvAssetPath: 'assets/Cold Trainers.csv',
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MenuItem extends StatelessWidget {
  final String title;
  final VoidCallback onTap;
  const _MenuItem({required this.title, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      title: Text(title),
      trailing: const Icon(Icons.chevron_right),
      onTap: onTap,
    );
  }
}
