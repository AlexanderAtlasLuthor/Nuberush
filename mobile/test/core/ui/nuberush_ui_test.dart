// NubeRush Driver — core UI primitive tests (Dr.1.4.B).

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/theme/nuberush_theme.dart';
import 'package:nuberush_driver/core/ui/ui.dart';

/// Wraps a primitive in the real app theme so it renders as in production.
Widget _host(Widget child) {
  return MaterialApp(
    theme: NubeRushTheme.dark(),
    home: Scaffold(body: Center(child: child)),
  );
}

void main() {
  testWidgets('NubeRushCard renders its child', (tester) async {
    await tester.pumpWidget(_host(const NubeRushCard(child: Text('card body'))));
    expect(find.text('card body'), findsOneWidget);
  });

  testWidgets('NubeRushPrimaryButton renders enabled label and fires onPressed',
      (tester) async {
    var tapped = false;
    await tester.pumpWidget(_host(NubeRushPrimaryButton(
      label: 'Sign in',
      onPressed: () => tapped = true,
    )));
    expect(find.text('Sign in'), findsOneWidget);
    await tester.tap(find.byType(NubeRushPrimaryButton));
    expect(tapped, isTrue);
  });

  testWidgets('NubeRushPrimaryButton is disabled when onPressed is null',
      (tester) async {
    await tester.pumpWidget(_host(
      const NubeRushPrimaryButton(label: 'Disabled', onPressed: null),
    ));
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
  });

  testWidgets('NubeRushPrimaryButton shows a spinner and disables when loading',
      (tester) async {
    var tapped = false;
    await tester.pumpWidget(_host(NubeRushPrimaryButton(
      label: 'Loading',
      isLoading: true,
      onPressed: () => tapped = true,
    )));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Loading'), findsNothing);
    final button = tester.widget<FilledButton>(find.byType(FilledButton));
    expect(button.onPressed, isNull);
    expect(tapped, isFalse);
  });

  testWidgets('NubeRushSecondaryButton renders its label', (tester) async {
    await tester.pumpWidget(_host(
      NubeRushSecondaryButton(label: 'Cancel', onPressed: () {}),
    ));
    expect(find.text('Cancel'), findsOneWidget);
    expect(find.byType(OutlinedButton), findsOneWidget);
  });

  testWidgets('NubeRushTextField renders label and error', (tester) async {
    await tester.pumpWidget(_host(const NubeRushTextField(
      label: 'Email',
      errorText: 'Required',
    )));
    expect(find.text('Email'), findsOneWidget);
    expect(find.text('Required'), findsOneWidget);
  });

  testWidgets('NubeRushInlineError renders the safe message', (tester) async {
    await tester.pumpWidget(_host(
      const NubeRushInlineError(message: 'Could not sign in.'),
    ));
    expect(find.text('Could not sign in.'), findsOneWidget);
    expect(find.byIcon(Icons.error_outline), findsOneWidget);
  });

  testWidgets('NubeRushLoadingState renders spinner and optional message',
      (tester) async {
    await tester.pumpWidget(_host(
      const NubeRushLoadingState(message: 'Loading…'),
    ));
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    expect(find.text('Loading…'), findsOneWidget);
  });

  testWidgets('NubeRushBrandHeader renders the NubeRush Driver wordmark',
      (tester) async {
    await tester.pumpWidget(_host(const NubeRushBrandHeader()));
    expect(find.text('NubeRush'), findsOneWidget);
    expect(find.text('Driver'), findsOneWidget);
    expect(find.byIcon(Icons.local_fire_department), findsOneWidget);
  });

  testWidgets('NubeRushScaffold renders its body', (tester) async {
    await tester.pumpWidget(MaterialApp(
      theme: NubeRushTheme.dark(),
      home: const NubeRushScaffold(body: Text('scaffold body')),
    ));
    expect(find.text('scaffold body'), findsOneWidget);
  });
}
