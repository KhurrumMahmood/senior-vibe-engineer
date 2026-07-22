declare namespace JSX {
  interface Element {}
  interface IntrinsicElements {
    section: Record<string, unknown>;
    p: Record<string, unknown>;
  }
}

declare function Select<T, U = unknown>(props: Record<string, unknown>): JSX.Element;

declare namespace UI {
  function Select<T, U = unknown>(props: Record<string, unknown>): JSX.Element;
}
