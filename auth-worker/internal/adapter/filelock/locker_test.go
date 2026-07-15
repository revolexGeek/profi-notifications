package filelock

import (
	"path/filepath"
	"testing"
	"time"
)

func TestAcquireAndReleaseAllowsReacquire(t *testing.T) {
	path := filepath.Join(t.TempDir(), "cookies.lock")
	locker := New(path, time.Second)

	release, err := locker.Acquire()
	if err != nil {
		t.Fatalf("first acquire: %v", err)
	}
	if err := release(); err != nil {
		t.Fatalf("release: %v", err)
	}

	release, err = locker.Acquire()
	if err != nil {
		t.Fatalf("re-acquire after release: %v", err)
	}
	if err := release(); err != nil {
		t.Fatalf("second release: %v", err)
	}
}

func TestAcquireCreatesMissingDirectory(t *testing.T) {
	path := filepath.Join(t.TempDir(), "nested", "dir", "cookies.lock")

	release, err := New(path, time.Second).Acquire()
	if err != nil {
		t.Fatalf("acquire in missing directory: %v", err)
	}
	if err := release(); err != nil {
		t.Fatalf("release: %v", err)
	}
}
