// NubeRush Driver — Safety toolkit hub (Dr.1.5.J).
//
// STATIC / LOCAL-ONLY safety & support hub. It opens dedicated static guidance
// screens (emergency help, support center, report app issue, report delivery
// incident) via local navigation only. It requires no backend data, works with
// no active assignment, calls no DriverRepository / ApiClient, triggers no
// emergency calling, integrates no phone/SMS API, opens no maps, submits no
// support/incident data, and shows no tokens/secrets/config.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import 'emergency_help_screen.dart';
import 'report_bug_info_screen.dart';
import 'report_incident_info_screen.dart';
import 'support_center_screen.dart';

class SafetyToolkitScreen extends StatelessWidget {
  const SafetyToolkitScreen({super.key});

  static const List<String> _reminders = <String>[
    'Your personal safety always comes first.',
    'In an urgent emergency, contact local emergency services directly, '
        'following the laws where you are and NubeRush policy.',
    'These tools are guidance only — NubeRush does not dispatch emergency help '
        'from the app.',
  ];

  void _open(BuildContext context, Widget screen) {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => screen),
    );
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Safety & support')),
      body: ListView(
        key: const Key('safety-toolkit-screen'),
        padding: const EdgeInsets.all(NubeRushSpacing.lg),
        children: [
          NubeRushCard(
            key: const Key('safety-toolkit-reminders'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.health_and_safety_outlined,
                        color: NubeRushColors.primary),
                    const SizedBox(width: NubeRushSpacing.sm),
                    Expanded(
                      child: Text('Stay safe',
                          style: Theme.of(context).textTheme.titleMedium),
                    ),
                  ],
                ),
                const SizedBox(height: NubeRushSpacing.md),
                for (final line in _reminders)
                  Padding(
                    padding: const EdgeInsets.symmetric(
                        vertical: NubeRushSpacing.xs),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('• ',
                            style:
                                TextStyle(color: NubeRushColors.textSecondary)),
                        Expanded(
                          child: Text(line,
                              style: const TextStyle(
                                  color: NubeRushColors.textPrimary)),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          _Entry(
            key: const Key('safety-entry-emergency'),
            icon: Icons.emergency_outlined,
            iconColor: NubeRushColors.danger,
            title: 'Emergency help',
            subtitle: 'What to do if you’re in danger.',
            onTap: () => _open(context, const EmergencyHelpScreen()),
          ),
          const SizedBox(height: NubeRushSpacing.md),
          _Entry(
            key: const Key('safety-entry-support'),
            icon: Icons.support_agent_outlined,
            title: 'Support center',
            subtitle: 'Find the right help for an issue.',
            onTap: () => _open(context, const SupportCenterScreen()),
          ),
          const SizedBox(height: NubeRushSpacing.md),
          _Entry(
            key: const Key('safety-entry-bug'),
            icon: Icons.bug_report_outlined,
            title: 'Report an app issue',
            subtitle: 'How to safely note an app problem.',
            onTap: () => _open(context, const ReportBugInfoScreen()),
          ),
          const SizedBox(height: NubeRushSpacing.md),
          _Entry(
            key: const Key('safety-entry-incident'),
            icon: Icons.report_problem_outlined,
            title: 'Report a delivery incident',
            subtitle: 'Guidance for delivery problems.',
            onTap: () => _open(context, const ReportIncidentInfoScreen()),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushPrimaryButton(
            key: const Key('safety-toolkit-back'),
            label: 'Back',
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    );
  }
}

/// A single static safety/support entry card. Pure presentation: it only invokes
/// the local [onTap] it is given. It never calls an endpoint.
class _Entry extends StatelessWidget {
  const _Entry({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.iconColor = NubeRushColors.primary,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final Color iconColor;

  @override
  Widget build(BuildContext context) {
    return NubeRushCard(
      onTap: onTap,
      child: Row(
        children: [
          Icon(icon, color: iconColor),
          const SizedBox(width: NubeRushSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    color: NubeRushColors.textPrimary,
                    fontWeight: FontWeight.w700,
                    fontSize: 16,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  subtitle,
                  style: const TextStyle(
                      color: NubeRushColors.textSecondary, fontSize: 13),
                ),
              ],
            ),
          ),
          const Icon(Icons.chevron_right, color: NubeRushColors.textSecondary),
        ],
      ),
    );
  }
}
