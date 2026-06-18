// NubeRush Driver — email/password login screen (Dr.1.4.D).
//
// NubeRush-branded sign-in built from the Dr.1.4.B primitives. It drives an
// injected [AuthController] and calls back via [onSignedIn] on success. This is
// NOT an AuthGate and is NOT wired as the root surface yet (Dr.1.4.E). It makes
// no backend/driver call, renders no raw error, and shows no env values.

import 'package:flutter/material.dart';

import '../../../core/auth/auth_controller.dart';
import '../../../core/theme/nuberush_spacing.dart';
import '../../../core/ui/ui.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key, required this.controller, this.onSignedIn});

  final AuthController controller;

  /// Called after a successful sign-in. Root routing is wired in Dr.1.4.E.
  final VoidCallback? onSignedIn;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final TextEditingController _email = TextEditingController();
  final TextEditingController _password = TextEditingController();

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final ok = await widget.controller.signInWithPassword(
      email: _email.text,
      password: _password.text,
    );
    if (!mounted) return;
    if (ok) widget.onSignedIn?.call();
  }

  @override
  Widget build(BuildContext context) {
    return NubeRushScaffold(
      padding: const EdgeInsets.all(NubeRushSpacing.xl),
      body: Center(
        child: SingleChildScrollView(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 420),
            child: ListenableBuilder(
              listenable: widget.controller,
              builder: (context, _) {
                final state = widget.controller.state;
                final submitting = state.isSubmitting;
                return Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Center(child: NubeRushBrandHeader()),
                    const SizedBox(height: NubeRushSpacing.xl),
                    NubeRushCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: [
                          Text(
                            'Sign in to drive',
                            style: Theme.of(context).textTheme.titleLarge,
                          ),
                          const SizedBox(height: NubeRushSpacing.lg),
                          NubeRushTextField(
                            key: const Key('login-email'),
                            controller: _email,
                            label: 'Email',
                            hint: 'you@example.com',
                            keyboardType: TextInputType.emailAddress,
                            textInputAction: TextInputAction.next,
                            enabled: !submitting,
                          ),
                          const SizedBox(height: NubeRushSpacing.md),
                          NubeRushTextField(
                            key: const Key('login-password'),
                            controller: _password,
                            label: 'Password',
                            obscureText: true,
                            textInputAction: TextInputAction.done,
                            enabled: !submitting,
                            onSubmitted: (_) => submitting ? null : _submit(),
                          ),
                          if (state.hasError) ...[
                            const SizedBox(height: NubeRushSpacing.lg),
                            NubeRushInlineError(
                              message: state.errorMessage ??
                                  'Could not sign in. Please try again.',
                            ),
                          ],
                          const SizedBox(height: NubeRushSpacing.xl),
                          NubeRushPrimaryButton(
                            key: const Key('login-submit'),
                            label: 'Sign in',
                            isLoading: submitting,
                            onPressed: submitting ? null : _submit,
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: NubeRushSpacing.lg),
                    Text(
                      'Use the email and password for your NubeRush driver '
                      'account.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ],
                );
              },
            ),
          ),
        ),
      ),
    );
  }
}
