// NubeRush Driver — read-only driver profile model (Dr.1.3.E).
//
// Self-scoped view from `GET /driver/me` (backend DriverProfileRead). The app
// only DISPLAYS this; it never decides eligibility or any business authority
// locally. Parsing is tolerant of missing/null fields so a backend addition
// never crashes the client.

/// A driver's own operational profile, as returned by `GET /driver/me`.
class DriverProfile {
  const DriverProfile({
    required this.id,
    required this.userId,
    required this.storeId,
    required this.status,
    required this.approvalStatus,
    this.createdAt,
    this.updatedAt,
    this.activatedAt,
    this.deactivatedAt,
    this.approvedAt,
  });

  final String id;
  final String userId;
  final String storeId;
  final String status;
  final String approvalStatus;
  final DateTime? createdAt;
  final DateTime? updatedAt;
  final DateTime? activatedAt;
  final DateTime? deactivatedAt;
  final DateTime? approvedAt;

  factory DriverProfile.fromJson(Map<String, dynamic> json) => DriverProfile(
        id: _asString(json['id']),
        userId: _asString(json['user_id']),
        storeId: _asString(json['store_id']),
        status: _asString(json['status']),
        approvalStatus: _asString(json['approval_status']),
        createdAt: _asDate(json['created_at']),
        updatedAt: _asDate(json['updated_at']),
        activatedAt: _asDate(json['activated_at']),
        deactivatedAt: _asDate(json['deactivated_at']),
        approvedAt: _asDate(json['approved_at']),
      );
}

String _asString(Object? value) => value is String ? value : (value?.toString() ?? '');

DateTime? _asDate(Object? value) =>
    value is String ? DateTime.tryParse(value) : null;
