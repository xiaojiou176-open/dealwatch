import { useEffect, useMemo, useState } from "preact/hooks";
import { ApiError } from "../lib/api";
import { useI18n } from "../lib/i18n";
import {
  useComparePreview,
  useCreateCompareEvidencePackage,
  useCreateWatchGroup,
  useNotificationSettings,
} from "../lib/hooks";
import { navigate, setWatchTaskDraft } from "../lib/routes";
import type {
  CompareEvidencePackageArtifact,
  ComparePreviewComparison,
  SavedCompareEvidencePackage,
  WatchGroupCandidateInput,
} from "../types";
import {
  EVIDENCE_STORAGE_KEY,
  MAX_SAVED_EVIDENCE_PACKAGES,
  defaultUrls,
  type DraftMessage,
} from "./compare/copy";
import {
  buildCandidateScoreIndex,
  buildCompareSchema,
  buildCreateGroupSchema,
  buildDecisionBoard,
  buildShareSummary,
  buildSavedEvidencePackage,
  buildSavedPackageId,
  defaultGroupTitle,
  loadSavedEvidencePackages,
  normalizeUrls,
  resolveCompareCopy,
  resolveUiMessage,
} from "./compare/helpers";
import {
  CompareDecisionSection,
  SavedEvidenceSection,
  CandidateEvidenceSection,
  GroupBuilderSection,
  PairEvidenceSection,
  type CompareGroupFormState,
} from "./compare/sections";

export function ComparePage() {
  const { locale, t } = useI18n();
  const compareSchema = useMemo(() => buildCompareSchema(), []);
  const createGroupSchema = useMemo(() => buildCreateGroupSchema(), []);
  const mutation = useComparePreview();
  const settingsQuery = useNotificationSettings();
  const createGroupMutation = useCreateWatchGroup();
  const createEvidencePackageMutation = useCreateCompareEvidencePackage();

  const [zipCode, setZipCode] = useState("98004");
  const [rawUrls, setRawUrls] = useState(defaultUrls);
  const [error, setError] = useState("");
  const [groupError, setGroupError] = useState("");
  const [evidenceError, setEvidenceError] = useState("");
  const [evidenceNotice, setEvidenceNotice] = useState("");
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);
  const [draftPackageId, setDraftPackageId] = useState<string | null>(null);
  const [savedPackages, setSavedPackages] = useState<SavedCompareEvidencePackage[]>(() => loadSavedEvidencePackages());
  const [groupForm, setGroupForm] = useState<CompareGroupFormState>({
    title: "",
    zipCode: "98004",
    cadenceMinutes: 360,
    thresholdType: "effective_price_below",
    thresholdValue: 0,
    cooldownMinutes: 240,
    recipientEmail: "owner@example.com",
    notificationsEnabled: true,
  });
  const compareText = (
    key: string,
    fallback: DraftMessage,
    values?: Record<string, string | number>,
  ) => resolveCompareCopy(t, locale, key, fallback, values);

  useEffect(() => {
    if (!settingsQuery.data) {
      return;
    }
    setGroupForm((current) => ({
      ...current,
      cooldownMinutes: settingsQuery.data.cooldownMinutes,
      recipientEmail:
        current.recipientEmail === "owner@example.com"
          ? settingsQuery.data.defaultRecipientEmail
          : current.recipientEmail,
      notificationsEnabled: settingsQuery.data.notificationsEnabled,
    }));
  }, [settingsQuery.data]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      window.localStorage.setItem(EVIDENCE_STORAGE_KEY, JSON.stringify(savedPackages));
    } catch {
      // Ignore local persistence failures and keep the in-memory review surface usable.
    }
  }, [savedPackages]);

  useEffect(() => {
    if (!selectedPackageId && savedPackages[0]) {
      setSelectedPackageId(savedPackages[0].id);
    }
  }, [savedPackages, selectedPackageId]);

  async function onSubmit(event: Event) {
    event.preventDefault();
    const parsed = compareSchema.safeParse({
      zipCode,
      submittedUrls: normalizeUrls(rawUrls),
    });
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "compare.notices.invalidCompare");
      return;
    }

    setError("");
    setGroupError("");
    setEvidenceError("");
    setEvidenceNotice("");
    setDraftPackageId(null);

    try {
      await mutation.mutateAsync(parsed.data);
      setGroupForm((current) => ({ ...current, zipCode: parsed.data.zipCode }));
    } catch (mutationError) {
      if (mutationError instanceof ApiError) {
        setError(mutationError.message);
        return;
      }
      setError("compare.notices.compareFailed");
    }
  }

  const result = mutation.data;
  const scoreByCandidate = useMemo(
    () => (result ? buildCandidateScoreIndex(result.matches) : {}),
    [result],
  );

  const comparisonByCandidateKey = useMemo(() => {
    const next = new Map<string, ComparePreviewComparison>();
    for (const item of result?.comparisons ?? []) {
      if (item.candidateKey) {
        next.set(item.candidateKey, item);
      }
    }
    return next;
  }, [result]);

  const successfulCandidates = useMemo<WatchGroupCandidateInput[]>(
    () =>
      (result?.comparisons ?? [])
        .filter((item) => item.fetchSucceeded && item.offer && item.storeKey && item.candidateKey)
        .map((item) => ({
          submittedUrl: item.submittedUrl,
          titleSnapshot: item.offer!.title,
          storeKey: item.storeKey!,
          candidateKey: item.candidateKey!,
          brandHint: item.brandHint,
          sizeHint: item.sizeHint,
          similarityScore: scoreByCandidate[item.candidateKey!] ?? 0,
        })),
    [result, scoreByCandidate],
  );
  const groupReadyCandidates = useMemo<WatchGroupCandidateInput[]>(
    () =>
      successfulCandidates.filter((candidate) =>
        comparisonByCandidateKey.get(candidate.candidateKey)?.supportContract?.canCreateWatchGroup,
      ),
    [comparisonByCandidateKey, successfulCandidates],
  );

  const decisionBoard = useMemo(
    () => (result ? buildDecisionBoard(locale, t, result, successfulCandidates, groupReadyCandidates) : null),
    [groupReadyCandidates, locale, result, successfulCandidates, t],
  );
  const compareAIExplain = result?.aiExplain ?? null;

  const selectedSavedPackage = useMemo(
    () => savedPackages.find((item) => item.id === selectedPackageId) ?? savedPackages[0] ?? null,
    [savedPackages, selectedPackageId],
  );

  useEffect(() => {
    if (!groupReadyCandidates.length) {
      return;
    }
    const bestObservedPrice = Math.min(
      ...groupReadyCandidates.map((candidate) => {
        const comparison = result?.comparisons.find((item) => item.candidateKey === candidate.candidateKey);
        return comparison?.offer?.price ?? Number.POSITIVE_INFINITY;
      }),
    );
    const nextTitle = defaultGroupTitle(groupReadyCandidates, locale, t);
    const nextThresholdValue = Number.isFinite(bestObservedPrice)
      ? Number(bestObservedPrice.toFixed(2))
      : undefined;
    setGroupForm((current) => {
      const resolvedTitle = current.title || nextTitle;
      const resolvedThresholdValue = nextThresholdValue ?? current.thresholdValue;
      if (
        current.title === resolvedTitle &&
        current.zipCode === zipCode &&
        current.thresholdValue === resolvedThresholdValue
      ) {
        return current;
      }
      return {
        ...current,
        title: resolvedTitle,
        zipCode,
        thresholdValue: resolvedThresholdValue,
      };
    });
  }, [groupReadyCandidates, locale, result, t, zipCode]);

  function updateGroupForm<K extends keyof CompareGroupFormState>(
    key: K,
    value: CompareGroupFormState[K],
  ) {
    setGroupForm((current) => ({ ...current, [key]: value }));
  }

  function useComparisonForTask(
    submittedUrl: string,
    normalizedUrl: string | undefined,
    offerTitle: string,
    storeKey: string | undefined,
    candidateKey: string | undefined,
    brandHint: string | undefined,
    sizeHint: string | undefined,
  ) {
    setWatchTaskDraft({
      submittedUrl,
      normalizedUrl: normalizedUrl ?? submittedUrl,
      title: offerTitle,
      storeKey: storeKey ?? "unknown",
      candidateKey: candidateKey ?? "unknown",
      brandHint,
      sizeHint,
      defaultRecipientEmail: settingsQuery.data?.defaultRecipientEmail ?? "owner@example.com",
      zipCode,
    });
    navigate("watch-new");
  }

  function upsertCurrentEvidencePackage(runtimeArtifact: CompareEvidencePackageArtifact | null) {
    if (!result || !decisionBoard) {
      return null;
    }

    const nextId = draftPackageId ?? buildSavedPackageId();
    const submittedUrls = normalizeUrls(rawUrls);
    const nextPackage = buildSavedEvidencePackage({
      id: nextId,
      result,
      zipCode,
      submittedUrls,
      decisionBoard,
      runtimeArtifact,
      locale,
      t,
    });

    setSavedPackages((current) => {
      const existing = current.find((item) => item.id === nextId);
      const merged: SavedCompareEvidencePackage = existing
        ? {
            ...existing,
            ...nextPackage,
            runtimeArtifact: runtimeArtifact ?? existing.runtimeArtifact,
          }
        : nextPackage;

      const withoutExisting = current.filter((item) => item.id !== nextId);
      return [merged, ...withoutExisting].slice(0, MAX_SAVED_EVIDENCE_PACKAGES);
    });

    setDraftPackageId(nextId);
    setSelectedPackageId(nextId);
    return nextPackage;
  }

  function handleSaveEvidencePackage() {
    if (!result || !decisionBoard) {
      return;
    }
    upsertCurrentEvidencePackage(null);
    setEvidenceError("");
    setEvidenceNotice("compare.notices.saveLocal");
  }

  async function handleCreateRuntimeEvidencePackage() {
    if (!result || !decisionBoard) {
      return;
    }
    setEvidenceError("");
    setEvidenceNotice("");
    try {
      const runtimeArtifact = await createEvidencePackageMutation.mutateAsync({
        submittedUrls: normalizeUrls(rawUrls),
        zipCode,
        compareResult: result,
      });
      upsertCurrentEvidencePackage(runtimeArtifact);
      setEvidenceNotice("compare.notices.runtimeCreated");
    } catch (mutationError) {
      if (mutationError instanceof ApiError) {
        setEvidenceError(mutationError.message);
        return;
      }
      setEvidenceError("compare.notices.runtimeFailed");
    }
  }

  async function handleCopyEvidenceSummary(payload: SavedCompareEvidencePackage | null) {
    if (!payload) {
      return;
    }
    try {
      await navigator.clipboard.writeText(buildShareSummary(locale, t, payload));
      setEvidenceError("");
      setEvidenceNotice("compare.notices.copiedSummary");
    } catch {
      setEvidenceError("compare.notices.clipboardFailed");
    }
  }

  async function onCreateGroup() {
    const parsed = createGroupSchema.safeParse(groupForm);
    if (!parsed.success) {
      setGroupError(parsed.error.issues[0]?.message ?? "compare.notices.invalidGroup");
      return;
    }
    if (groupReadyCandidates.length < 2) {
      setGroupError("compare.notices.needTwoCandidates");
      return;
    }
    setGroupError("");
    try {
      const group = await createGroupMutation.mutateAsync({
        ...parsed.data,
        title: parsed.data.title?.trim() || undefined,
        candidates: groupReadyCandidates,
      });
      navigate("watch-group-detail", group.id);
    } catch (mutationError) {
      if (mutationError instanceof ApiError) {
        setGroupError(mutationError.message);
        return;
      }
      setGroupError("compare.notices.createGroupFailed");
    }
  }

  const currentSharePayload = result && decisionBoard
    ? buildSavedEvidencePackage({
        id: draftPackageId ?? "current-compare-preview",
        result,
        zipCode,
        submittedUrls: normalizeUrls(rawUrls),
        decisionBoard,
        runtimeArtifact: null,
        locale,
        t,
      })
    : null;

  return (
    <section class="space-y-4">
      <form
        class="rounded-[1.75rem] border border-base-300 bg-base-100/95 p-6 shadow-card"
        onSubmit={onSubmit}
      >
        <p class="text-xs font-semibold uppercase tracking-[0.2em] text-ember">{t("compare.form.eyebrow")}</p>
        <h2 class="mt-2 text-2xl font-semibold text-ink">
          {t("compare.form.title")}
        </h2>
        <p class="mt-2 text-sm leading-6 text-slate-600">
          {t("compare.form.summary")}
        </p>

        <div class="mt-6 grid gap-4">
          <label class="form-control gap-2">
            <span class="label-text block font-medium">{t("compare.form.zipCode")}</span>
            <input
              class="input input-bordered"
              onInput={(event) => setZipCode((event.currentTarget as HTMLInputElement).value)}
              value={zipCode}
            />
          </label>

          <label class="form-control gap-2">
            <span class="label-text block font-medium">{t("compare.form.productUrls")}</span>
            <textarea
              class="textarea textarea-bordered min-h-48"
              onInput={(event) => setRawUrls((event.currentTarget as HTMLTextAreaElement).value)}
              value={rawUrls}
            />
            <span class="label-text-alt mt-2 text-slate-500">{t("compare.form.productUrlsHelp")}</span>
          </label>
        </div>

        {error ? <div class="alert alert-error mt-5">{resolveUiMessage(error, t)}</div> : null}
        {mutation.isPending ? <div class="alert alert-info mt-5">{t("compare.form.loading")}</div> : null}

        <div class="mt-6">
          <button class="btn btn-primary" type="submit">{t("compare.form.submit")}</button>
        </div>
      </form>

      {decisionBoard && result ? (
        <CompareDecisionSection
          compareAIExplain={compareAIExplain}
          recommendation={result.recommendation}
          compareText={compareText}
          copyCurrentEvidenceSummary={() => handleCopyEvidenceSummary(currentSharePayload)}
          createRuntimeEvidencePackage={handleCreateRuntimeEvidencePackage}
          createRuntimePending={createEvidencePackageMutation.isPending}
          decisionBoard={decisionBoard}
          evidenceError={evidenceError}
          evidenceNotice={evidenceNotice}
          locale={locale}
          result={result}
          saveEvidencePackage={handleSaveEvidencePackage}
          t={t}
        />
      ) : null}

      <SavedEvidenceSection
        compareText={compareText}
        copySavedEvidenceSummary={handleCopyEvidenceSummary}
        locale={locale}
        savedPackages={savedPackages}
        selectedPackageId={selectedPackageId}
        selectedSavedPackage={selectedSavedPackage}
        selectSavedPackage={setSelectedPackageId}
        t={t}
      />

      {result ? (
        <CandidateEvidenceSection
          compareText={compareText}
          comparisonByCandidateKey={comparisonByCandidateKey}
          groupReadyCandidates={groupReadyCandidates}
          locale={locale}
          result={result}
          scoreByCandidate={scoreByCandidate}
          t={t}
          useComparisonForTask={useComparisonForTask}
        />
      ) : null}

      {result ? (
        <div class="grid gap-4 xl:grid-cols-[1.1fr,0.9fr]">
          <GroupBuilderSection
            compareText={compareText}
            comparisonByCandidateKey={comparisonByCandidateKey}
            createGroup={onCreateGroup}
            createGroupPending={createGroupMutation.isPending}
            groupError={groupError}
            groupForm={groupForm}
            groupReadyCandidates={groupReadyCandidates}
            locale={locale}
            t={t}
            updateGroupForm={updateGroupForm}
          />
          <PairEvidenceSection
            compareText={compareText}
            comparisonByCandidateKey={comparisonByCandidateKey}
            locale={locale}
            matches={result.matches}
            t={t}
          />
        </div>
      ) : null}
    </section>
  );
}
