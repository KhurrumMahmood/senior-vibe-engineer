export type Entry = { count: number; label: string };

export type SemanticSummary = { total: number; labels: string[] };

export function summarizeByReduction(entries: Entry[]): SemanticSummary {
  const total = entries.reduce((running, entry) => running + entry.count, 0);
  const labels = entries.map((entry) => entry.label);
  return { total, labels };
}

export function summarizeByLoop(entries: Entry[]): SemanticSummary {
  let total = 0;
  const labels: string[] = [];
  for (const entry of entries) {
    total += entry.count;
    labels.push(entry.label);
  }
  return { labels, total };
}

export type CallerSummary = { total: number; labels: string[] };

export function calculateBase(entries: Entry[]): CallerSummary {
  return { total: entries.length, labels: entries.map((entry) => entry.label) };
}

export function calculateWithBoundary(entries: Entry[]): CallerSummary {
  const base = calculateBase(entries);
  return { labels: base.labels, total: base.total };
}

export type CloneSummary = { total: number; labels: string[] };

export function lexicalCloneOne(entries: Entry[]): CloneSummary {
  const total = entries.reduce((sum, entry) => sum + entry.count, 0);
  const labels = entries.map((entry) => entry.label);
  return { total, labels };
}

export function lexicalCloneTwo(entries: Entry[]): CloneSummary {
  const total = entries.reduce((sum, entry) => sum + entry.count, 0);
  const labels = entries.map((entry) => entry.label);
  return { total, labels };
}

export type PolicySummary = { total: number; labels: string[] };

export function failFastPolicy(entries: Entry[]): PolicySummary {
  if (entries.length === 0) throw new Error("entries required");
  return { total: entries.length, labels: entries.map((entry) => entry.label) };
}

export function defaultingPolicy(entries: Entry[]): PolicySummary {
  const labels = entries.map((entry) => entry.label);
  return { total: entries.length, labels };
}

export type UncertainSummary = { total: number; labels: string[] };

declare function readDeferred(entries: Entry[]): UncertainSummary;

const handlers: Record<string, (entries: Entry[]) => UncertainSummary> = {
  fallback: (entries) => ({ total: entries.length, labels: entries.map((entry) => entry.label) }),
};

export function summarizeWithDeferredCall(entries: Entry[]): UncertainSummary {
  const result = readDeferred(entries);
  return { total: result.total, labels: result.labels };
}

export function summarizeWithDynamicCall(entries: Entry[], mode: string): UncertainSummary {
  const result = handlers[mode](entries);
  return { labels: result.labels, total: result.total };
}
