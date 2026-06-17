// Dr.1.3.H — compliance action definitions + display-only mapping tests.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_compliance_action.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_operational_action.dart';

void main() {
  group('complianceActionsFor (display-only)', () {
    test('not started -> nothing', () {
      expect(
        complianceActionsFor(
            assignmentStatus: 'offered', deliveryState: 'arrived_at_customer'),
        isEmpty,
      );
    });

    test('arrived_at_customer -> verify age + report failed', () {
      expect(
        complianceActionsFor(
            assignmentStatus: 'started', deliveryState: 'arrived_at_customer'),
        [
          DriverComplianceAction.verifyAge,
          DriverComplianceAction.reportFailedDelivery,
        ],
      );
    });

    test('id_verified -> proof + complete + report failed', () {
      expect(
        complianceActionsFor(
            assignmentStatus: 'started', deliveryState: 'id_verified'),
        [
          DriverComplianceAction.submitProof,
          DriverComplianceAction.completeDelivery,
          DriverComplianceAction.reportFailedDelivery,
        ],
      );
    });

    test('delivery_failed / returning_to_store -> return to store', () {
      expect(
        complianceActionsFor(
            assignmentStatus: 'started', deliveryState: 'delivery_failed'),
        [DriverComplianceAction.returnToStore],
      );
      expect(
        complianceActionsFor(
            assignmentStatus: 'started', deliveryState: 'returning_to_store'),
        [DriverComplianceAction.returnToStore],
      );
    });

    test('unknown delivery state -> nothing (conservative)', () {
      expect(
        complianceActionsFor(
            assignmentStatus: 'started', deliveryState: 'mystery'),
        isEmpty,
      );
    });
  });

  group('compliance action metadata', () {
    test('ids match endpoint segments and exclude confirm-driver-return', () {
      expect(DriverComplianceAction.verifyAge.id, 'verify-age');
      expect(DriverComplianceAction.submitProof.id, 'proof');
      expect(DriverComplianceAction.completeDelivery.id, 'complete');
      expect(DriverComplianceAction.reportFailedDelivery.id, 'fail');
      expect(DriverComplianceAction.returnToStore.id, 'return-to-store');
      final ids = DriverComplianceAction.values.map((a) => a.id).toSet();
      expect(ids.contains('confirm-driver-return'), isFalse);
    });

    test('compliance ids do not overlap operational ids', () {
      final opIds = DriverOperationalAction.values.map((a) => a.id).toSet();
      final compIds = DriverComplianceAction.values.map((a) => a.id).toSet();
      expect(opIds.intersection(compIds), isEmpty);
    });
  });
}
