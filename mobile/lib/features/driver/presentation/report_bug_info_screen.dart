// NubeRush Driver — Report app issue / bug guidance (Dr.1.5.J).
//
// STATIC / LOCAL-ONLY. Tells a driver what safe information to note for an app
// issue and what NEVER to share. It collects no form for backend submission,
// attaches/displays no logs, shows no auth/session token, shows no raw config
// values, and sends nothing. In-app bug submission is future work.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

class ReportBugInfoScreen extends StatelessWidget {
  const ReportBugInfoScreen({super.key});

  static const List<String> _safeToNote = <String>[
    'What happened, in your own words.',
    'The screen name you were on.',
    'The approximate time it happened.',
    'The assignment id, only if it is already visible on screen.',
    'The on-screen error message, if it looks safe to repeat.',
  ];

  static const List<String> _neverShare = <String>[
    'Passwords or login codes.',
    'Auth or session tokens.',
    'Payment or banking information.',
    'ID photos or document images.',
    'Customer personal information (name, phone, full address).',
  ];

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Report an app issue')),
      body: ListView(
        key: const Key('report-bug-info-screen'),
        padding: const EdgeInsets.all(NubeRushSpacing.lg),
        children: [
          NubeRushCard(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Helpful details to note',
                    style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: NubeRushSpacing.sm),
                const Text(
                  'In-app bug submission is future work. For now, note the '
                  'details below so you can share them through the approved '
                  'NubeRush channel.',
                  style: TextStyle(
                      color: NubeRushColors.textSecondary, fontSize: 13),
                ),
                const SizedBox(height: NubeRushSpacing.md),
                for (final line in _safeToNote)
                  _bullet(line, color: NubeRushColors.textPrimary),
              ],
            ),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushCard(
            key: const Key('report-bug-never-share'),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.shield_outlined,
                        color: NubeRushColors.danger),
                    const SizedBox(width: NubeRushSpacing.sm),
                    Expanded(
                      child: Text('Never share these',
                          style: Theme.of(context).textTheme.titleMedium),
                    ),
                  ],
                ),
                const SizedBox(height: NubeRushSpacing.sm),
                for (final line in _neverShare)
                  _bullet(line, color: NubeRushColors.textPrimary),
              ],
            ),
          ),
          const SizedBox(height: NubeRushSpacing.lg),
          NubeRushPrimaryButton(
            key: const Key('report-bug-back'),
            label: 'Back to safety tools',
            onPressed: () => Navigator.of(context).maybePop(),
          ),
        ],
      ),
    );
  }

  static Widget _bullet(String text, {required Color color}) => Padding(
        padding: const EdgeInsets.symmetric(vertical: NubeRushSpacing.xs),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('• ',
                style: TextStyle(color: NubeRushColors.textSecondary)),
            Expanded(child: Text(text, style: TextStyle(color: color))),
          ],
        ),
      );
}
