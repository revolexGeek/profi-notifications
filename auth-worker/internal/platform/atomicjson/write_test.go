package atomicjson

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestWriteCreatesReadableJSON(t *testing.T) {
	path := filepath.Join(t.TempDir(), "nested", "out.json")

	err := Write(path, map[string]any{"name": "value", "count": 3})
	if err != nil {
		t.Fatalf("write: %v", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read back: %v", err)
	}
	if !strings.Contains(string(data), `"name": "value"`) {
		t.Errorf("output missing expected field: %s", data)
	}
}

func TestWriteDoesNotEscapeHTML(t *testing.T) {
	path := filepath.Join(t.TempDir(), "out.json")

	if err := Write(path, map[string]string{"note": "a < b & c > d"}); err != nil {
		t.Fatalf("write: %v", err)
	}

	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read back: %v", err)
	}
	if strings.Contains(string(data), `\u003c`) {
		t.Errorf("HTML characters were escaped: %s", data)
	}
	if !strings.Contains(string(data), "a < b & c > d") {
		t.Errorf("raw characters missing: %s", data)
	}
}

func TestWriteLeavesNoTempFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "out.json")

	if err := Write(path, map[string]int{"x": 1}); err != nil {
		t.Fatalf("write: %v", err)
	}

	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatalf("read dir: %v", err)
	}
	if len(entries) != 1 {
		t.Fatalf("directory has %d entries, want 1 (no temp file left behind)", len(entries))
	}
}
