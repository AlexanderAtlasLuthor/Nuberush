// NubeRush Driver — branded scaffold (Dr.1.4.B).
//
// Thin wrapper over [Scaffold] that applies the NubeRush background and wraps
// the body in a SafeArea. Pure presentation: no auth, no backend. Reusable by
// driver screens and the future LoginScreen.

import 'package:flutter/material.dart';

import '../theme/nuberush_colors.dart';

class NubeRushScaffold extends StatelessWidget {
  const NubeRushScaffold({
    super.key,
    required this.body,
    this.appBar,
    this.safeArea = true,
    this.padding,
  });

  final Widget body;
  final PreferredSizeWidget? appBar;
  final bool safeArea;
  final EdgeInsetsGeometry? padding;

  @override
  Widget build(BuildContext context) {
    Widget content = body;
    if (padding != null) {
      content = Padding(padding: padding!, child: content);
    }
    if (safeArea) {
      content = SafeArea(child: content);
    }
    return Scaffold(
      backgroundColor: NubeRushColors.background,
      appBar: appBar,
      body: content,
    );
  }
}
