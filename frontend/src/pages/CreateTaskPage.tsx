import { useEffect, useState } from "preact/hooks";
import { z } from "zod";
import { useCreateWatchTask } from "../lib/hooks";
import { ApiError } from "../lib/api";
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
  const mutation = useCreateWatchTask();
  const [form, setForm] = useState<FormState>(buildFormFromDraft);
  const [error, setError] = useState<string>("");
  const draft = pendingWatchTaskDraft.value;

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
    <section class="grid gap-4 xl:grid-cols-[1.15fr,0.85fr]">
      <form
        class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card"
        onSubmit={onSubmit}
      >
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">Create watch task</p>
        <h2 class="mt-2 text-2xl font-semibold text-ink">Turn a product URL into a long-lived task</h2>
        <p class="mt-2 text-sm leading-6 text-slate-600">
          Think of this form as the intake desk for the product pipeline: the URL is registered
          first, then monitoring cadence, history, and notifications can accumulate around it.
        </p>

        {draft ? (
          <div class="alert alert-info mt-5">
            Loaded compare preview context for <strong>{draft.title}</strong> from {draft.storeKey}.
            Review the threshold and create the task when it looks right.
          </div>
        ) : null}

        {draft ? (
          <div class="mt-5 rounded-2xl border border-base-300 bg-base-200/60 p-4 text-sm text-slate-600">
            <div class="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              Compare handoff
            </div>
            <div class="mt-3 grid gap-2 md:grid-cols-2">
              <div>
                <div class="font-semibold text-ink">Normalized URL</div>
                <p class="mt-1 break-words font-mono text-xs leading-6">{draft.normalizedUrl}</p>
              </div>
              <div>
                <div class="font-semibold text-ink">Candidate key</div>
                <p class="mt-1 break-words font-mono text-xs leading-6">{draft.candidateKey}</p>
              </div>
            </div>
          </div>
        ) : null}

        <div class="mt-6 grid gap-4 md:grid-cols-2">
          <label class="form-control md:col-span-2">
            <span class="label-text font-medium">Submitted URL</span>
            <input
              class="input input-bordered"
              onInput={(event) =>
                update("submittedUrl", (event.currentTarget as HTMLInputElement).value)
              }
              type="url"
              value={form.submittedUrl}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">ZIP Code</span>
            <input
              class="input input-bordered"
              onInput={(event) => update("zipCode", (event.currentTarget as HTMLInputElement).value)}
              value={form.zipCode}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">Cadence (minutes)</span>
            <input
              class="input input-bordered"
              min="30"
              onInput={(event) =>
                update("cadenceMinutes", Number((event.currentTarget as HTMLInputElement).value))
              }
              type="number"
              value={form.cadenceMinutes}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">Threshold Type</span>
            <select
              class="select select-bordered"
              onInput={(event) =>
                update("thresholdType", (event.currentTarget as HTMLSelectElement).value as FormState["thresholdType"])
              }
              value={form.thresholdType}
            >
              <option value="price_below">Price below</option>
              <option value="price_drop_percent">Price drop percent</option>
              <option value="effective_price_below">Effective price below</option>
            </select>
          </label>

          <label class="form-control">
            <span class="label-text font-medium">Threshold Value</span>
            <input
              class="input input-bordered"
              min="0.01"
              onInput={(event) =>
                update("thresholdValue", Number((event.currentTarget as HTMLInputElement).value))
              }
              step="0.01"
              type="number"
              value={form.thresholdValue}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">Cooldown (minutes)</span>
            <input
              class="input input-bordered"
              min="0"
              onInput={(event) =>
                update("cooldownMinutes", Number((event.currentTarget as HTMLInputElement).value))
              }
              type="number"
              value={form.cooldownMinutes}
            />
          </label>

          <label class="form-control">
            <span class="label-text font-medium">Recipient Email</span>
            <input
              class="input input-bordered"
              onInput={(event) =>
                update("recipientEmail", (event.currentTarget as HTMLInputElement).value)
              }
              type="email"
              value={form.recipientEmail}
            />
          </label>
        </div>

        {error ? <div class="alert alert-error mt-5">{error}</div> : null}
        {mutation.isPending ? <div class="alert alert-info mt-5">Creating task...</div> : null}

        <div class="mt-6 flex gap-3">
          <button class="btn btn-primary" type="submit">
            Create Watch Task
          </button>
          {draft ? (
            <button
              class="btn btn-ghost"
              onClick={() => navigate("compare")}
              type="button"
            >
              Back to compare result
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
              Cancel
            </button>
          )}
        </div>
      </form>

      <aside class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card">
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">API mapping</p>
        <h3 class="mt-2 text-xl font-semibold text-ink">Why this shape matters</h3>
        <div class="mt-4 space-y-4 text-sm leading-6 text-slate-600">
          <p>
            This page is not a decorative form. It maps directly to the live
            <code class="mx-1 rounded bg-base-200 px-1 py-0.5">POST /api/watch-tasks</code>
            request payload.
          </p>
          <p>
            In other words, the frontend is already wired to the active API instead of hiding
            behind placeholder data.
          </p>
        </div>
      </aside>
    </section>
  );
}
