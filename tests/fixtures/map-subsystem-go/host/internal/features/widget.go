package features

import "example.com/map-subsystem-go/internal/shared"

type Widget struct {
	Label string
}

const DefaultLabel = "default"

func BuildWidget(label string) Widget {
	return Widget{Label: shared.Prefix(label)}
}

func (widget Widget) PublicLabel() string {
	return widget.Label
}

func privateLabel() string {
	return DefaultLabel
}
