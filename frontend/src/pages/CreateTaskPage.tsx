import { useEffect, useState } from "preact/hooks";
import { z } from "zod";
import { useCreateWatchTask } from "../lib/hooks";
import { ApiError } from "../lib/api";
import { interpolate, type AppLocale, useI18n } from "../lib/i18n";
import { clearWatchTaskDraft, navigate, pendingWatchTaskDraft } from "../lib/routes";

const createSchema = z.object({
  submittedUrl: z.string().url("Please enter a valid product URL."),
  zipCode: z.string().min(3, "ZIP code is required."),
  cadenceMinutes: z.coerce.number().min(30).max(10080),
  thresholdType: z.enum(["price_below", "price_drop_percent", "effective_price_below"]),
  thresholdValue: z.coerce.number().positive(),
  cooldownMinutes: z.coerce.number().min(0).max(10080),
  recipientEmail: z.string().email("Recipient email is required."),
});

type FormState = z.infer<typeof createSchema>;
type DraftMessage = { en: string; "zh-CN"?: string };

const CREATE_TASK_COPY = {
  eyebrow: { en: "Create watch task", },
  title: { en: "Turn a product URL into a long-lived task", },
  summary: {
    en: "Think of this form as the intake desk for the product pipeline: the URL is registered first, then monitoring cadence, history, and notifications can accumulate around it.",
  },
  draftLoadedPrefix: { en: "Loaded compare preview context for", },
  draftLoadedSuffix: { en: "Review the threshold and create the task when it looks right.", },
  compareHandoff: { en: "Compare handoff", },
  normalizedUrl: { en: "Normalized URL", },
  candidateKey: { en: "Candidate key", },
  submittedUrl: { en: "Submitted URL", },
  zipCode: { en: "ZIP Code", },
  cadenceMinutes: { en: "Cadence (minutes)", },
  thresholdType: { en: "Threshold Type", },
  thresholdValue: { en: "Threshold Value", },
  cooldownMinutes: { en: "Cooldown (minutes)", },
  recipientEmail: { en: "Recipient Email", },
  thresholdTypeOptions: {
    priceBelow: { en: "Price below", },
    priceDropPercent: { en: "Price drop percent", },
    effectivePriceBelow: { en: "Effective price below", },
  },
  creating: { en: "Creating task...", },
  submit: { en: "Create Watch Task", },
  backToCompare: { en: "Back to compare result", },
  cancel: { en: "Cancel", },
  apiEyebrow: { en: "API mapping", },
  apiTitle: { en: "Why this shape matters", },
  apiSummaryLead: { en: "This page is not a decorative form. It maps directly to the live", },
  apiSummaryTail: { en: "request payload.", },
  apiSummaryBody: {
    en: "In other words, the frontend is already wired to the active API instead of hiding behind placeholder data.",
  },
  existsLabel: { en: "Why this page exists", },
  existsTitle: { en: "One intake desk, not six scattered forms", },
  existsSummary: {
    en: "The operator only needs one clear decision here: is this URL worth turning into a durable watch lane?",
  },
  progressiveLabel: { en: "Progressive disclosure", },
  progressiveTitle: { en: "Only surface detail when it changes the decision", },
  progressiveSummary: {
    en: "Compare context appears only when it exists, so the page stays lightweight for a direct single-task intake but still supports handoff from Compare Preview.",
  },
} as const;

function resolvePageCopy(
  t: (key: string) => string,
  locale: AppLocale,
  key: string,
  fallback: DraftMessage,
  values?: Record<string, string | number>,
): string {
  const translated = t(key);
  const template = translated === key ? fallback[locale] ?? fallback.en : translated;
  return values ? interpolate(template, values) : template;
}

const defaultForm: FormState = {
  submittedUrl: "https://www.sayweee.com/product/example/12345",
  zipCode: "98101",
  cadenceMinutes: 360,
  thresholdType: "effective_price_below",
  thresholdValue: 6.5,
  cooldownMinutes: 240,
  recipientEmail: "owner@example.com",
};

function buildFormFromDraft() {
  const draft = pendingWatchTaskDraft.value;
  if (!draft) {
    return defaultForm;
  }
  return {
    ...defaultForm,
    submittedUrl: draft.normalizedUrl || draft.submittedUrl,
    zipCode: draft.zipCode,
    recipientEmail: draft.defaultRecipientEmail || defaultForm.recipientEmail,
  };
}

export function CreateTaskPage() {
  const { locale, t } = useI18n();
  const mutation = useCreateWatchTask();
  const [form, setForm] = useState<FormState>(buildFormFromDraft);
  const [error, setError] = useState<string>("");
  const draft = pendingWatchTaskDraft.value;
  const createText = (
    key: string,
    fallback: DraftMessage,
    values?: Record<string, string | number>,
  ) => resolvePageCopy(t, locale, key, fallback, values);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  useEffect(() => {
    if (!draft) {
      return;
    }
    setForm((current) => ({
      ...current,
      submittedUrl: draft.normalizedUrl || draft.submittedUrl,
      zipCode: draft.zipCode,
      recipientEmail: draft.defaultRecipientEmail || current.recipientEmail,
    }));
  }, [draft]);

  async function onSubmit(event: Event) {
    event.preventDefault();
    const parsed = createSchema.safeParse(form);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Invalid form input.");
      return;
    }
    setError("");
    try {
      const task = await mutation.mutateAsync({
        ...parsed.data,
        compareHandoff: draft
          ? {
              titleSnapshot: draft.title,
              storeKey: draft.storeKey,
              candidateKey: draft.candidateKey,
              brandHint: draft.brandHint,
              sizeHint: draft.sizeHint,
            }
          : undefined,
      });
      clearWatchTaskDraft();
      navigate("watch-detail", task.id);
    } catch (mutationError) {
      if (mutationError instanceof ApiError) {
        if (mutationError.status === 400) {
          setError(
            mutationError.message === "unsupported_store_host"
              ? "This store is not in the official registry yet. Keep it in compare review first, or submit a URL from an officially supported store."
              : mutationError.message === "unsupported_store_path"
                ? "This store is recognized, but this URL is not an officially supported product-detail path yet."
                : mutationError.message,
          );
          return;
        }
        if (mutationError.status === 404) {
          setError("The product endpoint could not be found. Please refresh and try again.");
          return;
        }
      }
      setError("Failed to create the watch task. Please try again.");
    }
  }

  return (
    <section class="page-hero-grid">
      <form
        class="surface-panel surface-panel-primary surface-panel-block"
        onSubmit={onSubmit}
      >
        <p class="eyebrow-label">{createText("createTaskPage.eyebrow", CREATE_TASK_COPY.eyebrow)}</p>
        <h2 class="mt-2 text-2xl font-semibold text-ink">{createText("createTaskPage.title", CREATE_TASK_COPY.title)}</h2>
        <p class="supporting-copy">{createText("createTaskPage.summary", CREATE_TASK_COPY.summary)}</p>

        {draft ? (
          <div class="alert alert-info mt-5">
            {createText("createTaskPage.draftLoadedPrefix", CREATE_TASK_COPY.draftLoadedPrefix)}{" "}
            <strong>{draft.title}</strong> {draft.storeKey}.{" "}
            {createText("createTaskPage.draftLoadedSuffix", CREATE_TASK_COPY.draftLoadedSuffix)}
          </div>
        ) : null}

        {draft ? (
          <div class="mt-5 rounded-2xl border border-base-300 bg-base-200/60 p-4 text-sm text-slate-600">
            <div class="workflow-label">
              {createText("createTaskPage.compareHandoff", CREATE_TASK_COPY.compareHandoff)}
            </div>
            <div class="mt-3 grid gap-2 md:grid-cols-2">
              <div>
                <div class="font-semibold text-ink">{createText("createTaskPage.normalizedUrl", CREATE_TASK_COPY.normalizedUrl)}</div>
                <p class="mt-1 break-words font-mono text-xs leading-6">{draft.normalizedUrl}</p>
              </div>
              <div>
                <div class="font-semibold text-ink">{createText("createTaskPage.candidateKey", CREATE_TASK_COPY.candidateKey)}</div>
                <p class="mt-1 break-words font-mono text-xs leading-6">{draft.candidateKey}</p>
              </div>
            </div>
          </div>
        ) : null}

        <div class="mt-6 grid gap-4 md:grid-cols-2">
          <label class="form-control md:col-span-2">
            <span class="label-text font-medium">{createText("createTaskPage.submittedUrl", CREATE_TASK_COPY.submittedUrl)}</span>
            <input
              autocomplete="url"
              class="input input-bordered"
              name="submittedUrl"
              onInput={(event) =>
                update("submittedUrl", (event.currentTarget as HTMLInputElement).value)
              }
              spellcheck={false}
              type="url"
              value={form.submittedUrl}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">{createText("createTaskPage.zipCode", CREATE_TASK_COPY.zipCode)}</span>
            <input
              autocomplete="postal-code"
              class="input input-bordered"
              inputMode="numeric"
              name="zipCode"
              onInput={(event) => update("zipCode", (event.currentTarget as HTMLInputElement).value)}
              spellcheck={false}
              value={form.zipCode}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">{createText("createTaskPage.cadenceMinutes", CREATE_TASK_COPY.cadenceMinutes)}</span>
            <input
              class="input input-bordered"
              min="30"
              name="cadenceMinutes"
              onInput={(event) =>
                update("cadenceMinutes", Number((event.currentTarget as HTMLInputElement).value))
              }
              type="number"
              value={form.cadenceMinutes}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">{createText("createTaskPage.thresholdType", CREATE_TASK_COPY.thresholdType)}</span>
            <select
              class="select select-bordered"
              name="thresholdType"
              onInput={(event) =>
                update("thresholdType", (event.currentTarget as HTMLSelectElement).value as FormState["thresholdType"])
              }
              value={form.thresholdType}
            >
              <option value="price_below">{createText("createTaskPage.thresholdTypeOptions.priceBelow", CREATE_TASK_COPY.thresholdTypeOptions.priceBelow)}</option>
              <option value="price_drop_percent">{createText("createTaskPage.thresholdTypeOptions.priceDropPercent", CREATE_TASK_COPY.thresholdTypeOptions.priceDropPercent)}</option>
              <option value="effective_price_below">{createText("createTaskPage.thresholdTypeOptions.effectivePriceBelow", CREATE_TASK_COPY.thresholdTypeOptions.effectivePriceBelow)}</option>
            </select>
          </label>

          <label class="form-control">
            <span class="label-text font-medium">{createText("createTaskPage.thresholdValue", CREATE_TASK_COPY.thresholdValue)}</span>
            <input
              class="input input-bordered"
              min="0.01"
              name="thresholdValue"
              onInput={(event) =>
                update("thresholdValue", Number((event.currentTarget as HTMLInputElement).value))
              }
              step="0.01"
              type="number"
              value={form.thresholdValue}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">{createText("createTaskPage.cooldownMinutes", CREATE_TASK_COPY.cooldownMinutes)}</span>
            <input
              class="input input-bordered"
              min="0"
              name="cooldownMinutes"
              onInput={(event) =>
                update("cooldownMinutes", Number((event.currentTarget as HTMLInputElement).value))
              }
              type="number"
              value={form.cooldownMinutes}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">{createText("createTaskPage.recipientEmail", CREATE_TASK_COPY.recipientEmail)}</span>
            <input
              autocomplete="email"
              class="input input-bordered"
              name="recipientEmail"
              onInput={(event) =>
                update("recipientEmail", (event.currentTarget as HTMLInputElement).value)
              }
              spellcheck={false}
              type="email"
              value={form.recipientEmail}
            />
          </label>
        </div>

        {error ? <div aria-live="polite" class="alert alert-error mt-5">{error}</div> : null}
        {mutation.isPending ? <div aria-live="polite" class="alert alert-info mt-5">{createText("createTaskPage.creating", CREATE_TASK_COPY.creating)}</div> : null}

        <div class="mt-6 flex flex-wrap gap-3">
          <button class="btn btn-primary w-full sm:w-auto" type="submit">
            {createText("createTaskPage.submit", CREATE_TASK_COPY.submit)}
          </button>
          {draft ? (
            <button
              class="btn btn-ghost"
              onClick={() => navigate("compare")}
              type="button"
            >
              {createText("createTaskPage.backToCompare", CREATE_TASK_COPY.backToCompare)}
            </button>
          ) : (
            <button
              class="btn btn-ghost"
              onClick={() => {
                clearWatchTaskDraft();
                navigate("watch-list");
              }}
              type="button"
            >
              {createText("createTaskPage.cancel", CREATE_TASK_COPY.cancel)}
            </button>
          )}
        </div>
      </form>

      <aside class="surface-panel surface-panel-block">
        <p class="eyebrow-label">{createText("createTaskPage.apiEyebrow", CREATE_TASK_COPY.apiEyebrow)}</p>
        <h3 class="mt-2 text-xl font-semibold text-ink">{createText("createTaskPage.apiTitle", CREATE_TASK_COPY.apiTitle)}</h3>
        <div class="mt-4 space-y-4 text-sm leading-6 text-slate-600">
          <p>
            {createText("createTaskPage.apiSummaryLead", CREATE_TASK_COPY.apiSummaryLead)}{" "}
            <code class="mx-1 rounded bg-base-200 px-1 py-0.5" translate={false}>POST /api/watch-tasks</code>
            {createText("createTaskPage.apiSummaryTail", CREATE_TASK_COPY.apiSummaryTail)}
          </p>
          <p>
            {createText("createTaskPage.apiSummaryBody", CREATE_TASK_COPY.apiSummaryBody)}
          </p>
        </div>

        <div class="metric-grid mt-6">
          <div class="metric-card">
            <div class="workflow-label">{createText("createTaskPage.existsLabel", CREATE_TASK_COPY.existsLabel)}</div>
            <div class="panel-title">{createText("createTaskPage.existsTitle", CREATE_TASK_COPY.existsTitle)}</div>
            <p class="panel-copy">{createText("createTaskPage.existsSummary", CREATE_TASK_COPY.existsSummary)}</p>
          </div>
          <div class="metric-card">
            <div class="workflow-label">{createText("createTaskPage.progressiveLabel", CREATE_TASK_COPY.progressiveLabel)}</div>
            <div class="panel-title">{createText("createTaskPage.progressiveTitle", CREATE_TASK_COPY.progressiveTitle)}</div>
            <p class="panel-copy">{createText("createTaskPage.progressiveSummary", CREATE_TASK_COPY.progressiveSummary)}</p>
          </div>
        </div>
      </aside>
    </section>
  );
}
