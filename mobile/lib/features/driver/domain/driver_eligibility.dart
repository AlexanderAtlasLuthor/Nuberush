// NubeRush Driver — read-only eligibility model (Dr.1.3.E).
//
// Backend-authoritative go-online eligibility from `GET /driver/eligibility`
// (backend DriverEligibilityRead). The app only DISPLAYS `can_go_online` and
// the structured blockers — it never computes or overrides eligibility. Codes
// are kept as plain strings so a new backend blocker code never crashes the
// client.

/// A single backend-reported reason the driver cannot go online.
class DriverEligibilityBlocker {
  const DriverEligibilityBlocker({
    required this.code,
    required this.message,
    required this.source,
    required this.severity,
  });

  final String code;
  final String message;
  final String source;
  final String severity;

  factory DriverEligibilityBlocker.fromJson(Map<String, dynamic> json) =>
      DriverEligibilityBlocker(
        code: _asString(json['code']),
        message: _asString(json['message']),
        source: _asString(json['source']),
        severity: _asString(json['severity']),
      );
}

/// Backend-computed go-online eligibility for the current driver.
class DriverEligibility {
  const DriverEligibility({
    required this.canGoOnline,
    required this.blockers,
    required this.userActive,
    this.driverStatus,
    this.driverApprovalStatus,
    this.storeActive,
    this.evaluatedAt,
  });

  final bool canGoOnline;
  final List<DriverEligibilityBlocker> blockers;
  final bool userActive;
  final String? driverStatus;
  final String? driverApprovalStatus;
  final bool? storeActive;
  final DateTime? evaluatedAt;

  factory DriverEligibility.fromJson(Map<String, dynamic> json) {
    final Object? rawBlockers = json['blockers'];
    final List<DriverEligibilityBlocker> blockers = rawBlockers is List
        ? rawBlockers
            .whereType<Map>()
            .map((m) => DriverEligibilityBlocker.fromJson(
                  Map<String, dynamic>.from(m),
                ))
            .toList(growable: false)
        : const <DriverEligibilityBlocker>[];

    return DriverEligibility(
      canGoOnline: _asBool(json['can_go_online']),
      blockers: blockers,
      userActive: _asBool(json['user_active']),
      driverStatus: _asNullableString(json['driver_status']),
      driverApprovalStatus: _asNullableString(json['driver_approval_status']),
      storeActive: json['store_active'] is bool ? json['store_active'] as bool : null,
      evaluatedAt: _asDate(json['evaluated_at']),
    );
  }
}

String _asString(Object? value) => value is String ? value : (value?.toString() ?? '');

String? _asNullableString(Object? value) => value is String ? value : null;

bool _asBool(Object? value) => value is bool ? value : false;

DateTime? _asDate(Object? value) =>
    value is String ? DateTime.tryParse(value) : null;
