//go:build linux

package service

// PlatformName is available only for the linux build constraint.
func PlatformName() string {
	return "linux"
}
