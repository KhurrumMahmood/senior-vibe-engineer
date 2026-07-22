package implicitstate

type Job struct {
	State string
	Label string
}

func isQueued(job *Job) bool {
	return job.State == "queued"
}

func start(job *Job) {
	job.State = "running"
}

func finish(job *Job) {
	job.State = "done"
}

func isFinished(job *Job) bool {
	return "done" == job.State
}

func hasQueueLabel(job *Job) bool {
	return job.Label == "queued"
}

type OneShot struct {
	Status string
}

func isNew(value *OneShot) bool {
	return value.Status == "new"
}

type DeliveryPhase string

const (
	DeliveryQueued DeliveryPhase = "queued"
	DeliveryDone   DeliveryPhase = "done"
)

type Delivery struct {
	Phase DeliveryPhase
}

func deliveryQueued(delivery *Delivery) bool {
	return delivery.Phase == "queued"
}

type VendorJobPayload struct {
	State string
}

func vendorQueued(payload *VendorJobPayload) bool {
	return payload.State == "queued"
}
