import { Suspense, lazy } from "preact/compat";
import { useEffect } from "preact/hooks";
import { AppShell } from "../components/AppShell";
import { useI18n } from "../lib/i18n";
import { bootstrapRoute, currentRoute } from "../lib/routes";

const ComparePage = lazy(() =>
  import("../pages/ComparePage").then((module) => ({ default: module.ComparePage })),
);
const CreateTaskPage = lazy(() =>
  import("../pages/CreateTaskPage").then((module) => ({ default: module.CreateTaskPage })),
);
const NotificationSettingsPage = lazy(() =>
  import("../pages/NotificationSettingsPage").then((module) => ({
    default: module.NotificationSettingsPage,
  })),
);
const TaskDetailPage = lazy(() =>
  import("../pages/TaskDetailPage").then((module) => ({ default: module.TaskDetailPage })),
);
const TaskListPage = lazy(() =>
  import("../pages/TaskListPage").then((module) => ({ default: module.TaskListPage })),
);
const WatchGroupDetailPage = lazy(() =>
  import("../pages/WatchGroupDetailPage").then((module) => ({
    default: module.WatchGroupDetailPage,
  })),
);

function RouteView() {
  switch (currentRoute.value) {
    case "compare":
      return <ComparePage />;
    case "watch-new":
      return <CreateTaskPage />;
    case "watch-detail":
      return <TaskDetailPage />;
    case "watch-group-detail":
      return <WatchGroupDetailPage />;
    case "settings":
      return <NotificationSettingsPage />;
    case "watch-list":
    default:
      return <TaskListPage />;
  }
}

function RouteLoadingFallback() {
  const { t } = useI18n();
  return <div aria-live="polite" class="alert alert-info">{t("common.loadingRoute")}</div>;
}

export function App() {
  useEffect(() => {
    bootstrapRoute();
    const onHashChange = () => bootstrapRoute();
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  return (
    <AppShell>
      <Suspense fallback={<RouteLoadingFallback />}>
        <RouteView />
      </Suspense>
    </AppShell>
  );
}
