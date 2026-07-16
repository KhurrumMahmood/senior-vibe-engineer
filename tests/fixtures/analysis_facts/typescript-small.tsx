import { fetchValue } from "./dep";

export function exported(input: number): number {
  const local = (value: number) => fetchValue(value);
  function nested(value: number): number {
    return local(value);
  }
  return nested(input);
}

export const load = (input: number) => exported(input);

export class Widget {
  render(state: { value: number }): number {
    state.value = load(state.value);
    return state.value;
  }
}
