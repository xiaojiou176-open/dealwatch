import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  CompareEvidencePackageArtifact,
  CreateCompareEvidencePackageInput,
  ComparePreviewInput,
  CreateWatchGroupInput,
  CreateWatchTaskInput,
  NotificationEvent,
  NotificationSettings,
  RecoveryInbox,
  RuntimeReadiness,
  StoreBindingSetting,
  StoreOnboardingCockpit,
  UpdateWatchGroupInput,
  UpdateWatchTaskInput,
} from "../types";
import { apiClient } from "./api";

export function useWatchTasks() {
  return useQuery({
    queryKey: ["watch-tasks"],
    queryFn: () => apiClient.listWatchTasks(),
  });
}

export function useWatchTaskDetail(taskId: string) {
  return useQuery({
    queryKey: ["watch-task", taskId],
    queryFn: () => apiClient.getWatchTaskDetail(taskId),
    enabled: Boolean(taskId),
  });
}

export function useCreateWatchTask() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateWatchTaskInput) => apiClient.createWatchTask(input),
    onSuccess: async (task) => {
      await client.invalidateQueries({ queryKey: ["watch-tasks"] });
      await client.invalidateQueries({ queryKey: ["watch-task", task.id] });
    },
  });
}

export function useUpdateWatchTask(taskId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateWatchTaskInput) => apiClient.updateWatchTask(taskId, input),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["watch-tasks"] });
      await client.invalidateQueries({ queryKey: ["watch-task", taskId] });
      await client.invalidateQueries({ queryKey: ["recovery-inbox"] });
    },
  });
}

export function useRunWatchTask() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (taskId: string) => apiClient.runWatchTask(taskId),
    onSuccess: async (run, taskId) => {
      await client.invalidateQueries({ queryKey: ["watch-tasks"] });
      await client.invalidateQueries({ queryKey: ["watch-task", taskId] });
      await client.invalidateQueries({ queryKey: ["run", run.id] });
      await client.invalidateQueries({ queryKey: ["notifications"] });
      await client.invalidateQueries({ queryKey: ["recovery-inbox"] });
    },
  });
}

export function useWatchGroups() {
  return useQuery({
    queryKey: ["watch-groups"],
    queryFn: () => apiClient.listWatchGroups(),
  });
}

export function useRecoveryInbox() {
  return useQuery<RecoveryInbox>({
    queryKey: ["recovery-inbox"],
    queryFn: () => apiClient.getRecoveryInbox(),
  });
}

export function useWatchGroupDetail(groupId: string) {
  return useQuery({
    queryKey: ["watch-group", groupId],
    queryFn: () => apiClient.getWatchGroupDetail(groupId),
    enabled: Boolean(groupId),
  });
}

export function useCreateWatchGroup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: CreateWatchGroupInput) => apiClient.createWatchGroup(input),
    onSuccess: async (group) => {
      await client.invalidateQueries({ queryKey: ["watch-groups"] });
      await client.invalidateQueries({ queryKey: ["watch-group", group.id] });
    },
  });
}

export function useUpdateWatchGroup(groupId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (input: UpdateWatchGroupInput) => apiClient.updateWatchGroup(groupId, input),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["watch-groups"] });
      await client.invalidateQueries({ queryKey: ["watch-group", groupId] });
      await client.invalidateQueries({ queryKey: ["recovery-inbox"] });
    },
  });
}

export function useRunWatchGroup() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => apiClient.runWatchGroup(groupId),
    onSuccess: async (run, groupId) => {
      await client.invalidateQueries({ queryKey: ["watch-groups"] });
      await client.invalidateQueries({ queryKey: ["watch-group", groupId] });
      await client.invalidateQueries({ queryKey: ["run", run.id] });
      await client.invalidateQueries({ queryKey: ["notifications"] });
      await client.invalidateQueries({ queryKey: ["recovery-inbox"] });
    },
  });
}

export function useNotificationSettings() {
  return useQuery({
    queryKey: ["notification-settings"],
    queryFn: () => apiClient.getNotificationSettings(),
  });
}

export function useRuntimeReadiness() {
  return useQuery<RuntimeReadiness>({
    queryKey: ["runtime-readiness"],
    queryFn: () => apiClient.getRuntimeReadiness(),
  });
}

export function useNotificationEvents() {
  return useQuery<NotificationEvent[]>({
    queryKey: ["notifications"],
    queryFn: () => apiClient.listNotificationEvents(),
  });
}

export function useStoreBindings() {
  return useQuery<StoreBindingSetting[]>({
    queryKey: ["store-bindings"],
    queryFn: () => apiClient.listStoreBindings(),
  });
}

export function useStoreOnboardingCockpit() {
  return useQuery<StoreOnboardingCockpit>({
    queryKey: ["store-onboarding-cockpit"],
    queryFn: () => apiClient.getStoreOnboardingCockpit(),
  });
}

export function useUpdateStoreBinding() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ storeKey, enabled }: { storeKey: string; enabled: boolean }) =>
      apiClient.updateStoreBinding(storeKey, enabled),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["store-bindings"] });
      await client.invalidateQueries({ queryKey: ["store-onboarding-cockpit"] });
      await client.invalidateQueries({ queryKey: ["watch-groups"] });
      await client.invalidateQueries({ queryKey: ["watch-tasks"] });
      await client.invalidateQueries({ queryKey: ["runtime-readiness"] });
    },
  });
}

export function useUpdateNotificationSettings() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (payload: NotificationSettings) => apiClient.updateNotificationSettings(payload),
    onSuccess: async () => {
      await client.invalidateQueries({ queryKey: ["notification-settings"] });
      await client.invalidateQueries({ queryKey: ["runtime-readiness"] });
    },
  });
}

export function useComparePreview() {
  return useMutation({
    mutationFn: (input: ComparePreviewInput) => apiClient.comparePreview(input),
  });
}

export function useCreateCompareEvidencePackage() {
  return useMutation<CompareEvidencePackageArtifact, Error, CreateCompareEvidencePackageInput>({
    mutationFn: (input) => apiClient.createCompareEvidencePackage(input),
  });
}
