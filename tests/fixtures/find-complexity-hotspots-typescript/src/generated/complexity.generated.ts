export function generatedHotspot(values: number[]): number {
  let total = 0;
  for (const value of values) {
    if (value % 2 === 0) total += 1;
    if (value % 3 === 0) total += 1;
    if (value % 5 === 0) total += 1;
    if (value % 7 === 0) total += 1;
    if (value % 11 === 0) total += 1;
    if (value % 13 === 0) total += 1;
    if (value % 17 === 0) total += 1;
    if (value % 19 === 0) total += 1;
    if (value % 23 === 0) total += 1;
    if (value % 29 === 0) total += 1;
    if (value % 31 === 0) total += 1;
    if (value % 37 === 0) total += 1;
    if (value % 41 === 0) total += 1;
    if (value % 43 === 0) total += 1;
    if (value % 47 === 0) total += 1;
    if (value % 53 === 0) total += 1;
    if (value % 59 === 0) total += 1;
  }
  return total;
}
