package consumer

import "example.com/map-subsystem-go/internal/features"

func UseWidget() string {
	return features.BuildWidget("consumer").PublicLabel()
}
