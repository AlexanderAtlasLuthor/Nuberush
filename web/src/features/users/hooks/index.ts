// F2.9.2 + F2.15.4: barrel for users hooks.
//
// Feature pages should import from `@/features/users/hooks` rather
// than reaching into individual files; that keeps the public surface
// in one place and lets internals change without ripple edits.

export { usersQueryKeys } from "./queryKeys";

// Queries
export { useUsersQuery } from "./useUsersQuery";
export { useUserQuery } from "./useUserQuery";

// Mutations
export { useCreateUserMutation } from "./useCreateUserMutation";
export { useUpdateUserMutation } from "./useUpdateUserMutation";
export { useDeactivateUserMutation } from "./useDeactivateUserMutation";
export { useReactivateUserMutation } from "./useReactivateUserMutation";
export { useChangeUserRoleMutation } from "./useChangeUserRoleMutation";
export { useAssignUserStoreMutation } from "./useAssignUserStoreMutation";
export { useAdminSetPasswordMutation } from "./useAdminSetPasswordMutation";
