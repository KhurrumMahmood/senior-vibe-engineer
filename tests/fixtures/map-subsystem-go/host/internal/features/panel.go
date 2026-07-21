package features

import sharedAlias "example.com/map-subsystem-go/internal/shared"

var DefaultPanel = sharedAlias.Prefix("panel")

func NewPanel() string {
	return DefaultPanel
}
