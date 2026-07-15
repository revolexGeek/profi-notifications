package config

import "os"

// unset removes an environment variable. t.Setenv already registers cleanup for
// the key, so restoring the original value is handled by the test framework.
func unset(key string) error {
	return os.Unsetenv(key)
}
