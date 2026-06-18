// Dr.1.5.J — Static Safety / Support surface tests.
//
// These screens are static/local-only: they take no controller, repository, or
// ApiClient, so they structurally cannot make a backend call. The tests render
// each screen, exercise local navigation, and assert no submission/forbidden
// content. No FakeDriverRepository is involved anywhere in this file.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/app/app.dart';
import 'package:nuberush_driver/features/driver/presentation/emergency_help_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/report_bug_info_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/report_incident_info_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/safety_toolkit_screen.dart';
import 'package:nuberush_driver/features/driver/presentation/support_center_screen.dart';

void main() {
  Widget app(Widget home) => NubeRushDriverApp(home: home);

  Future<void> tapVisible(WidgetTester tester, Key key) async {
    final finder = find.byKey(key);
    if (finder.evaluate().isEmpty) {
      await tester.scrollUntilVisible(
        finder,
        200,
        scrollable: find.byType(Scrollable).first,
      );
    }
    await tester.ensureVisible(finder);
    await tester.pumpAndSettle();
    await tester.tap(finder);
    await tester.pumpAndSettle();
  }

  // --- SafetyToolkitScreen --------------------------------------------- //

  testWidgets('safety toolkit renders all four entries and reminders',
      (tester) async {
    await tester.pumpWidget(app(const SafetyToolkitScreen()));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('safety-toolkit-screen')), findsOneWidget);
    expect(find.byKey(const Key('safety-toolkit-reminders')), findsOneWidget);
    expect(find.byKey(const Key('safety-entry-emergency')), findsOneWidget);
    expect(find.byKey(const Key('safety-entry-support')), findsOneWidget);
    expect(find.byKey(const Key('safety-entry-bug')), findsOneWidget);
    expect(find.byKey(const Key('safety-entry-incident')), findsOneWidget);
  });

  testWidgets('toolkit opens each static screen and returns safely',
      (tester) async {
    await tester.pumpWidget(app(const SafetyToolkitScreen()));
    await tester.pumpAndSettle();

    // Emergency
    await tapVisible(tester, const Key('safety-entry-emergency'));
    expect(find.byKey(const Key('emergency-help-screen')), findsOneWidget);
    await tapVisible(tester, const Key('emergency-help-back'));
    expect(find.byKey(const Key('safety-toolkit-screen')), findsOneWidget);

    // Support
    await tapVisible(tester, const Key('safety-entry-support'));
    expect(find.byKey(const Key('support-center-screen')), findsOneWidget);
    await tapVisible(tester, const Key('support-center-back'));
    expect(find.byKey(const Key('safety-toolkit-screen')), findsOneWidget);

    // Bug
    await tapVisible(tester, const Key('safety-entry-bug'));
    expect(find.byKey(const Key('report-bug-info-screen')), findsOneWidget);
    await tapVisible(tester, const Key('report-bug-back'));
    expect(find.byKey(const Key('safety-toolkit-screen')), findsOneWidget);

    // Incident
    await tapVisible(tester, const Key('safety-entry-incident'));
    expect(find.byKey(const Key('report-incident-info-screen')), findsOneWidget);
    await tapVisible(tester, const Key('report-incident-back'));
    expect(find.byKey(const Key('safety-toolkit-screen')), findsOneWidget);
  });

  // --- EmergencyHelpScreen --------------------------------------------- //

  testWidgets('emergency help renders static guidance only', (tester) async {
    await tester.pumpWidget(app(const EmergencyHelpScreen()));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('emergency-help-screen')), findsOneWidget);
    expect(find.textContaining('personal safety'), findsWidgets);
    // No claim that the app dispatches emergency help.
    expect(find.textContaining('does not dispatch'), findsWidgets);
  });

  // --- SupportCenterScreen --------------------------------------------- //

  testWidgets('support center lists categories and states no live ticketing',
      (tester) async {
    await tester.pumpWidget(app(const SupportCenterScreen()));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('support-center-screen')), findsOneWidget);
    expect(find.text('App issue'), findsOneWidget);
    expect(find.text('Failed delivery / return issue'), findsOneWidget);
    expect(find.textContaining('not implemented'), findsWidgets);
  });

  // --- ReportBugInfoScreen --------------------------------------------- //

  testWidgets('report bug warns against sharing secrets and PII',
      (tester) async {
    await tester.pumpWidget(app(const ReportBugInfoScreen()));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('report-bug-info-screen')), findsOneWidget);
    expect(find.byKey(const Key('report-bug-never-share')), findsOneWidget);
    expect(find.textContaining('Passwords'), findsWidgets);
    expect(find.textContaining('tokens'), findsWidgets);
    expect(find.textContaining('Customer personal information'), findsWidgets);
    expect(find.textContaining('future work'), findsWidgets);
  });

  // --- ReportIncidentInfoScreen ---------------------------------------- //

  testWidgets('report incident renders static guidance, submits nothing',
      (tester) async {
    await tester.pumpWidget(app(const ReportIncidentInfoScreen()));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('report-incident-info-screen')), findsOneWidget);
    expect(find.byKey(const Key('report-incident-guidance')), findsOneWidget);
    expect(find.text('Safety concern'), findsOneWidget);
    expect(find.textContaining('report failed delivery'), findsWidgets);
    expect(find.textContaining('future work'), findsWidgets);
  });

  // --- Safety / boundary ----------------------------------------------- //

  testWidgets('no token / secret / raw config is displayed on any screen',
      (tester) async {
    for (final screen in <Widget>[
      const SafetyToolkitScreen(),
      const EmergencyHelpScreen(),
      const SupportCenterScreen(),
      const ReportBugInfoScreen(),
      const ReportIncidentInfoScreen(),
    ]) {
      await tester.pumpWidget(app(screen));
      await tester.pumpAndSettle();
      expect(find.textContaining('Bearer '), findsNothing);
      expect(find.textContaining('access_token'), findsNothing);
      expect(find.textContaining('refresh_token'), findsNothing);
      expect(find.textContaining('SUPABASE'), findsNothing);
      expect(find.textContaining('anon key'), findsNothing);
    }
  });
}
