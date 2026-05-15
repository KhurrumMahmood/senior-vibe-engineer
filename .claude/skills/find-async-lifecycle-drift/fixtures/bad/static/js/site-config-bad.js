function startProgressPolling() {
    setInterval(pollProgressStatus, 1000);
}

async function pollProgressStatus() {
    const response = await fetch('/api/progress/');
    const data = await response.json();
    document.getElementById('progressPanel').textContent = data.status;
    if (data.status === 'complete' || data.status === 'failed') {
        document.getElementById('donePanel').textContent = 'done';
    }
}
