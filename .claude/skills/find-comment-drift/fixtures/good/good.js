/**
 * Initialize the setup workflow controller from Django-provided boot data.
 *
 * @param {Object} config Shared SiteConfigCore boot payload.
 * @returns {{config: Object}} Local controller state.
 */
function initializeSetupWorkflow(config) {
    return { config };
}

/**
 * Refresh setup data through the legacy global hook.
 *
 * @returns {Object} Shared SiteConfigCore boot payload.
 */
window.handleSetupRefresh = function handleSetupRefresh() {
    return window.SITES_CONFIG;
};
