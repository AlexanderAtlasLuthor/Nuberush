// Dr.1.3.F — assignment + delivery-state model parsing tests.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/domain/driver_delivery_state.dart';

void main() {
  group('DriverAssignmentSummary / list envelope', () {
    test('parses an assignment summary row', () {
      final s = DriverAssignmentSummary.fromJson({
        'id': 'a-1',
        'order_id': 'o-1',
        'store_id': 's-1',
        'status': 'offered',
        'store': {'name': 'Test Store'},
        'order': {'status': 'pending'},
      });
      expect(s.id, 'a-1');
      expect(s.orderId, 'o-1');
      expect(s.status, 'offered');
      expect(s.storeName, 'Test Store');
      expect(s.orderStatus, 'pending');
    });

    test('parseAssignmentList extracts items from the envelope', () {
      final list = parseAssignmentList({
        'items': [
          {'id': 'a-1', 'order_id': 'o-1', 'store_id': 's-1', 'status': 'offered'},
          {'id': 'a-2', 'order_id': 'o-2', 'store_id': 's-1', 'status': 'started'},
        ],
        'total': 2,
        'limit': 50,
        'offset': 0,
      });
      expect(list, hasLength(2));
      expect(list.first.id, 'a-1');
      expect(list.last.status, 'started');
    });

    test('parseAssignmentList tolerates a missing items key', () {
      expect(parseAssignmentList({}), isEmpty);
    });
  });

  group('DriverAssignmentDetail', () {
    test('parses detail with nested order + store', () {
      final d = DriverAssignmentDetail.fromJson({
        'id': 'a-1',
        'order_id': 'o-1',
        'store_id': 's-1',
        'driver_profile_id': 'd-1',
        'status': 'started',
        'created_at': '2026-06-17T10:00:00Z',
        'updated_at': '2026-06-17T11:00:00Z',
        'order': {
          'id': 'o-1',
          'status': 'out_for_delivery',
          'created_at': '2026-06-17T09:00:00Z',
          'updated_at': '2026-06-17T10:00:00Z',
        },
        'store': {
          'id': 's-1',
          'name': 'Test Store',
          'code': 'TS',
          'timezone': 'America/New_York',
        },
      });
      expect(d.id, 'a-1');
      expect(d.status, 'started');
      expect(d.order?.status, 'out_for_delivery');
      expect(d.store?.name, 'Test Store');
      expect(d.store?.timezone, 'America/New_York');
    });

    test('tolerates missing nested objects', () {
      final d = DriverAssignmentDetail.fromJson({
        'id': 'a-1',
        'order_id': 'o-1',
        'store_id': 's-1',
        'status': 'offered',
      });
      expect(d.order, isNull);
      expect(d.store, isNull);
    });
  });

  group('DriverDeliveryState', () {
    test('parses the delivery-state shape', () {
      final ds = DriverDeliveryState.fromJson({
        'id': 'ds-1',
        'assignment_id': 'a-1',
        'order_id': 'o-1',
        'driver_profile_id': 'd-1',
        'store_id': 's-1',
        'state': 'en_route_to_customer',
        'state_started_at': '2026-06-17T12:00:00Z',
        'last_transition_at': '2026-06-17T12:30:00Z',
      });
      expect(ds.assignmentId, 'a-1');
      expect(ds.state, 'en_route_to_customer');
      expect(ds.stateStartedAt, isNotNull);
    });

    test('keeps unknown state strings verbatim and tolerates missing fields',
        () {
      final ds = DriverDeliveryState.fromJson({
        'id': 'ds-1',
        'assignment_id': 'a-1',
        'order_id': 'o-1',
        'state': 'some_future_state',
      });
      expect(ds.state, 'some_future_state');
      expect(ds.lastTransitionAt, isNull);
    });
  });
}
