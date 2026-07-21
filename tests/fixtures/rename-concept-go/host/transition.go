package renamefixture

import "example.com/renamefixture/legacy"

type Envelope struct {
	LegacyStatus string
}

func Convert(value legacy.LegacyStatus) CanonicalStatus {
	legacyStatus := value
	_ = Envelope{LegacyStatus: string(legacyStatus)}
	return CanonicalStatus(legacyStatus)
}

const retiredCopy = "legacy status"
