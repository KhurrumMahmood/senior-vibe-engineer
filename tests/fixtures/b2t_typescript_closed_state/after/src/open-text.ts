export function echoReason(reason: string): string {
  return reason === "queued" ? reason : "not queued";
}
