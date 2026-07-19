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
