import 'package:flutter/material.dart';

class RunnerChip extends StatefulWidget {
  final String runnerName;
  final double ldPercentage;
  final double blPercentage;
  final double dthPercentage;
  final int horseQty;
  final int bellPosLeadCount;
  final double bellPosLeadPct;
  final int bellPosBLCount;
  final double bellPosBLPct;
  final int bellPosDthCount;
  final double bellPosDthPct;

  const RunnerChip({
    required this.runnerName,
    required this.ldPercentage,
    required this.blPercentage,
    required this.dthPercentage,
    required this.horseQty,
    required this.bellPosLeadCount,
    required this.bellPosLeadPct,
    required this.bellPosBLCount,
    required this.bellPosBLPct,
    required this.bellPosDthCount,
    required this.bellPosDthPct,
  });

  @override
  _RunnerChipState createState() => _RunnerChipState();
}

class _RunnerChipState extends State<RunnerChip> {
  bool _isLdExpanded = false;
  bool _isBlExpanded = false;
  bool _isDthExpanded = false;
  bool _isHovered = false;

  // Gradually darken the color based on percentage with a steeper curve
  Color _getChipColor(double percentage, Color baseColor) {
    // This applies a steeper darkening effect as the percentage increases.
    double opacity = (percentage / 100.0).clamp(0.2, 1.0); // Restrict opacity between 0.2 to 1.0
    opacity = opacity * opacity * 9.5; // Exponentially increase the darkness for higher percentages

    // Return color with the computed opacity
    return baseColor.withOpacity(opacity);
  }


  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) {
        setState(() {
          _isHovered = true;
        });
      },
      onExit: (_) {
        setState(() {
          _isHovered = false;
        });
      },
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // Ld Chip with increased contrast
              _buildChip(
                label: 'Ld ${widget.ldPercentage.round()}%',
                onTap: () {
                  setState(() {
                    _isLdExpanded = !_isLdExpanded;
                  });
                },
                isExpanded: _isHovered || _isLdExpanded,
                color: _getChipColor(widget.ldPercentage, Colors.green),
                additionalInfo: _getExpandedInfo('Ld'),
              ),
              // BL Chip with increased contrast
              _buildChip(
                label: 'BL ${widget.blPercentage.round()}%',
                onTap: () {
                  setState(() {
                    _isBlExpanded = !_isBlExpanded;
                  });
                },
                isExpanded: _isHovered || _isBlExpanded,
                color: _getChipColor(widget.blPercentage, Colors.yellow.shade700),
                additionalInfo: _getExpandedInfo('BL'),
              ),
              // Dth Chip with increased contrast
              _buildChip(
                label: 'Dth ${widget.dthPercentage.round()}%',
                onTap: () {
                  setState(() {
                    _isDthExpanded = !_isDthExpanded;
                  });
                },
                isExpanded: _isHovered || _isDthExpanded,
                color: _getChipColor(widget.dthPercentage, Colors.red),
                additionalInfo: _getExpandedInfo('Dth'),
              ),
            ],
          ),
        ],
      ),
    );
  }

  // Method to build each chip (Ld, BL, Dth)
  Widget _buildChip({
    required String label,
    required VoidCallback onTap,
    required bool isExpanded,
    required Color color,
    required Widget additionalInfo,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Chip(
            label: Text(label),
            backgroundColor: _isHovered
                ? color.withOpacity(0.6) // Hover effect color change
                : color,
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          ),
          if (isExpanded) additionalInfo,
        ],
      ),
    );
  }

  // Method to return the expanded info for each chip
  Widget _getExpandedInfo(String type) {
    String label = '';
    switch (type) {
      case 'Ld':
        label = 'Ld: ${widget.ldPercentage.round()}%\n'
            'Bell Pos Lead: ${widget.bellPosLeadCount} (${widget.bellPosLeadPct.round()}%)';
        break;
      case 'BL':
        label = 'BL: ${widget.blPercentage.round()}%\n'
            'Bell Pos BL: ${widget.bellPosBLCount} (${widget.bellPosBLPct.round()}%)';
        break;
      case 'Dth':
        label = 'Dth: ${widget.dthPercentage.round()}%\n'
            'Bell Pos Dth: ${widget.bellPosDthCount} (${widget.bellPosDthPct.round()}%)';
        break;
    }
    return Padding(
      padding: const EdgeInsets.only(top: 8.0),
      child: Text(label),
    );
  }
}
