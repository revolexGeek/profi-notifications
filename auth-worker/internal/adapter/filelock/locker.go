// Package filelock implements usecase.Locker with an advisory file lock. It
// confines the gofrs/flock dependency to the edge of the system.
package filelock

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"github.com/gofrs/flock"
)

const pollInterval = 100 * time.Millisecond

// Locker acquires an OS advisory lock on a lock file, bounded by a timeout.
type Locker struct {
	path    string
	timeout time.Duration
}

// New creates a Locker for the given lock file path and acquisition timeout.
func New(path string, timeout time.Duration) *Locker {
	return &Locker{path: path, timeout: timeout}
}

// Acquire blocks until the lock is held or the timeout elapses, returning a
// release function on success.
func (l *Locker) Acquire() (func() error, error) {
	if err := os.MkdirAll(filepath.Dir(l.path), 0o755); err != nil {
		return nil, fmt.Errorf("create lock directory: %w", err)
	}

	lock := flock.New(l.path)

	ctx, cancel := context.WithTimeout(context.Background(), l.timeout)
	defer cancel()

	locked, err := lock.TryLockContext(ctx, pollInterval)
	if err != nil {
		return nil, fmt.Errorf("acquire cookie lock within %s: %w", l.timeout, err)
	}
	if !locked {
		return nil, fmt.Errorf("could not acquire cookie lock within %s: %s", l.timeout, l.path)
	}

	return lock.Unlock, nil
}
