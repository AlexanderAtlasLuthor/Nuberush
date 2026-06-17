// Dr.1.3.E — driver read-only model parsing tests.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/features/driver/domain/driver_eligibility.dart';
import 'package:nuberush_driver/features/driver/domain/driver_profile.dart';

void main() {
  group('DriverProfile.fromJson', () {
    test('parses the expected /driver/me shape', () {
      final p = DriverProfile.fromJson({
        'id': 'd-1',
        'user_id': 'u-1',
        'store_id': 's-1',
        'status': 'active',
        'approval_status': 'approved',
        'created_at': '2026-06-17T10:00:00Z',
        'updated_at': '2026-06-17T11:00:00Z',
        'activated_at': '2026-06-17T10:30:00Z',
        'deactivated_at': null,
        'approved_at': '2026-06-17T10:15:00Z',
      });
      expect(p.id, 'd-1');
      expect(p.userId, 'u-1');
      expect(p.storeId, 's-1');
      expect(p.status, 'active');
      expect(p.approvalStatus, 'approved');
      expect(p.createdAt, isNotNull);
      expect(p.deactivatedAt, isNull);
    });

    test('tolerates missing optional fields', () {
      final p = DriverProfile.fromJson({
        'id': 'd-1',
        'user_id': 'u-1',
        'store_id': 's-1',
        'status': 'pending',
        'approval_status': 'pending',
      });
      expect(p.createdAt, isNull);
      expect(p.approvedAt, isNull);
      expect(p.status, 'pending');
    });
  });

  group('DriverEligibility.fromJson', () {
    test('parses can_go_online true with no blockers', () {
      final e = DriverEligibility.fromJson({
        'can_go_online': true,
        'blockers': [],
        'driver_status': 'active',
        'driver_approval_status': 'approved',
        'user_active': true,
        'store_active': true,
        'evaluated_at': '2026-06-17T12:00:00Z',
      });
      expect(e.canGoOnline, isTrue);
      expect(e.blockers, isEmpty);
      expect(e.userActive, isTrue);
      expect(e.storeActive, isTrue);
      expect(e.evaluatedAt, isNotNull);
    });

    test('parses blockers list', () {
      final e = DriverEligibility.fromJson({
        'can_go_online': false,
        'blockers': [
          {
            'code': 'driver_approval_pending',
            'message': 'Approval pending',
            'source': 'driver_profile',
            'severity': 'blocker',
          },
        ],
        'driver_status': 'pending',
        'driver_approval_status': 'pending',
        'user_active': true,
        'store_active': null,
        'evaluated_at': '2026-06-17T12:00:00Z',
      });
      expect(e.canGoOnline, isFalse);
      expect(e.blockers, hasLength(1));
      expect(e.blockers.single.code, 'driver_approval_pending');
      expect(e.blockers.single.message, 'Approval pending');
      expect(e.storeActive, isNull);
    });

    test('tolerates missing/invalid fields with safe defaults', () {
      final e = DriverEligibility.fromJson({});
      expect(e.canGoOnline, isFalse);
      expect(e.blockers, isEmpty);
      expect(e.userActive, isFalse);
      expect(e.driverStatus, isNull);
      expect(e.evaluatedAt, isNull);
    });
  });
}
