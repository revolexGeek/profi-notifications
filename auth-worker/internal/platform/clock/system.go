// Package clock provides the production Clock implementation.
package clock

import "time"

// System reports wall-clock time. It satisfies usecase.Clock.
type System struct{}

// Now returns the current unix time in seconds.
func (System) Now() int64 {
	return time.Now().Unix()
}
