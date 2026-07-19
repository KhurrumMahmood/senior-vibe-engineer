export function unsafeParse(payload: string): unknown {
  return JSON.parse(payload);
}

export function safeParse(payload: string): unknown | null {
  try {
    return JSON.parse(payload);
  } catch {
    return null;
  }
}

export function callbackParse(payload: string): void {
  try {
    queueMicrotask(() => {
      JSON.parse(payload);
    });
  } catch {
    // The callback's runtime is not inferred from its lexical parent.
  }
}

export const prose = "JSON.parse(payload) is only text";
