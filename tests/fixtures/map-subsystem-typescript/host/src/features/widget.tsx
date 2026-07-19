import { increment } from "@app/shared/math";

export type WidgetProps = { label: string };

export function FeatureWidget({ label }: WidgetProps): string {
  return `${label}:${increment(1)}`;
}

export function formatWidgetLabel(label: string): string {
  return label.trim();
}
