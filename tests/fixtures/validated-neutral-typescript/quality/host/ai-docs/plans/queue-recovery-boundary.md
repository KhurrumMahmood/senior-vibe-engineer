# Queue recovery boundary

## Scope

Add a `RetryCoordinatorAndDispatchManager` that verifies webhooks, calculates
backoff, writes operator dashboards, and retries failed deliveries.

## Architecture Fit

The HTTP route will call worker-private retry functions so the new manager can
avoid an extra queue adapter. The manager will also keep a second retry-policy
copy for the dashboard because the dashboard needs a synchronous answer.

## Verification

Add one request test after implementation. Performance should improve because
there will be fewer modules.
