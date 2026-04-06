import { signal } from "@preact/signals";
import type { WatchTaskDraft } from "../types";

export type AppRoute =
  | "compare"
  | "watch-new"
  | "watch-list"
  | "watch-detail"
  | "watch-group-detail"
  | "settings";

const WATCH_TASK_DRAFT_STORAGE_KEY = "dealwatch.watchTaskDraft";

function isWatchTaskDraft(value: unknown): value is WatchTaskDraft {
  if (!value || typeof value !== "object") {
    return false;
  }
  const draft = value as Record<string, unknown>;
  return (
    typeof draft.submittedUrl === "string" &&
    typeof draft.normalizedUrl === "string" &&
    typeof draft.title === "string" &&
    typeof draft.storeKey === "string" &&
    typeof draft.candidateKey === "string" &&
    (typeof draft.brandHint === "undefined" || typeof draft.brandHint === "string") &&
    (typeof draft.sizeHint === "undefined" || typeof draft.sizeHint === "string") &&
    typeof draft.defaultRecipientEmail === "string" &&
    typeof draft.zipCode === "string"
  );
}

function loadWatchTaskDraft(): WatchTaskDraft | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(WATCH_TASK_DRAFT_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed: unknown = JSON.parse(raw);
    return isWatchTaskDraft(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function persistWatchTaskDraft(draft: WatchTaskDraft | null): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    if (draft === null) {
      window.sessionStorage.removeItem(WATCH_TASK_DRAFT_STORAGE_KEY);
      return;
    }
    window.sessionStorage.setItem(WATCH_TASK_DRAFT_STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // Fail open: keep in-memory draft state even if sessionStorage is unavailable.
  }
}

function buildHash(route: AppRoute): string {
  if (route === "watch-detail" && currentTaskId.value) {
    return `#${route}/${currentTaskId.value}`;
  }
  if (route === "watch-group-detail" && currentGroupId.value) {
    return `#${route}/${currentGroupId.value}`;
  }
  return `#${route}`;
}

export const currentRoute = signal<AppRoute>("watch-list");
export const currentTaskId = signal<string>("");
export const currentGroupId = signal<string>("");
export const pendingWatchTaskDraft = signal<WatchTaskDraft | null>(loadWatchTaskDraft());

export function navigate(route: AppRoute, entityId?: string): void {
  if (route === "watch-detail") {
    if (entityId) {
      currentTaskId.value = entityId;
    }
    if (!currentTaskId.value) {
      currentRoute.value = "watch-list";
      window.location.hash = "#watch-list";
      return;
    }
  }

  if (route === "watch-group-detail") {
    if (entityId) {
      currentGroupId.value = entityId;
    }
    if (!currentGroupId.value) {
      currentRoute.value = "watch-list";
      window.location.hash = "#watch-list";
      return;
    }
  }

  currentRoute.value = route;
  window.location.hash = buildHash(route);
}

export function setWatchTaskDraft(draft: WatchTaskDraft): void {
  pendingWatchTaskDraft.value = draft;
  persistWatchTaskDraft(draft);
}

export function clearWatchTaskDraft(): void {
  pendingWatchTaskDraft.value = null;
  persistWatchTaskDraft(null);
}

export function bootstrapRoute(): void {
  pendingWatchTaskDraft.value = loadWatchTaskDraft();
  const raw = window.location.hash.replace(/^#/, "");
  if (!raw) {
    navigate("compare");
    return;
  }

  const [route, entityId] = raw.split("/");
  if (route === "compare" || route === "watch-new" || route === "watch-list" || route === "settings") {
    currentRoute.value = route;
    return;
  }
  if (route === "watch-detail" && entityId) {
    currentTaskId.value = entityId;
    currentRoute.value = "watch-detail";
    return;
  }
  if (route === "watch-group-detail" && entityId) {
    currentGroupId.value = entityId;
    currentRoute.value = "watch-group-detail";
    return;
  }
  navigate("compare");
}
