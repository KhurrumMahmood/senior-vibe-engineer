type JsonPanelProps = { payload: string };

export function JsonPanel({payload}: JsonPanelProps): JSX.Element {
  const parsed = JSON.parse(payload);
  return <section>{String(parsed)}</section>;
}
