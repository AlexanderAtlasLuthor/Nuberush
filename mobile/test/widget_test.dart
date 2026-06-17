// NubeRush Driver — skeleton smoke test (Dr.1.3.B).
//
// Verifies the app shell renders and shows the locked display name. It does
// not depend on the default Flutter counter template and exercises no API,
// auth, or driver business logic (none exist yet).

import 'package:flutter_test/flutter_test.dart';

import 'package:nuberush_driver/app/app.dart';

void main() {
  testWidgets('App renders the NubeRush Driver shell', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(const NubeRushDriverApp());
    await tester.pumpAndSettle();

    // The display name appears (AppBar title + body), confirming the shell
    // mounted. At least one occurrence is sufficient.
    expect(find.text('NubeRush Driver'), findsWidgets);
  });
}
