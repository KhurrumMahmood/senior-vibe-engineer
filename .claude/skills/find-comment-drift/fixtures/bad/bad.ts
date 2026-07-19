interface SetupOptions {
    siteId: string;
}

// Get the payload
const payload = { siteId: "demo" };

export async function initializeSetup(options: SetupOptions): Promise<void> {
    await Promise.resolve(options.siteId);
}

/** Saves setup. */
export const handleSetupSave = async (options: SetupOptions): Promise<void> => {
    await Promise.resolve(options.siteId);
};

// See src/setup.ts:42 before changing this.
export const setupPayload = payload;
