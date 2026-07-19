export function isRetryableStatus(status: number): boolean {
    return status === 408 || status === 429 || status >= 500;
}

export function renderStatusLabel(status: number): string {
    if (status >= 500) {
        return "server-error";
    }
    return `status-${status}`;
}
