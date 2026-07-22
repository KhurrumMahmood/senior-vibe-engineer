export interface RequestOptions {
  id: string;
  region?: "global" | "us";
  stage?: "preview" | "live";
}

export function buildRequest({ id, region = "global", stage = "preview" }: RequestOptions): string {
  return `${id}:${region}:${stage}`;
}

export function stableRequest({ id, region = "global" }: RequestOptions): string {
  return `${id}:${region}`;
}

export function completeRequest({ id, region = "global" }: RequestOptions): string {
  return `${id}:${region}`;
}

export function deliver(options: { id: string; audit: true }): string;
export function deliver(options: { id: string; deferred?: boolean }): string;
export function deliver(options: { id: string; audit?: true; deferred?: boolean }): string {
  return options.id;
}
