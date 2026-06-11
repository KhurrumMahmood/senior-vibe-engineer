let pollingTimer = null;
let requestGeneration = 0;
let controller = null;

function stopStatusPolling() {
    if (pollingTimer) {
        clearInterval(pollingTimer);
        pollingTimer = null;
    }
    if (controller) {
        controller.abort();
    }
}

function startStatusPolling() {
    requestGeneration += 1;
    controller = new AbortController();
    pollingTimer = setInterval(pollStatus, 1000);
}

async function pollStatus() {
    const generation = requestGeneration;
    const response = await fetch('/api/status/', {signal: controller.signal});
    const data = await response.json();
    if (generation !== requestGeneration) {
        return;
    }
    document.getElementById('statusPanel').textContent = data.status;
    if (['complete', 'failed', 'cancelled'].includes(data.status)) {
        stopStatusPolling();
    }
}

function cancelJob() {
    stopStatusPolling();
}

function retryJob() {
    startStatusPolling();
}
