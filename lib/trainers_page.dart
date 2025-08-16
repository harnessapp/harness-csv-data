import 'package:flutter/material.dart';

class TrainersPage extends StatefulWidget {
  const TrainersPage({super.key});

  @override
  _TrainersPageState createState() => _TrainersPageState();
}

class _TrainersPageState extends State<TrainersPage> {
  // Initialize filters
  String selectedFilter = 'Hot'; // Default to Hot
  String selectedPeriod = '30d'; // Default to 30 days
  String selectedType = '100s';  // Default to 100s

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trainers'),
        actions: [
          IconButton(
            icon: const Icon(Icons.search),
            onPressed: () {
              // Trigger any filter action
            },
          ),
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Hot / Cold Filter Section
            Row(
              mainAxisAlignment: MainAxisAlignment.start,
              children: [
                _buildFilterButton('Hot'),
                const SizedBox(width: 10),
                _buildFilterButton('Cold'),
              ],
            ),
            const SizedBox(height: 20),

            // 30d / 100s Filter Section
            Row(
              mainAxisAlignment: MainAxisAlignment.start,
              children: [
                _buildPeriodButton('30d'),
                const SizedBox(width: 10),
                _buildPeriodButton('100s'),
              ],
            ),
            const SizedBox(height: 20),

            // Display the corresponding data for the selected filters
            Expanded(
              child: _buildTrainersList(),
            ),
          ],
        ),
      ),
    );
  }

  // Filter Button for Hot / Cold
  Widget _buildFilterButton(String filter) {
    return ElevatedButton(
      style: ElevatedButton.styleFrom(
        backgroundColor: selectedFilter == filter ? Colors.blue : Colors.grey, // Corrected style parameter
      ),
      onPressed: () {
        setState(() {
          selectedFilter = filter;
        });
      },
      child: Text(filter),
    );
  }

  // Period Button for 30d / 100s
  Widget _buildPeriodButton(String period) {
    return ElevatedButton(
      style: ElevatedButton.styleFrom(
        backgroundColor: selectedPeriod == period ? Colors.blue : Colors.grey, // Corrected style parameter
      ),
      onPressed: () {
        setState(() {
          selectedPeriod = period;
        });
      },
      child: Text(period),
    );
  }

  // Placeholder method to display a list of trainers
  Widget _buildTrainersList() {
    // Here you will implement the logic to display data based on selected filters.
    // For now, we will just display a placeholder list.

    return ListView.builder(
      itemCount: 10, // Just a placeholder count
      itemBuilder: (context, index) {
        return ListTile(
          title: Text('Trainer ${index + 1}'),
          subtitle: Text('Stats for $selectedFilter, $selectedPeriod, $selectedType'),
        );
      },
    );
  }
}
