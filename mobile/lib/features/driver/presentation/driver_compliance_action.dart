// NubeRush Driver — compliance action definitions (Dr.1.3.H).
//
// Separate from the Dr.1.3.G operational actions. Covers the five driver
// compliance endpoints (verify-age / proof / complete / fail / return-to-store).
// `confirm-driver-return` is store-side and intentionally absent.
//
// `complianceActionsFor(...)` is a DISPLAY-ONLY hint deciding which compliance
// actions to OFFER from the backend-reported status/state. It computes no
// outcome, enforces no correctness, and defaults to offering nothing for
// unknown states. The backend is the compliance authority; a rejected action
// surfaces as a normal error.

enum DriverComplianceAction {
  verifyAge,
  submitProof,
  completeDelivery,
  reportFailedDelivery,
  returnToStore,
}

extension DriverComplianceActionX on DriverComplianceAction {
  /// Stable id (used as a widget key). Distinct from operational action ids.
  String get id => switch (this) {
        DriverComplianceAction.verifyAge => 'verify-age',
        DriverComplianceAction.submitProof => 'proof',
        DriverComplianceAction.completeDelivery => 'complete',
        DriverComplianceAction.reportFailedDelivery => 'fail',
        DriverComplianceAction.returnToStore => 'return-to-store',
      };

  String get label => switch (this) {
        DriverComplianceAction.verifyAge => 'Verify age',
        DriverComplianceAction.submitProof => 'Submit proof',
        DriverComplianceAction.completeDelivery => 'Complete delivery',
        DriverComplianceAction.reportFailedDelivery => 'Report failed delivery',
        DriverComplianceAction.returnToStore => 'Return to store',
      };
}

/// Display-only mapping: which compliance actions to OFFER for the current
/// backend status + delivery state. Conservative — empty for unknown/terminal
/// states. Backend remains the authority.
List<DriverComplianceAction> complianceActionsFor({
  required String assignmentStatus,
  String? deliveryState,
}) {
  // Compliance happens while the assignment is `started`.
  if (assignmentStatus != 'started') return const [];

  switch (deliveryState) {
    case 'arrived_at_customer':
      return const [
        DriverComplianceAction.verifyAge,
        DriverComplianceAction.reportFailedDelivery,
      ];
    case 'id_verified':
      return const [
        DriverComplianceAction.submitProof,
        DriverComplianceAction.completeDelivery,
        DriverComplianceAction.reportFailedDelivery,
      ];
    case 'delivery_failed':
    case 'returning_to_store':
      return const [DriverComplianceAction.returnToStore];
    default:
      return const [];
  }
}
