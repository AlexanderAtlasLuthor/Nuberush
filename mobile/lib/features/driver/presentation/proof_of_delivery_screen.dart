// NubeRush Driver — dedicated proof-of-delivery screen (Dr.1.5.G).
//
// Promotes the existing proof compliance dialog into a dedicated surface. It
// reuses the EXISTING ProofRequest payload (the manual-checklist MVP: three
// required confirmations + optional note) and the existing controller method.
// No photo, camera, image_picker, signature, customer PIN, or invented proof
// types. It claims no proof beyond what the backend records.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/compliance_requests.dart';
import 'assignment_detail_controller.dart';
import 'driver_compliance_action.dart';

class ProofOfDeliveryScreen extends StatefulWidget {
  const ProofOfDeliveryScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<ProofOfDeliveryScreen> createState() => _ProofOfDeliveryScreenState();
}

class _ProofOfDeliveryScreenState extends State<ProofOfDeliveryScreen> {
  bool _recipient = false;
  bool _handoff = false;
  bool _unattended = false;
  final _note = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      widget.controller.clearActionError();
    });
  }

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  bool get _valid => _recipient && _handoff && _unattended;

  Future<void> _submit() async {
    final note = _note.text.trim();
    await widget.controller.submitProof(ProofRequest(
      recipientPresentConfirmed: _recipient,
      handoffConfirmed: _handoff,
      restrictedNotLeftUnattended: _unattended,
      note: note.isEmpty ? null : note,
    ));
    if (!mounted) return;
    if (!widget.controller.state.hasActionError) {
      Navigator.of(context).maybePop();
    }
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Proof of delivery')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final state = widget.controller.state;
          final running = state.runningComplianceAction ==
              DriverComplianceAction.submitProof;
          final inFlight = state.isActionInFlight;
          return ListView(
            key: const Key('proof-of-delivery-screen'),
            padding: const EdgeInsets.all(NubeRushSpacing.lg),
            children: [
              NubeRushCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Confirm handoff',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: NubeRushSpacing.sm),
                    const Text(
                      'NubeRush records a manual handoff checklist as proof. '
                      'All three confirmations are required.',
                      style: TextStyle(color: NubeRushColors.textSecondary,
                          fontSize: 13),
                    ),
                    CheckboxListTile(
                      key: const Key('dropoff-proof-recipient'),
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                      activeColor: NubeRushColors.primary,
                      title: const Text('Recipient present',
                          style: TextStyle(color: NubeRushColors.textPrimary)),
                      value: _recipient,
                      onChanged: inFlight
                          ? null
                          : (v) => setState(() => _recipient = v ?? false),
                    ),
                    CheckboxListTile(
                      key: const Key('dropoff-proof-handoff'),
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                      activeColor: NubeRushColors.primary,
                      title: const Text('Handoff confirmed',
                          style: TextStyle(color: NubeRushColors.textPrimary)),
                      value: _handoff,
                      onChanged: inFlight
                          ? null
                          : (v) => setState(() => _handoff = v ?? false),
                    ),
                    CheckboxListTile(
                      key: const Key('dropoff-proof-unattended'),
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                      activeColor: NubeRushColors.primary,
                      title: const Text('Not left unattended',
                          style: TextStyle(color: NubeRushColors.textPrimary)),
                      value: _unattended,
                      onChanged: inFlight
                          ? null
                          : (v) => setState(() => _unattended = v ?? false),
                    ),
                    TextField(
                      key: const Key('dropoff-proof-note'),
                      controller: _note,
                      enabled: !inFlight,
                      maxLength: 500,
                      decoration: const InputDecoration(
                          labelText: 'Note (optional)'),
                    ),
                  ],
                ),
              ),
              if (state.actionErrorMessage != null) ...[
                const SizedBox(height: NubeRushSpacing.lg),
                NubeRushInlineError(
                  key: const Key('dropoff-proof-action-error'),
                  message: state.actionErrorMessage!,
                ),
              ],
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('dropoff-proof-submit'),
                label: 'Submit proof',
                isLoading: running,
                onPressed: (_valid && !inFlight) ? _submit : null,
              ),
            ],
          );
        },
      ),
    );
  }
}
