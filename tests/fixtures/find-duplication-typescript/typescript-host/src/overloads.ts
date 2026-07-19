export function toKey(value: string): string;
export function toKey(value: number): string;
export function toKey(value: string | number): string {
    return String(value);
}

export function toToken(value: string): string;
export function toToken(value: number): string;
export function toToken(value: string | number): string {
    return String(value);
}
