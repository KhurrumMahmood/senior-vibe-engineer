export type QueueEntry = {
    id: string;
    label: string;
    retryCount: number;
};

export function summarizeTestEntries(entries: readonly QueueEntry[]): string[] {
    const eligible = entries.filter((entry) => entry.retryCount < 3);
    const labels = eligible.map((entry) => `${entry.id}:${entry.label}`);
    const output: string[] = [];

    for (const label of labels) {
        if (!output.includes(label)) {
            output.push(label);
        }
    }

    return output.sort();
}
