// NubeRush Driver — operational action definitions (Dr.1.3.G).
//
// A thin UI/controller layer over the seven operational assignment actions.
// Each action maps to a repository method (the only place an endpoint is
// called). It carries a label and optional confirmation copy.
//
// IMPORTANT — backend is the authority. `operationalActionsFor(...)` is a
// DISPLAY-ONLY hint that decides which buttons to OFFER from the
// backend-reported status/state. It computes no result state, enforces no
// correctness, and defaults to offering nothing for unknown states. Any action
// the backend rejects surfaces as a normal error. No compliance actions live
// here (verify-age / proof / complete / fail / return-to-store are out of G).

import '../data/driver_repository.dart';

enum DriverOperationalAction {
  accept,
  decline,
  start,
  arriveStore,
  pickup,
  departToCustomer,
  arriveCustomer,
}

extension DriverOperationalActionX on DriverOperationalAction {
  /// Stable id (used as a widget key / loading discriminator).
  String get id => switch (this) {
        DriverOperationalAction.accept => 'accept',
        DriverOperationalAction.decline => 'decline',
        DriverOperationalAction.start => 'start',
        DriverOperationalAction.arriveStore => 'arrive-store',
        DriverOperationalAction.pickup => 'pickup',
        DriverOperationalAction.departToCustomer => 'depart-to-customer',
        DriverOperationalAction.arriveCustomer => 'arrive-customer',
      };

  String get label => switch (this) {
        DriverOperationalAction.accept => 'Accept',
        DriverOperationalAction.decline => 'Decline',
        DriverOperationalAction.start => 'Start delivery',
        DriverOperationalAction.arriveStore => 'Arrive at store',
        DriverOperationalAction.pickup => 'Pick up order',
        DriverOperationalAction.departToCustomer => 'Depart to customer',
        DriverOperationalAction.arriveCustomer => 'Arrive at customer',
      };

  /// Actions that warrant a confirm dialog before submitting.
  bool get requiresConfirmation => this == DriverOperationalAction.decline;

  /// Confirmation copy, when [requiresConfirmation] is true.
  String? get confirmCopy => this == DriverOperationalAction.decline
      ? 'Decline this assignment? This cannot be undone.'
      : null;

  /// Invoke the matching repository method (the single endpoint boundary).
  Future<void> invoke(DriverReadRepository repo, String assignmentId) =>
      switch (this) {
        DriverOperationalAction.accept => repo.acceptAssignment(assignmentId),
        DriverOperationalAction.decline => repo.declineAssignment(assignmentId),
        DriverOperationalAction.start => repo.startAssignment(assignmentId),
        DriverOperationalAction.arriveStore => repo.arriveStore(assignmentId),
        DriverOperationalAction.pickup => repo.pickupAssignment(assignmentId),
        DriverOperationalAction.departToCustomer =>
          repo.departToCustomer(assignmentId),
        DriverOperationalAction.arriveCustomer =>
          repo.arriveCustomer(assignmentId),
      };
}

/// Display-only mapping: which operational actions to OFFER for the current
/// backend-reported assignment status + delivery state. Conservative — returns
/// an empty list for unknown/compliance/terminal states (G stops at
/// arrive-customer). The backend remains the final authority.
List<DriverOperationalAction> operationalActionsFor({
  required String assignmentStatus,
  String? deliveryState,
}) {
  switch (assignmentStatus) {
    case 'offered':
      return const [
        DriverOperationalAction.accept,
        DriverOperationalAction.decline,
      ];
    case 'accepted':
      return const [DriverOperationalAction.start];
    case 'started':
      switch (deliveryState) {
        case 'en_route_to_store':
          return const [DriverOperationalAction.arriveStore];
        case 'arrived_at_store':
          return const [DriverOperationalAction.pickup];
        case 'picked_up':
          return const [DriverOperationalAction.departToCustomer];
        case 'en_route_to_customer':
          return const [DriverOperationalAction.arriveCustomer];
        default:
          // arrived_at_customer and beyond are compliance (out of G), and
          // unknown states offer nothing.
          return const [];
      }
    default:
      return const [];
  }
}
