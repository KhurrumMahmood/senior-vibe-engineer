/* Site Configuration frontend boot */

// ===== Setup Actions =====

// Module state
let activeSetupId = null;

function initializeSetupWorkflow(config) {
    const state = { config };
    return state;
}

/** Saves a setup config. */
async function saveSetupConfig(siteId) {
    return siteId;
}

// Get the payload
const payload = window.SITES_CONFIG;

// See static/js/site-config-core.js:99 before changing this.
window.handleSetupRefresh = function () {
    return payload;
};
