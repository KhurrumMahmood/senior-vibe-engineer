function start() {
    const panel = document.getElementById('knownPanel');
    const picker = document.getElementById('setupExternalSourceBrandId');
    const spreadsheetEditor = document.getElementById('jss_textarea');
    const target = document.querySelector('[data-known-target]');
    const generatedAttr = document.querySelector('[data-product-relevant="false"]');
    const url = window.SiteConfigCore.siteEndpoint('knownEndpoint');
    const row = document.createElement('div');
    row.dataset.productRelevant = 'true';
    return {panel, picker, spreadsheetEditor, target, generatedAttr, row, url};
}

window.SiteConfigGood = {start};
