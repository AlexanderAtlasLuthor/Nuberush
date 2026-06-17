// Dr.1.3.H — compliance request payload tests (exact backend wire shapes).

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/features/driver/domain/compliance_requests.dart';

void main() {
  group('VerifyAgeRequest.toJson', () {
    test('pass omits failure_reason_code', () {
      final j = const VerifyAgeRequest(outcome: VerifyAgeOutcome.pass).toJson();
      expect(j['outcome'], 'pass');
      expect(j.containsKey('failure_reason_code'), isFalse);
    });

    test('fail includes failure_reason_code wire value', () {
      final j = const VerifyAgeRequest(
        outcome: VerifyAgeOutcome.fail,
        failureReasonCode: VerifyAgeFailureReason.idExpired,
      ).toJson();
      expect(j['outcome'], 'fail');
      expect(j['failure_reason_code'], 'id_expired');
    });

    test('manual_review wire value + optional checklist/note', () {
      final j = const VerifyAgeRequest(
        outcome: VerifyAgeOutcome.manualReview,
        ageOver21Confirmed: true,
        note: 'looks ok',
      ).toJson();
      expect(j['outcome'], 'manual_review');
      expect(j['age_over_21_confirmed'], true);
      expect(j['note'], 'looks ok');
      // Unset optionals are omitted.
      expect(j.containsKey('id_expiration_checked'), isFalse);
    });
  });

  test('ProofRequest.toJson carries the three confirmations', () {
    final j = const ProofRequest(
      recipientPresentConfirmed: true,
      handoffConfirmed: true,
      restrictedNotLeftUnattended: true,
    ).toJson();
    expect(j['recipient_present_confirmed'], true);
    expect(j['handoff_confirmed'], true);
    expect(j['restricted_not_left_unattended'], true);
  });

  test('FailRequest.toJson carries reason_code wire value', () {
    final j = const FailRequest(reasonCode: FailureReason.unsafeLocation)
        .toJson();
    expect(j['reason_code'], 'unsafe_location');
  });

  test('ReturnToStoreRequest.toJson carries action wire value', () {
    expect(
      const ReturnToStoreRequest(action: ReturnAction.start).toJson()['action'],
      'start',
    );
    expect(
      const ReturnToStoreRequest(action: ReturnAction.arrive)
          .toJson()['action'],
      'arrive',
    );
  });

  test('all failure reason wire values match backend enum', () {
    expect(
      FailureReason.values.map((r) => r.wire).toSet(),
      {
        'customer_unavailable',
        'customer_underage',
        'id_invalid',
        'id_expired',
        'customer_refused',
        'unsafe_location',
        'restricted_product_issue',
        'store_issue',
        'driver_emergency',
        'other_manual_review',
      },
    );
  });
}
