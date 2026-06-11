async function loadProgress() {
    setLoadingState('loading');
    const response = await fetch('/api/progress/');
    const data = await response.json();
    if (!data.items.length) {
        showEmptyState('no data');
    }
    if (data.status === 'failed' || data.status === 'cancelled') {
        const recoveryAction = 'retry';
        showRetryAction();
        return recoveryAction;
    }
    return data;
}
