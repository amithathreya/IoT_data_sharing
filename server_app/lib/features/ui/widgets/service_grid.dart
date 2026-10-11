import 'package:flutter/material.dart';
import '../../supervisor/services/process_supervisor.dart';
import 'service_card.dart';

class ServiceGrid extends StatelessWidget {
  final ProcessSupervisor supervisor;

  const ServiceGrid({
    super.key,
    required this.supervisor,
  });

  @override
  Widget build(BuildContext context) {
    final states = supervisor.states.values.toList();

    return LayoutBuilder(
      builder: (context, constraints) {
        // Choose column count based on available desktop width
        int crossAxisCount = 3;
        if (constraints.maxWidth < 1100) {
          crossAxisCount = 2;
        }
        if (constraints.maxWidth < 700) {
          crossAxisCount = 1;
        }

        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: states.length,
            gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: crossAxisCount,
              mainAxisSpacing: 16,
              crossAxisSpacing: 16,
              childAspectRatio: 1.6,
            ),
            itemBuilder: (context, index) {
              return ServiceCard(
                state: states[index],
                supervisor: supervisor,
              );
            },
          ),
        );
      },
    );
  }
}
