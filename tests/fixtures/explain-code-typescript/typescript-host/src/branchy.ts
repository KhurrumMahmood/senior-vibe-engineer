import { fallback } from "./fallback";

export function decide(value: number): string {
  if (value > 10) {
    return "large";
  }
  if (value === 0) {
    return fallback(value);
  }
  return "small";
}

export const renderLabel = (name: string): string => (name ? `Hello ${name}` : "Hello");

const privateHelper = (): string => "private";
const localThing = "legacy";
export { localThing as legacyThing };
export { remoteThing } from "./remote";
export * from "./barrel";
