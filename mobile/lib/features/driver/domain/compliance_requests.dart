// NubeRush Driver — compliance action request payloads (Dr.1.3.H).
//
// Exact mirrors of the backend request schemas (backend/app/schemas/driver.py):
//   - DriverVerifyAgeRequest        (verify-age)
//   - DriverProofSubmitRequest      (proof)
//   - DriverFailDeliveryRequest     (fail)
//   - DriverReturnToStoreRequest    (return-to-store)
//   - complete takes NO body.
//
// REDACTION-SAFE ONLY: these carry no raw ID image/number, OCR/barcode/biometric
// data, photo, signature, artifact path, DOB, or customer PII — the backend MVP
// is a manual checklist. The client never decides pass/fail beyond the user's
// form selection and never computes age locally.

/// verify-age outcome — wire values "pass" | "fail" | "manual_review".
enum VerifyAgeOutcome { pass, fail, manualReview }

extension VerifyAgeOutcomeX on VerifyAgeOutcome {
  String get wire => switch (this) {
        VerifyAgeOutcome.pass => 'pass',
        VerifyAgeOutcome.fail => 'fail',
        VerifyAgeOutcome.manualReview => 'manual_review',
      };
  String get label => switch (this) {
        VerifyAgeOutcome.pass => 'Pass',
        VerifyAgeOutcome.fail => 'Fail',
        VerifyAgeOutcome.manualReview => 'Manual review',
      };
}

/// Structured 21+ failure reasons (backend DriverDeliveryVerificationFailureReason).
enum VerifyAgeFailureReason {
  customerUnderage,
  idInvalid,
  idExpired,
  idNotAvailable,
  customerRefused,
  manualReviewRequired,
  otherManualReview,
}

extension VerifyAgeFailureReasonX on VerifyAgeFailureReason {
  String get wire => switch (this) {
        VerifyAgeFailureReason.customerUnderage => 'customer_underage',
        VerifyAgeFailureReason.idInvalid => 'id_invalid',
        VerifyAgeFailureReason.idExpired => 'id_expired',
        VerifyAgeFailureReason.idNotAvailable => 'id_not_available',
        VerifyAgeFailureReason.customerRefused => 'customer_refused',
        VerifyAgeFailureReason.manualReviewRequired => 'manual_review_required',
        VerifyAgeFailureReason.otherManualReview => 'other_manual_review',
      };
}

/// Structured failed-delivery reasons (backend DriverDeliveryFailureReason).
enum FailureReason {
  customerUnavailable,
  customerUnderage,
  idInvalid,
  idExpired,
  customerRefused,
  unsafeLocation,
  restrictedProductIssue,
  storeIssue,
  driverEmergency,
  otherManualReview,
}

extension FailureReasonX on FailureReason {
  String get wire => switch (this) {
        FailureReason.customerUnavailable => 'customer_unavailable',
        FailureReason.customerUnderage => 'customer_underage',
        FailureReason.idInvalid => 'id_invalid',
        FailureReason.idExpired => 'id_expired',
        FailureReason.customerRefused => 'customer_refused',
        FailureReason.unsafeLocation => 'unsafe_location',
        FailureReason.restrictedProductIssue => 'restricted_product_issue',
        FailureReason.storeIssue => 'store_issue',
        FailureReason.driverEmergency => 'driver_emergency',
        FailureReason.otherManualReview => 'other_manual_review',
      };
  String get label => switch (this) {
        FailureReason.customerUnavailable => 'Customer unavailable',
        FailureReason.customerUnderage => 'Customer underage',
        FailureReason.idInvalid => 'ID invalid',
        FailureReason.idExpired => 'ID expired',
        FailureReason.customerRefused => 'Customer refused',
        FailureReason.unsafeLocation => 'Unsafe location',
        FailureReason.restrictedProductIssue => 'Restricted product issue',
        FailureReason.storeIssue => 'Store issue',
        FailureReason.driverEmergency => 'Driver emergency',
        FailureReason.otherManualReview => 'Other (manual review)',
      };
}

/// return-to-store custody step (backend DriverReturnToStoreAction).
enum ReturnAction { start, arrive }

extension ReturnActionX on ReturnAction {
  String get wire => this == ReturnAction.start ? 'start' : 'arrive';
}

/// Body for POST /driver/assignments/{id}/verify-age.
class VerifyAgeRequest {
  const VerifyAgeRequest({
    required this.outcome,
    this.failureReasonCode,
    this.ageOver21Confirmed,
    this.idExpirationChecked,
    this.idNotExpired,
    this.note,
  });

  final VerifyAgeOutcome outcome;
  final VerifyAgeFailureReason? failureReasonCode;
  final bool? ageOver21Confirmed;
  final bool? idExpirationChecked;
  final bool? idNotExpired;
  final String? note;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'outcome': outcome.wire,
        if (failureReasonCode != null)
          'failure_reason_code': failureReasonCode!.wire,
        if (ageOver21Confirmed != null)
          'age_over_21_confirmed': ageOver21Confirmed,
        if (idExpirationChecked != null)
          'id_expiration_checked': idExpirationChecked,
        if (idNotExpired != null) 'id_not_expired': idNotExpired,
        if (note != null && note!.isNotEmpty) 'note': note,
      };
}

/// Body for POST /driver/assignments/{id}/proof. All three confirmations must
/// be true (the backend rejects otherwise with 422).
class ProofRequest {
  const ProofRequest({
    required this.recipientPresentConfirmed,
    required this.handoffConfirmed,
    required this.restrictedNotLeftUnattended,
    this.note,
  });

  final bool recipientPresentConfirmed;
  final bool handoffConfirmed;
  final bool restrictedNotLeftUnattended;
  final String? note;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'recipient_present_confirmed': recipientPresentConfirmed,
        'handoff_confirmed': handoffConfirmed,
        'restricted_not_left_unattended': restrictedNotLeftUnattended,
        if (note != null && note!.isNotEmpty) 'note': note,
      };
}

/// Body for POST /driver/assignments/{id}/fail.
class FailRequest {
  const FailRequest({required this.reasonCode, this.note});

  final FailureReason reasonCode;
  final String? note;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'reason_code': reasonCode.wire,
        if (note != null && note!.isNotEmpty) 'note': note,
      };
}

/// Body for POST /driver/assignments/{id}/return-to-store.
class ReturnToStoreRequest {
  const ReturnToStoreRequest({required this.action, this.note});

  final ReturnAction action;
  final String? note;

  Map<String, dynamic> toJson() => <String, dynamic>{
        'action': action.wire,
        if (note != null && note!.isNotEmpty) 'note': note,
      };
}
