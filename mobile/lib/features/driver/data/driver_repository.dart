// NubeRush Driver — read-only driver repository (Dr.1.3.E).
//
// Thin adapter over the core ApiClient for the two read-only endpoints in
// scope: `GET /driver/me` and `GET /driver/eligibility`. No POST/actions, no
// assignment/compliance endpoints, no caching, no retry/offline — those are
// later subphases. `ApiError` is allowed to bubble to the controller, which
// maps it to a view state.

import '../../../core/api/api_client.dart';
import '../../../core/util/idempotency.dart';
import '../domain/compliance_requests.dart';
import '../domain/driver_assignment.dart';
import '../domain/driver_delivery_state.dart';
import '../domain/driver_eligibility.dart';
import '../domain/driver_profile.dart';

/// Read-only driver data source.
abstract class DriverReadRepository {
  /// `GET /driver/me`.
  Future<DriverProfile> fetchDriverProfile();

  /// `GET /driver/eligibility`.
  Future<DriverEligibility> fetchDriverEligibility();

  /// `GET /driver/assignments`.
  Future<List<DriverAssignmentSummary>> fetchAssignments();

  /// `GET /driver/assignments/{assignment_id}`.
  Future<DriverAssignmentDetail> fetchAssignmentDetail(String assignmentId);

  /// `GET /driver/assignments/{assignment_id}/delivery-state`.
  Future<DriverDeliveryState> fetchDeliveryState(String assignmentId);

  // --- Operational actions (Dr.1.3.G) ---------------------------------- //
  // All seven are bodyless POSTs (the backend routes take no request body —
  // decline included). The backend remains the lifecycle authority; these
  // just submit the action and the caller re-reads detail + delivery-state.

  /// `POST /driver/assignments/{assignment_id}/accept`.
  Future<void> acceptAssignment(String assignmentId);

  /// `POST /driver/assignments/{assignment_id}/decline`.
  Future<void> declineAssignment(String assignmentId);

  /// `POST /driver/assignments/{assignment_id}/start`.
  Future<void> startAssignment(String assignmentId);

  /// `POST /driver/assignments/{assignment_id}/arrive-store`.
  Future<void> arriveStore(String assignmentId);

  /// `POST /driver/assignments/{assignment_id}/pickup`.
  Future<void> pickupAssignment(String assignmentId);

  /// `POST /driver/assignments/{assignment_id}/depart-to-customer`.
  Future<void> departToCustomer(String assignmentId);

  /// `POST /driver/assignments/{assignment_id}/arrive-customer`.
  Future<void> arriveCustomer(String assignmentId);

  // --- Compliance actions (Dr.1.3.H) ----------------------------------- //
  // Each carries the exact backend request body and an optional client-
  // generated `Idempotency-Key`. The backend is the compliance authority —
  // it gates outcomes and the caller re-reads detail + delivery-state.

  /// `POST /driver/assignments/{assignment_id}/verify-age`.
  Future<void> verifyAge(String assignmentId, VerifyAgeRequest request);

  /// `POST /driver/assignments/{assignment_id}/proof`.
  Future<void> submitProof(String assignmentId, ProofRequest request);

  /// `POST /driver/assignments/{assignment_id}/complete` (bodyless).
  Future<void> completeDelivery(String assignmentId);

  /// `POST /driver/assignments/{assignment_id}/fail`.
  Future<void> failDelivery(String assignmentId, FailRequest request);

  /// `POST /driver/assignments/{assignment_id}/return-to-store`.
  Future<void> returnToStore(String assignmentId, ReturnToStoreRequest request);
}

/// [DriverReadRepository] backed by the core [ApiClient].
class ApiDriverRepository implements DriverReadRepository {
  ApiDriverRepository(this._client, {IdempotencyKeyGenerator? keyGenerator})
      : _keyGenerator = keyGenerator ?? defaultIdempotencyKey;

  /// Generates a fresh `Idempotency-Key` per compliance attempt. Injectable
  /// for deterministic tests.
  final IdempotencyKeyGenerator _keyGenerator;

  final ApiClient _client;

  @override
  Future<DriverProfile> fetchDriverProfile() async {
    final dynamic body = await _client.get('/driver/me');
    return DriverProfile.fromJson(_asMap(body));
  }

  @override
  Future<DriverEligibility> fetchDriverEligibility() async {
    final dynamic body = await _client.get('/driver/eligibility');
    return DriverEligibility.fromJson(_asMap(body));
  }

  @override
  Future<List<DriverAssignmentSummary>> fetchAssignments() async {
    final dynamic body = await _client.get('/driver/assignments');
    return parseAssignmentList(_asMap(body));
  }

  @override
  Future<DriverAssignmentDetail> fetchAssignmentDetail(
    String assignmentId,
  ) async {
    final dynamic body = await _client.get('/driver/assignments/$assignmentId');
    return DriverAssignmentDetail.fromJson(_asMap(body));
  }

  @override
  Future<DriverDeliveryState> fetchDeliveryState(String assignmentId) async {
    final dynamic body =
        await _client.get('/driver/assignments/$assignmentId/delivery-state');
    return DriverDeliveryState.fromJson(_asMap(body));
  }

  // --- Operational actions (Dr.1.3.G): bodyless POSTs ------------------ //

  @override
  Future<void> acceptAssignment(String assignmentId) =>
      _action(assignmentId, 'accept');

  @override
  Future<void> declineAssignment(String assignmentId) =>
      _action(assignmentId, 'decline');

  @override
  Future<void> startAssignment(String assignmentId) =>
      _action(assignmentId, 'start');

  @override
  Future<void> arriveStore(String assignmentId) =>
      _action(assignmentId, 'arrive-store');

  @override
  Future<void> pickupAssignment(String assignmentId) =>
      _action(assignmentId, 'pickup');

  @override
  Future<void> departToCustomer(String assignmentId) =>
      _action(assignmentId, 'depart-to-customer');

  @override
  Future<void> arriveCustomer(String assignmentId) =>
      _action(assignmentId, 'arrive-customer');

  /// Submit a bodyless operational action POST. Response is ignored; callers
  /// re-read detail + delivery-state for the authoritative new state.
  Future<void> _action(String assignmentId, String action) async {
    await _client.post('/driver/assignments/$assignmentId/$action');
  }

  // --- Compliance actions (Dr.1.3.H): bodied POSTs + Idempotency-Key --- //

  @override
  Future<void> verifyAge(String assignmentId, VerifyAgeRequest request) =>
      _compliance(assignmentId, 'verify-age', request.toJson());

  @override
  Future<void> submitProof(String assignmentId, ProofRequest request) =>
      _compliance(assignmentId, 'proof', request.toJson());

  @override
  Future<void> completeDelivery(String assignmentId) =>
      // Bodyless per backend contract; still carries an Idempotency-Key.
      _compliance(assignmentId, 'complete', null);

  @override
  Future<void> failDelivery(String assignmentId, FailRequest request) =>
      _compliance(assignmentId, 'fail', request.toJson());

  @override
  Future<void> returnToStore(
    String assignmentId,
    ReturnToStoreRequest request,
  ) =>
      _compliance(assignmentId, 'return-to-store', request.toJson());

  /// Submit a compliance action POST with the exact backend body (or none) and
  /// a fresh client-generated Idempotency-Key. Response is ignored; callers
  /// re-read detail + delivery-state for the authoritative new state.
  Future<void> _compliance(
    String assignmentId,
    String action,
    Map<String, dynamic>? body,
  ) async {
    await _client.post(
      '/driver/assignments/$assignmentId/$action',
      body: body,
      idempotencyKey: _keyGenerator(),
    );
  }

  Map<String, dynamic> _asMap(dynamic body) =>
      body is Map<String, dynamic> ? body : <String, dynamic>{};
}
