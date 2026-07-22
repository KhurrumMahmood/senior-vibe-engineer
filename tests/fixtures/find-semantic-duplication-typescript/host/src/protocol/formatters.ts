import type { Entry } from "../semantic.js";

export type ProtocolSummary = { total: number; labels: string[] };

export interface Formatter {
  format(entries: Entry[]): ProtocolSummary;
}

export class WireFormatter implements Formatter {
  format(entries: Entry[]): ProtocolSummary {
    return { total: entries.length, labels: entries.map((entry) => entry.label) };
  }
}

export class DisplayFormatter implements Formatter {
  format(entries: Entry[]): ProtocolSummary {
    const labels = entries.map((entry) => entry.label);
    return { labels, total: entries.length };
  }
}
