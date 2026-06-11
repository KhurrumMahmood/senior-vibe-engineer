async function loadProgress() {
    const response = await fetch('/api/progress/');
    const data = await response.json();
    document.getElementById('status').textContent = data.status;
    if (data.status === 'complete') {
        document.getElementById('status').textContent = 'done';
    }
}
