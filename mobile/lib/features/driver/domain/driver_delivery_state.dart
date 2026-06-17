// NubeRush Driver — read-only delivery operational state (Dr.1.3.F).
//
// From `GET /driver/assignments/{id}/delivery-state`
// (DriverDeliveryOperationalStateRead). The physical driver-flow axis, distinct
// from order status and assignment lifecycle. The app DISPLAYS `state` only —
// it never computes or advances transitions locally. `state` is kept raw.

import 'json_parse.dart';

class DriverDeliveryState {
  const DriverDeliveryState({
    required this.id,
    required this.assignmentId,
    required this.orderId,
    required this.state,
    this.stateStartedAt,
    this.lastTransitionAt,
    this.createdAt,
    this.updatedAt,
  });

  final String id;
  final String assignmentId;
  final String orderId;
  final String state;
  final DateTime? stateStartedAt;
  final DateTime? lastTransitionAt;
  final DateTime? createdAt;
  final DateTime? updatedAt;

  factory DriverDeliveryState.fromJson(Map<String, dynamic> json) =>
      DriverDeliveryState(
        id: asString(json['id']),
        assignmentId: asString(json['assignment_id']),
        orderId: asString(json['order_id']),
        state: asString(json['state']),
        stateStartedAt: asDate(json['state_started_at']),
        lastTransitionAt: asDate(json['last_transition_at']),
        createdAt: asDate(json['created_at']),
        updatedAt: asDate(json['updated_at']),
      );
}
