// NubeRush Driver — tolerant JSON parse helpers (Dr.1.3.F).
//
// Small, shared helpers so domain models stay forgiving of missing/null/extra
// backend fields. No business logic — pure coercion.

String asString(Object? value) =>
    value is String ? value : (value?.toString() ?? '');

String? asNullableString(Object? value) => value is String ? value : null;

bool asBool(Object? value) => value is bool ? value : false;

DateTime? asDate(Object? value) =>
    value is String ? DateTime.tryParse(value) : null;

Map<String, dynamic> asMap(Object? value) =>
    value is Map<String, dynamic> ? value : const <String, dynamic>{};

List<Map<String, dynamic>> asMapList(Object? value) => value is List
    ? value
        .whereType<Map>()
        .map((m) => Map<String, dynamic>.from(m))
        .toList(growable: false)
    : const <Map<String, dynamic>>[];
