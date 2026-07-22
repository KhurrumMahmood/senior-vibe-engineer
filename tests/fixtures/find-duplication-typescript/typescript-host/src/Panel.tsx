declare global {
    namespace JSX {
        interface IntrinsicElements {
            section: { "aria-label": string; children?: string };
        }
    }
}

export function Panel({ label }: { label: string }) {
    return <section aria-label={label}>{label}</section>;
}
