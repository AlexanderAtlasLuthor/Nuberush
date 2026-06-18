// NubeRush Driver — dedicated 21+ age verification screen (Dr.1.5.G).
//
// Promotes the existing verify-age compliance dialog into a dedicated surface.
// It reuses the EXISTING VerifyAgeRequest payload and the existing controller
// method (which attaches the Idempotency-Key and re-reads state on success).
// It scans no ID, uploads no photo, stores no DOB/ID data, and claims no legal
// authority beyond the backend response. The "can't verify" path routes to the
// failure surface (the existing fail action) — never to return-to-store.

import 'package:flutter/material.dart';

import '../../../core/theme/nuberush_colors.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';
import '../domain/compliance_requests.dart';
import 'age_verification_failed_screen.dart';
import 'assignment_detail_controller.dart';
import 'driver_compliance_action.dart';

class AgeVerificationScreen extends StatefulWidget {
  const AgeVerificationScreen({super.key, required this.controller});

  final AssignmentDetailController controller;

  @override
  State<AgeVerificationScreen> createState() => _AgeVerificationScreenState();
}

class _AgeVerificationScreenState extends State<AgeVerificationScreen> {
  bool _confirmed = false;
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

  Future<void> _submit() async {
    final note = _note.text.trim();
    await widget.controller.verifyAge(VerifyAgeRequest(
      outcome: VerifyAgeOutcome.pass,
      ageOver21Confirmed: true,
      note: note.isEmpty ? null : note,
    ));
    if (!mounted) return;
    final st = widget.controller.state;
    // Success (reloaded, no inline error) or auth-expired -> leave the screen.
    if (!st.hasActionError) Navigator.of(context).maybePop();
  }

  void _openFailedPath() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) =>
            AgeVerificationFailedScreen(controller: widget.controller),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      appBar: AppBar(title: const Text('Verify age (21+)')),
      body: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final state = widget.controller.state;
          final running =
              state.runningComplianceAction == DriverComplianceAction.verifyAge;
          final inFlight = state.isActionInFlight;
          return ListView(
            key: const Key('age-verification-screen'),
            padding: const EdgeInsets.all(NubeRushSpacing.lg),
            children: [
              NubeRushCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Recipient eligibility',
                        style: Theme.of(context).textTheme.titleMedium),
                    const SizedBox(height: NubeRushSpacing.sm),
                    const Text(
                      'Confirm the recipient meets NubeRush 21+ policy before '
                      'handing over a restricted order. The backend records and '
                      'verifies the outcome.',
                      style: TextStyle(color: NubeRushColors.textPrimary),
                    ),
                    const SizedBox(height: NubeRushSpacing.sm),
                    CheckboxListTile(
                      key: const Key('age-21-confirm'),
                      contentPadding: EdgeInsets.zero,
                      controlAffinity: ListTileControlAffinity.leading,
                      activeColor: NubeRushColors.primary,
                      title: const Text(
                        'I confirm the recipient is 21 or older per NubeRush '
                        'policy.',
                        style: TextStyle(color: NubeRushColors.textPrimary),
                      ),
                      value: _confirmed,
                      onChanged: inFlight
                          ? null
                          : (v) => setState(() => _confirmed = v ?? false),
                    ),
                    TextField(
                      key: const Key('age-note'),
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
                  key: const Key('age-action-error'),
                  message: state.actionErrorMessage!,
                ),
              ],
              const SizedBox(height: NubeRushSpacing.lg),
              NubeRushPrimaryButton(
                key: const Key('age-verify-submit'),
                label: 'Confirm 21+ verified',
                isLoading: running,
                onPressed: (_confirmed && !inFlight) ? _submit : null,
              ),
              const SizedBox(height: NubeRushSpacing.sm),
              NubeRushSecondaryButton(
                key: const Key('age-cant-verify'),
                label: "Can't verify age",
                onPressed: inFlight ? null : _openFailedPath,
              ),
            ],
          );
        },
      ),
    );
  }
}
