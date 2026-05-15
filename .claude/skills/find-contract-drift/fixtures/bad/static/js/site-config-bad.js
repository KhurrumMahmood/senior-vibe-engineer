function stop() {
    return true;
}

function loadContracts() {
    const panel = document.getElementById('missingPanel');
    const target = document.querySelector('[data-missing-target]');
    const url = window.SiteConfigCore.siteEndpoint('missingEndpoint');
    return {panel, target, url};
}

window.SiteConfigBad = {stop, loadContracts};
