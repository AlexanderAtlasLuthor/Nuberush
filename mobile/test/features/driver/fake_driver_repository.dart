// Dr.1.3.E — shared fake repository for controller/widget tests. No network.

import 'dart:async';

import 'package:nuberush_driver/features/driver/data/driver_repository.dart';
import 'package:nuberush_driver/features/driver/domain/compliance_requests.dart';
import 'package:nuberush_driver/features/driver/domain/driver_assignment.dart';
import 'package:nuberush_driver/features/driver/domain/driver_delivery_state.dart';
import 'package:nuberush_driver/features/driver/domain/driver_eligibility.dart';
import 'package:nuberush_driver/features/driver/domain/driver_profile.dart';

DriverAssignmentSummary sampleSummary({String id = 'a-1'}) =>
    DriverAssignmentSummary(
      id: id,
      orderId: 'o-1',
      storeId: 's-1',
      status: 'offered',
      storeName: 'Test Store',
      orderStatus: 'pending',
    );

DriverAssignmentDetail sampleDetail({String id = 'a-1'}) =>
    DriverAssignmentDetail(
      id: id,
      orderId: 'o-1',
      storeId: 's-1',
      status: 'started',
    );

DriverDeliveryState sampleDeliveryState({String assignmentId = 'a-1'}) =>
    DriverDeliveryState(
      id: 'ds-1',
      assignmentId: assignmentId,
      orderId: 'o-1',
      state: 'en_route_to_store',
    );

DriverProfile sampleProfile() => const DriverProfile(
      id: 'd-1',
      userId: 'u-1',
      storeId: 's-1',
      status: 'active',
      approvalStatus: 'approved',
    );

DriverEligibility sampleEligibility({bool canGoOnline = true}) =>
    DriverEligibility(
      canGoOnline: canGoOnline,
      blockers: canGoOnline
          ? const []
          : const [
              DriverEligibilityBlocker(
                code: 'driver_approval_pending',
                message: 'Approval pending',
                source: 'driver_profile',
                severity: 'blocker',
              ),
            ],
      userActive: true,
    );

/// Configurable fake. Set the `*Error` fields to make a fetch throw.
class FakeDriverRepository implements DriverReadRepository {
  FakeDriverRepository({
    DriverProfile? profile,
    DriverEligibility? eligibility,
    List<DriverAssignmentSummary>? assignments,
    DriverAssignmentDetail? detail,
    DriverDeliveryState? deliveryState,
    this.profileError,
    this.eligibilityError,
    this.assignmentsError,
    this.detailError,
    this.deliveryStateError,
  })  : profile = profile ?? sampleProfile(),
        eligibility = eligibility ?? sampleEligibility(),
        assignments = assignments ?? <DriverAssignmentSummary>[sampleSummary()],
        detail = detail ?? sampleDetail(),
        deliveryState = deliveryState ?? sampleDeliveryState();

  DriverProfile profile;
  DriverEligibility eligibility;
  List<DriverAssignmentSummary> assignments;
  DriverAssignmentDetail detail;
  DriverDeliveryState deliveryState;

  Object? profileError;
  Object? eligibilityError;
  Object? assignmentsError;
  Object? detailError;
  Object? deliveryStateError;

  int profileCalls = 0;
  int eligibilityCalls = 0;
  int assignmentsCalls = 0;
  int detailCalls = 0;
  int deliveryStateCalls = 0;

  /// Operational action calls (Dr.1.3.G): action id -> call count.
  final Map<String, int> actionCalls = <String, int>{};

  /// If set, the next matching action throws this error.
  Object? actionError;

  /// If set, actions await this gate before completing — lets a widget test
  /// observe the in-flight (loading/disabled) UI before resolving the action.
  Completer<void>? actionGate;

  @override
  Future<DriverProfile> fetchDriverProfile() async {
    profileCalls++;
    final err = profileError;
    if (err != null) throw err;
    return profile;
  }

  @override
  Future<DriverEligibility> fetchDriverEligibility() async {
    eligibilityCalls++;
    final err = eligibilityError;
    if (err != null) throw err;
    return eligibility;
  }

  @override
  Future<List<DriverAssignmentSummary>> fetchAssignments() async {
    assignmentsCalls++;
    final err = assignmentsError;
    if (err != null) throw err;
    return assignments;
  }

  @override
  Future<DriverAssignmentDetail> fetchAssignmentDetail(
    String assignmentId,
  ) async {
    detailCalls++;
    final err = detailError;
    if (err != null) throw err;
    return detail;
  }

  @override
  Future<DriverDeliveryState> fetchDeliveryState(String assignmentId) async {
    deliveryStateCalls++;
    final err = deliveryStateError;
    if (err != null) throw err;
    return deliveryState;
  }

  Future<void> _recordAction(String id) async {
    actionCalls[id] = (actionCalls[id] ?? 0) + 1;
    final gate = actionGate;
    if (gate != null) await gate.future;
    final err = actionError;
    if (err != null) throw err;
  }

  @override
  Future<void> acceptAssignment(String assignmentId) => _recordAction('accept');

  @override
  Future<void> declineAssignment(String assignmentId) =>
      _recordAction('decline');

  @override
  Future<void> startAssignment(String assignmentId) => _recordAction('start');

  @override
  Future<void> arriveStore(String assignmentId) =>
      _recordAction('arrive-store');

  @override
  Future<void> pickupAssignment(String assignmentId) =>
      _recordAction('pickup');

  @override
  Future<void> departToCustomer(String assignmentId) =>
      _recordAction('depart-to-customer');

  @override
  Future<void> arriveCustomer(String assignmentId) =>
      _recordAction('arrive-customer');

  // --- Compliance (Dr.1.3.H) ------------------------------------------- //

  /// Captures the last compliance request body submitted (by action id).
  final Map<String, Object?> complianceBodies = <String, Object?>{};

  Future<void> _recordCompliance(String id, Object? body) async {
    actionCalls[id] = (actionCalls[id] ?? 0) + 1;
    complianceBodies[id] = body;
    final gate = actionGate;
    if (gate != null) await gate.future;
    final err = actionError;
    if (err != null) throw err;
  }

  @override
  Future<void> verifyAge(String assignmentId, VerifyAgeRequest request) =>
      _recordCompliance('verify-age', request.toJson());

  @override
  Future<void> submitProof(String assignmentId, ProofRequest request) =>
      _recordCompliance('proof', request.toJson());

  @override
  Future<void> completeDelivery(String assignmentId) =>
      _recordCompliance('complete', null);

  @override
  Future<void> failDelivery(String assignmentId, FailRequest request) =>
      _recordCompliance('fail', request.toJson());

  @override
  Future<void> returnToStore(
    String assignmentId,
    ReturnToStoreRequest request,
  ) =>
      _recordCompliance('return-to-store', request.toJson());
}
