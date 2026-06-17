// NubeRush Driver — compliance action dialogs (Dr.1.3.H).
//
// Manual-checklist forms only. NO OCR, ID/photo/signature/file upload, no DOB,
// no local age computation, no sensitive ID data. Each returns the exact
// backend request body (or null/false when cancelled). Inputs are never logged.

import 'package:flutter/material.dart';

import '../domain/compliance_requests.dart';

/// verify-age: outcome + (failure reason when fail) + optional checklist + note.
Future<VerifyAgeRequest?> showVerifyAgeDialog(BuildContext context) {
  return showDialog<VerifyAgeRequest>(
    context: context,
    builder: (_) => const _VerifyAgeDialog(),
  );
}

/// proof: three required handoff confirmations (all true) + optional note.
Future<ProofRequest?> showProofDialog(BuildContext context) {
  return showDialog<ProofRequest>(
    context: context,
    builder: (_) => const _ProofDialog(),
  );
}

/// complete: confirm-only (bodyless backend call).
Future<bool> showCompleteConfirm(BuildContext context) async {
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => AlertDialog(
      title: const Text('Complete delivery'),
      content: const Text(
        'Submit this delivery as complete? The backend verifies the gates.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(ctx).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('complete-confirm'),
          onPressed: () => Navigator.of(ctx).pop(true),
          child: const Text('Complete'),
        ),
      ],
    ),
  );
  return ok ?? false;
}

/// fail: structured reason + optional note.
Future<FailRequest?> showFailDialog(BuildContext context) {
  return showDialog<FailRequest>(
    context: context,
    builder: (_) => const _FailDialog(),
  );
}

/// return-to-store: confirm the given custody step (start/arrive) + note.
Future<ReturnToStoreRequest?> showReturnToStoreDialog(
  BuildContext context,
  ReturnAction action,
) {
  return showDialog<ReturnToStoreRequest>(
    context: context,
    builder: (_) => _ReturnToStoreDialog(action: action),
  );
}

// --------------------------------------------------------------------------

class _VerifyAgeDialog extends StatefulWidget {
  const _VerifyAgeDialog();
  @override
  State<_VerifyAgeDialog> createState() => _VerifyAgeDialogState();
}

class _VerifyAgeDialogState extends State<_VerifyAgeDialog> {
  VerifyAgeOutcome _outcome = VerifyAgeOutcome.pass;
  VerifyAgeFailureReason? _reason;
  bool _ageOver21 = false;
  final _note = TextEditingController();

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  bool get _valid =>
      _outcome != VerifyAgeOutcome.fail || _reason != null; // reason req on fail

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      key: const Key('verify-age-dialog'),
      title: const Text('Verify age (21+)'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            DropdownButton<VerifyAgeOutcome>(
              key: const Key('verify-age-outcome'),
              isExpanded: true,
              value: _outcome,
              items: [
                for (final o in VerifyAgeOutcome.values)
                  DropdownMenuItem(value: o, child: Text(o.label)),
              ],
              onChanged: (v) => setState(() {
                _outcome = v ?? _outcome;
                if (_outcome != VerifyAgeOutcome.fail) _reason = null;
              }),
            ),
            if (_outcome == VerifyAgeOutcome.fail)
              DropdownButton<VerifyAgeFailureReason>(
                key: const Key('verify-age-reason'),
                isExpanded: true,
                hint: const Text('Failure reason'),
                value: _reason,
                items: [
                  for (final r in VerifyAgeFailureReason.values)
                    DropdownMenuItem(value: r, child: Text(r.wire)),
                ],
                onChanged: (v) => setState(() => _reason = v),
              ),
            CheckboxListTile(
              key: const Key('verify-age-over21'),
              title: const Text('Confirmed 21 or older'),
              value: _ageOver21,
              onChanged: (v) => setState(() => _ageOver21 = v ?? false),
            ),
            TextField(
              key: const Key('verify-age-note'),
              controller: _note,
              maxLength: 500,
              decoration: const InputDecoration(labelText: 'Note (optional)'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('verify-age-submit'),
          onPressed: _valid
              ? () => Navigator.of(context).pop(
                    VerifyAgeRequest(
                      outcome: _outcome,
                      failureReasonCode:
                          _outcome == VerifyAgeOutcome.fail ? _reason : null,
                      ageOver21Confirmed: _ageOver21 ? true : null,
                      note: _note.text.trim().isEmpty ? null : _note.text.trim(),
                    ),
                  )
              : null,
          child: const Text('Submit'),
        ),
      ],
    );
  }
}

class _ProofDialog extends StatefulWidget {
  const _ProofDialog();
  @override
  State<_ProofDialog> createState() => _ProofDialogState();
}

class _ProofDialogState extends State<_ProofDialog> {
  bool _recipient = false;
  bool _handoff = false;
  bool _unattended = false;
  final _note = TextEditingController();

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  bool get _valid => _recipient && _handoff && _unattended;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      key: const Key('proof-dialog'),
      title: const Text('Proof of delivery'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CheckboxListTile(
              key: const Key('proof-recipient'),
              title: const Text('Recipient present'),
              value: _recipient,
              onChanged: (v) => setState(() => _recipient = v ?? false),
            ),
            CheckboxListTile(
              key: const Key('proof-handoff'),
              title: const Text('Handoff confirmed'),
              value: _handoff,
              onChanged: (v) => setState(() => _handoff = v ?? false),
            ),
            CheckboxListTile(
              key: const Key('proof-unattended'),
              title: const Text('Not left unattended'),
              value: _unattended,
              onChanged: (v) => setState(() => _unattended = v ?? false),
            ),
            TextField(
              key: const Key('proof-note'),
              controller: _note,
              maxLength: 500,
              decoration: const InputDecoration(labelText: 'Note (optional)'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('proof-submit'),
          onPressed: _valid
              ? () => Navigator.of(context).pop(
                    ProofRequest(
                      recipientPresentConfirmed: _recipient,
                      handoffConfirmed: _handoff,
                      restrictedNotLeftUnattended: _unattended,
                      note: _note.text.trim().isEmpty ? null : _note.text.trim(),
                    ),
                  )
              : null,
          child: const Text('Submit'),
        ),
      ],
    );
  }
}

class _FailDialog extends StatefulWidget {
  const _FailDialog();
  @override
  State<_FailDialog> createState() => _FailDialogState();
}

class _FailDialogState extends State<_FailDialog> {
  FailureReason _reason = FailureReason.customerUnavailable;
  final _note = TextEditingController();

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      key: const Key('fail-dialog'),
      title: const Text('Report failed delivery'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButton<FailureReason>(
              key: const Key('fail-reason'),
              isExpanded: true,
              value: _reason,
              items: [
                for (final r in FailureReason.values)
                  DropdownMenuItem(value: r, child: Text(r.label)),
              ],
              onChanged: (v) => setState(() => _reason = v ?? _reason),
            ),
            TextField(
              key: const Key('fail-note'),
              controller: _note,
              maxLength: 500,
              decoration: const InputDecoration(labelText: 'Note (optional)'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('fail-submit'),
          onPressed: () => Navigator.of(context).pop(
            FailRequest(
              reasonCode: _reason,
              note: _note.text.trim().isEmpty ? null : _note.text.trim(),
            ),
          ),
          child: const Text('Submit'),
        ),
      ],
    );
  }
}

class _ReturnToStoreDialog extends StatefulWidget {
  const _ReturnToStoreDialog({required this.action});
  final ReturnAction action;
  @override
  State<_ReturnToStoreDialog> createState() => _ReturnToStoreDialogState();
}

class _ReturnToStoreDialogState extends State<_ReturnToStoreDialog> {
  final _note = TextEditingController();

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isStart = widget.action == ReturnAction.start;
    return AlertDialog(
      key: const Key('return-to-store-dialog'),
      title: const Text('Return to store'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(isStart
                ? 'Start the return-to-store leg.'
                : 'Confirm arrival back at the store.'),
            TextField(
              key: const Key('return-note'),
              controller: _note,
              maxLength: 500,
              decoration: const InputDecoration(labelText: 'Note (optional)'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        FilledButton(
          key: const Key('return-confirm'),
          onPressed: () => Navigator.of(context).pop(
            ReturnToStoreRequest(
              action: widget.action,
              note: _note.text.trim().isEmpty ? null : _note.text.trim(),
            ),
          ),
          child: Text(isStart ? 'Start return' : 'Confirm arrival'),
        ),
      ],
    );
  }
}
