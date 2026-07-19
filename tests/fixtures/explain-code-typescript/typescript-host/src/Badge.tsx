/** Render an accessible activity badge. */
export function Badge({ active }: { active: boolean }) {
  return <span>{active ? "active" : "idle"}</span>;
}
