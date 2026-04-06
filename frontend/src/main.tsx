import type { ComponentChildren, FunctionComponent } from "preact";
import { render } from "preact";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nProvider } from "./lib/i18n";
import { App } from "./ui/App";
import "./styles.css";

const queryClient = new QueryClient();
const QueryProvider = QueryClientProvider as unknown as FunctionComponent<{
  client: QueryClient;
  children?: ComponentChildren;
}>;

render(
  <QueryProvider client={queryClient}>
    <I18nProvider>
      <App />
    </I18nProvider>
  </QueryProvider>,
  document.getElementById("app")!,
);
