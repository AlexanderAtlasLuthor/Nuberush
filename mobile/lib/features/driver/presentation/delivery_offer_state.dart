// NubeRush Driver — Delivery Offer Surface view state (Dr.1.5.D).
//
// A delivery offer is simply an existing assignment whose backend-reported
// `status == offered` (GET /driver/assignments). There is NO separate offer
// model, no realtime/push/websocket, no expiry/countdown. The screen DISPLAYS
// offered assignments and lets the driver accept/decline via the existing
// endpoints — the backend remains the authority.

import '../domain/driver_assignment.dart';

/// Backend assignment status that the driver app treats as a delivery offer.
const String kOfferedStatus = 'offered';

/// Which offer action is currently running (for per-card feedback).
enum OfferAction { accept, decline }

enum DeliveryOfferStatus {
  initial,
  loading,
  loaded,
  empty,
  unauthenticated,
  error,
  offline,
}

/// Immutable view state for the Delivery Offer Surface.
class DeliveryOfferState {
  const DeliveryOfferState({
    this.status = DeliveryOfferStatus.initial,
    this.offers = const <DriverAssignmentSummary>[],
    this.errorMessage,
    this.runningOfferId,
    this.runningAction,
    this.actionErrorMessage,
    this.actionErrorIsOffline = false,
  });

  final DeliveryOfferStatus status;

  /// Offered assignments only (already filtered by the controller).
  final List<DriverAssignmentSummary> offers;

  /// Full-screen error copy (initial-load failures with no loaded data).
  final String? errorMessage;

  /// Assignment id of the offer whose accept/decline is in flight, or null.
  final String? runningOfferId;

  /// Which action is running on [runningOfferId], or null.
  final OfferAction? runningAction;

  /// Non-destructive inline action error (keeps the offer list visible).
  final String? actionErrorMessage;
  final bool actionErrorIsOffline;

  bool get isActionInFlight => runningOfferId != null;
  bool get hasActionError => actionErrorMessage != null;

  DeliveryOfferState copyWith({
    DeliveryOfferStatus? status,
    List<DriverAssignmentSummary>? offers,
    String? errorMessage,
    String? runningOfferId,
    OfferAction? runningAction,
    bool clearRunning = false,
    String? actionErrorMessage,
    bool? actionErrorIsOffline,
    bool clearActionError = false,
  }) {
    return DeliveryOfferState(
      status: status ?? this.status,
      offers: offers ?? this.offers,
      errorMessage: errorMessage ?? this.errorMessage,
      runningOfferId: clearRunning ? null : (runningOfferId ?? this.runningOfferId),
      runningAction: clearRunning ? null : (runningAction ?? this.runningAction),
      actionErrorMessage:
          clearActionError ? null : (actionErrorMessage ?? this.actionErrorMessage),
      actionErrorIsOffline:
          clearActionError ? false : (actionErrorIsOffline ?? this.actionErrorIsOffline),
    );
  }
}
