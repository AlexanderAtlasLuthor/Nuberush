// NubeRush Driver — read-only assignment models (Dr.1.3.F).
//
// From `GET /driver/assignments` (envelope of DriverAssignmentRead) and
// `GET /driver/assignments/{id}` (DriverAssignmentRead). The backend read model
// is deliberately PII-free: the order summary carries only lifecycle status +
// timestamps (no customer identity, money, items, or address), and the store
// summary is store context. The app only DISPLAYS this — it never computes
// lifecycle transitions or action eligibility locally. Status strings are kept
// raw so a new backend status never crashes the client.

import 'json_parse.dart';

/// Store context attached to an assignment.
class DriverAssignmentStore {
  const DriverAssignmentStore({
    required this.id,
    required this.name,
    required this.code,
    required this.timezone,
  });

  final String id;
  final String name;
  final String code;
  final String timezone;

  factory DriverAssignmentStore.fromJson(Map<String, dynamic> json) =>
      DriverAssignmentStore(
        id: asString(json['id']),
        name: asString(json['name']),
        code: asString(json['code']),
        timezone: asString(json['timezone']),
      );
}

/// PII-free order summary attached to an assignment (lifecycle + timestamps).
class DriverAssignmentOrder {
  const DriverAssignmentOrder({
    required this.id,
    required this.status,
    this.createdAt,
    this.updatedAt,
    this.acceptedAt,
    this.canceledAt,
    this.deliveredAt,
    this.returnedAt,
  });

  final String id;
  final String status;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final DateTime? acceptedAt;
  final DateTime? canceledAt;
  final DateTime? deliveredAt;
  final DateTime? returnedAt;

  factory DriverAssignmentOrder.fromJson(Map<String, dynamic> json) =>
      DriverAssignmentOrder(
        id: asString(json['id']),
        status: asString(json['status']),
        createdAt: asDate(json['created_at']),
        updatedAt: asDate(json['updated_at']),
        acceptedAt: asDate(json['accepted_at']),
        canceledAt: asDate(json['canceled_at']),
        deliveredAt: asDate(json['delivered_at']),
        returnedAt: asDate(json['returned_at']),
      );
}

/// Lightweight list-row view of an assignment.
class DriverAssignmentSummary {
  const DriverAssignmentSummary({
    required this.id,
    required this.orderId,
    required this.storeId,
    required this.status,
    this.storeName,
    this.orderStatus,
  });

  final String id;
  final String orderId;
  final String storeId;
  final String status;
  final String? storeName;
  final String? orderStatus;

  factory DriverAssignmentSummary.fromJson(Map<String, dynamic> json) {
    final store = json['store'];
    final order = json['order'];
    return DriverAssignmentSummary(
      id: asString(json['id']),
      orderId: asString(json['order_id']),
      storeId: asString(json['store_id']),
      status: asString(json['status']),
      storeName: store is Map ? asNullableString(store['name']) : null,
      orderStatus: order is Map ? asNullableString(order['status']) : null,
    );
  }
}

/// Full read-only assignment detail.
class DriverAssignmentDetail {
  const DriverAssignmentDetail({
    required this.id,
    required this.orderId,
    required this.storeId,
    required this.status,
    this.assignedAt,
    this.acceptedAt,
    this.declinedAt,
    this.canceledAt,
    this.completedAt,
    this.createdAt,
    this.updatedAt,
    this.order,
    this.store,
  });

  final String id;
  final String orderId;
  final String storeId;
  final String status;
  final DateTime? assignedAt;
  final DateTime? acceptedAt;
  final DateTime? declinedAt;
  final DateTime? canceledAt;
  final DateTime? completedAt;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final DriverAssignmentOrder? order;
  final DriverAssignmentStore? store;

  factory DriverAssignmentDetail.fromJson(Map<String, dynamic> json) {
    final order = json['order'];
    final store = json['store'];
    return DriverAssignmentDetail(
      id: asString(json['id']),
      orderId: asString(json['order_id']),
      storeId: asString(json['store_id']),
      status: asString(json['status']),
      assignedAt: asDate(json['assigned_at']),
      acceptedAt: asDate(json['accepted_at']),
      declinedAt: asDate(json['declined_at']),
      canceledAt: asDate(json['canceled_at']),
      completedAt: asDate(json['completed_at']),
      createdAt: asDate(json['created_at']),
      updatedAt: asDate(json['updated_at']),
      order: order is Map
          ? DriverAssignmentOrder.fromJson(Map<String, dynamic>.from(order))
          : null,
      store: store is Map
          ? DriverAssignmentStore.fromJson(Map<String, dynamic>.from(store))
          : null,
    );
  }
}

/// Parse the `GET /driver/assignments` envelope into summary rows.
List<DriverAssignmentSummary> parseAssignmentList(Map<String, dynamic> json) =>
    asMapList(json['items'])
        .map(DriverAssignmentSummary.fromJson)
        .toList(growable: false);
