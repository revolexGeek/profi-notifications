// Package atomicjson writes JSON files atomically with restrictive permissions.
// It is infrastructure shared by adapters that persist sensitive data: the
// write goes to a temporary file that is fsynced and renamed into place, so a
// crash never leaves a partially written file for another reader.
package atomicjson

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
)

const (
	privateFileMode = 0o600
	dirMode         = 0o755
)

// Write serialises value as indented JSON and replaces path atomically. On
// POSIX systems the file is created with 0600 permissions.
func Write(path string, value any) error {
	directory := filepath.Dir(path)
	if err := os.MkdirAll(directory, dirMode); err != nil {
		return fmt.Errorf("create directory %q: %w", directory, err)
	}

	data, err := marshalIndented(value)
	if err != nil {
		return fmt.Errorf("encode json for %q: %w", path, err)
	}

	temporary := filepath.Join(directory, fmt.Sprintf(".%s.%d.tmp", filepath.Base(path), os.Getpid()))
	defer os.Remove(temporary)

	if err := writeSyncedFile(temporary, data); err != nil {
		return err
	}

	if err := os.Rename(temporary, path); err != nil {
		return fmt.Errorf("replace %q: %w", path, err)
	}

	setPrivatePermissions(path)
	return nil
}

// marshalIndented mirrors Python's json.dump(ensure_ascii=False, indent=2):
// two-space indentation and no HTML escaping of <, >, and &.
func marshalIndented(value any) ([]byte, error) {
	var buffer bytes.Buffer
	encoder := json.NewEncoder(&buffer)
	encoder.SetEscapeHTML(false)
	encoder.SetIndent("", "  ")

	if err := encoder.Encode(value); err != nil {
		return nil, err
	}

	return buffer.Bytes(), nil
}

func writeSyncedFile(path string, data []byte) error {
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, privateFileMode)
	if err != nil {
		return fmt.Errorf("open temp file %q: %w", path, err)
	}

	if _, err := file.Write(data); err != nil {
		file.Close()
		return fmt.Errorf("write temp file %q: %w", path, err)
	}

	if err := file.Sync(); err != nil {
		file.Close()
		return fmt.Errorf("sync temp file %q: %w", path, err)
	}

	if err := file.Close(); err != nil {
		return fmt.Errorf("close temp file %q: %w", path, err)
	}

	return nil
}

func setPrivatePermissions(path string) {
	if runtime.GOOS == "windows" {
		return
	}
	_ = os.Chmod(path, privateFileMode)
}
