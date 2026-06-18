// NubeRush Driver — pickup checklist (Dr.1.5.F).
//
// A LOCAL, PRESENTATION-ONLY checklist that helps the driver self-confirm the
// store pickup is in order before marking pickup. It mutates no backend state,
// claims no inventory verification, asserts no store-staff confirmation as
// backend fact, and creates no legal/compliance authority. The parent decides
// whether to enable the confirm action based on [onReadyChanged].

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

/// The fixed, generic, safe checklist items. Driver self-confirmations only —
/// no backend claim, no PII, no instructions sourced from a (nonexistent)
/// backend field.
const List<String> kPickupChecklistItems = <String>[
  "I'm at the correct NubeRush store.",
  'Store staff handed over the sealed, ready order.',
  'The order is sealed and secure.',
  "I'll follow NubeRush restricted-product handling rules.",
];

class PickupChecklist extends StatefulWidget {
  const PickupChecklist({
    super.key,
    required this.onReadyChanged,
    this.enabled = true,
  });

  /// Fired whenever the "all items checked" state changes.
  final ValueChanged<bool> onReadyChanged;

  /// When false the checkboxes are disabled (e.g. an action is in flight).
  final bool enabled;

  @override
  State<PickupChecklist> createState() => _PickupChecklistState();
}

class _PickupChecklistState extends State<PickupChecklist> {
  late final List<bool> _checked =
      List<bool>.filled(kPickupChecklistItems.length, false);

  bool get _allChecked => _checked.every((c) => c);

  void _set(int i, bool value) {
    setState(() => _checked[i] = value);
    widget.onReadyChanged(_allChecked);
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushCard(
      key: const Key('pickup-checklist'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Pickup checklist',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: NubeRushSpacing.xs),
          const Text(
            'For your guidance only — NubeRush and the store confirm the '
            'order on their side.',
            style: TextStyle(color: NubeRushColors.textSecondary, fontSize: 13),
          ),
          const SizedBox(height: NubeRushSpacing.sm),
          for (var i = 0; i < kPickupChecklistItems.length; i++)
            CheckboxListTile(
              key: Key('pickup-check-$i'),
              contentPadding: EdgeInsets.zero,
              controlAffinity: ListTileControlAffinity.leading,
              activeColor: NubeRushColors.primary,
              title: Text(
                kPickupChecklistItems[i],
                style: const TextStyle(color: NubeRushColors.textPrimary),
              ),
              value: _checked[i],
              onChanged: widget.enabled ? (v) => _set(i, v ?? false) : null,
            ),
        ],
      ),
    );
  }
}
