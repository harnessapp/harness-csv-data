import 'package:flutter/material.dart';
import 'drivers_table_page.dart';

class DriversMenuPage extends StatelessWidget {
  const DriversMenuPage({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Drivers')),
      body: ListView(
        children: [
          _MenuItem(
            title: 'Hot Drivers 30 days',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const DriversTablePage(
                  title: 'Hot Drivers 30 Days',
                  csvAssetPath: 'assets/Hot Drivers 30.csv',
                ),
              ),
            ),
          ),
          _MenuItem(
            title: 'Hot Drivers last 100',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const DriversTablePage(
                  title: 'Hot Drivers – Last 100',
                  csvAssetPath: 'assets/Hot Drivers.csv',
                ),
              ),
            ),
          ),
          _MenuItem(
            title: 'Cold Drivers 30 days',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const DriversTablePage(
                  title: 'Cold Drivers 30 Days',
                  csvAssetPath: 'assets/Cold Drivers 30.csv',
                ),
              ),
            ),
          ),
          _MenuItem(
            title: 'Cold Drivers last 100',
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => const DriversTablePage(
                  title: 'Cold Drivers – Last 100',
                  csvAssetPath: 'assets/Cold Drivers.csv',
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
