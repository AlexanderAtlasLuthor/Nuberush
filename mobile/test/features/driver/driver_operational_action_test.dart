// Dr.1.3.G — operational action definition + display-only mapping tests.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_operational_action.dart';

void main() {
  group('operationalActionsFor (display-only mapping)', () {
    test('offered -> accept + decline', () {
      expect(
        operationalActionsFor(assignmentStatus: 'offered'),
        [DriverOperationalAction.accept, DriverOperationalAction.decline],
      );
    });

    test('accepted -> start', () {
      expect(
        operationalActionsFor(assignmentStatus: 'accepted'),
        [DriverOperationalAction.start],
      );
    });

    test('started maps each delivery state to a single next action', () {
      expect(
        operationalActionsFor(
            assignmentStatus: 'started', deliveryState: 'en_route_to_store'),
        [DriverOperationalAction.arriveStore],
      );
      expect(
        operationalActionsFor(
            assignmentStatus: 'started', deliveryState: 'arrived_at_store'),
        [DriverOperationalAction.pickup],
      );
      expect(
        operationalActionsFor(
            assignmentStatus: 'started', deliveryState: 'picked_up'),
        [DriverOperationalAction.departToCustomer],
      );
      expect(
        operationalActionsFor(
            assignmentStatus: 'started', deliveryState: 'en_route_to_customer'),
        [DriverOperationalAction.arriveCustomer],
      );
    });

    test('arrived_at_customer (compliance boundary) offers nothing in G', () {
      expect(
        operationalActionsFor(
            assignmentStatus: 'started', deliveryState: 'arrived_at_customer'),
        isEmpty,
      );
    });

    test('unknown / terminal statuses offer nothing (conservative default)',
        () {
      expect(operationalActionsFor(assignmentStatus: 'completed'), isEmpty);
      expect(operationalActionsFor(assignmentStatus: 'canceled'), isEmpty);
      expect(operationalActionsFor(assignmentStatus: 'something_new'), isEmpty);
      expect(
        operationalActionsFor(
            assignmentStatus: 'started', deliveryState: 'mystery_state'),
        isEmpty,
      );
    });
  });

  group('action metadata', () {
    test('only decline requires confirmation', () {
      for (final a in DriverOperationalAction.values) {
        expect(a.requiresConfirmation, a == DriverOperationalAction.decline);
      }
      expect(DriverOperationalAction.decline.confirmCopy, isNotNull);
    });

    test('ids match endpoint path segments', () {
      expect(DriverOperationalAction.arriveStore.id, 'arrive-store');
      expect(DriverOperationalAction.departToCustomer.id, 'depart-to-customer');
      expect(DriverOperationalAction.arriveCustomer.id, 'arrive-customer');
    });

    test('no compliance actions exist in the enum', () {
      final ids = DriverOperationalAction.values.map((a) => a.id).toSet();
      for (final forbidden in const [
        'verify-age',
        'proof',
        'complete',
        'fail',
        'return-to-store',
        'confirm-driver-return',
      ]) {
        expect(ids.contains(forbidden), isFalse);
      }
    });
  });
}
