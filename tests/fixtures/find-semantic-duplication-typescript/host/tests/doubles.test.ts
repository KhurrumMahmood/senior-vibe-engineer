export type DoubleSummary = { total: number; labels: string[] };

export function fakeOne(value: string): DoubleSummary {
  return { total: value.length, labels: [value] };
}

export function fakeTwo(value: string): DoubleSummary {
  return { total: value.length, labels: [value] };
}
