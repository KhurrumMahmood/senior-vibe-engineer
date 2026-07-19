interface SetupOptions {
    siteId: string;
}

/**
 * Initialize setup state before the first request is dispatched.
 *
 * @param options Stable identifiers needed to construct the state.
 * @returns A promise that settles after initialization completes.
 */
export async function initializeSetup(options: SetupOptions): Promise<void> {
    await Promise.resolve(options.siteId);
}
