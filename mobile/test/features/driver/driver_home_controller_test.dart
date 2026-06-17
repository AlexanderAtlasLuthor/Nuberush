// Dr.1.3.E — DriverHomeController state-mapping tests. Fake repo, no network.

import 'package:flutter_test/flutter_test.dart';
import 'package:nuberush_driver/core/api/api_error.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_home_controller.dart';
import 'package:nuberush_driver/features/driver/presentation/driver_home_state.dart';

import 'fake_driver_repository.dart';

void main() {
  test('initial state before load', () {
    final controller = DriverHomeController(FakeDriverRepository());
    expect(controller.state.status, DriverHomeStatus.initial);
  });

  test('emits loading then loaded with profile + eligibility', () async {
    final controller = DriverHomeController(FakeDriverRepository());
    final seen = <DriverHomeStatus>[];
    controller.addListener(() => seen.add(controller.state.status));
    await controller.load();
    expect(seen.first, DriverHomeStatus.loading);
    expect(controller.state.status, DriverHomeStatus.loaded);
    expect(controller.state.profile, isNotNull);
    expect(controller.state.eligibility, isNotNull);
  });

  test('profile error -> error state with message', () async {
    final controller = DriverHomeController(
      FakeDriverRepository(
        profileError: const ApiError(status: 403, message: 'Forbidden'),
      ),
    );
    await controller.load();
    expect(controller.state.status, DriverHomeStatus.error);
    expect(controller.state.errorMessage, 'Forbidden');
  });

  test('eligibility error -> error state', () async {
    final controller = DriverHomeController(
      FakeDriverRepository(
        eligibilityError: const ApiError(status: 500, message: 'Server error'),
      ),
    );
    await controller.load();
    expect(controller.state.status, DriverHomeStatus.error);
  });

  test('network ApiError (status 0) -> offline state', () async {
    final controller = DriverHomeController(
      FakeDriverRepository(profileError: ApiError.network()),
    );
    await controller.load();
    expect(controller.state.status, DriverHomeStatus.offline);
  });

  test('401 -> unauthenticated state', () async {
    final controller = DriverHomeController(
      FakeDriverRepository(
        profileError: const ApiError(status: 401, message: 'Not authenticated'),
      ),
    );
    await controller.load();
    expect(controller.state.status, DriverHomeStatus.unauthenticated);
  });

  test('retry reloads and can recover from offline to loaded', () async {
    final repo = FakeDriverRepository(profileError: ApiError.network());
    final controller = DriverHomeController(repo);
    await controller.load();
    expect(controller.state.status, DriverHomeStatus.offline);

    // Backend recovers; retry succeeds.
    repo.profileError = null;
    await controller.retry();
    expect(controller.state.status, DriverHomeStatus.loaded);
    expect(repo.profileCalls, 2);
  });
}
