export function overloaded(value: number): number;
export function overloaded(value: string): string;
export function overloaded(value: number | string): number | string {
  return value;
}
