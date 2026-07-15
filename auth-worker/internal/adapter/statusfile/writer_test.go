package statusfile

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"auth-worker/internal/domain"
)

func readStatus(t *testing.T, path string) map[string]any {
	t.Helper()
	data, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read status file: %v", err)
	}
	var decoded map[string]any
	if err := json.Unmarshal(data, &decoded); err != nil {
		t.Fatalf("decode status file: %v", err)
	}
	return decoded
}

func TestReportWritesNullsForAbsentFields(t *testing.T) {
	path := filepath.Join(t.TempDir(), "auth-status.json")

	err := New(path).Report(domain.StatusReport{
		Status:    domain.StatusRequiresLogin,
		UpdatedAt: 1700000000,
	})
	if err != nil {
		t.Fatalf("report: %v", err)
	}

	status := readStatus(t, path)
	if status["status"] != "requires_login" {
		t.Errorf("status = %v, want requires_login", status["status"])
	}
	if status["token_ttl"] != nil {
		t.Errorf("token_ttl = %v, want null", status["token_ttl"])
	}
	if status["error"] != nil {
		t.Errorf("error = %v, want null", status["error"])
	}
	if tokens, ok := status["tokens"].([]any); !ok || len(tokens) != 0 {
		t.Errorf("tokens = %v, want empty array", status["tokens"])
	}
}

func TestReportWritesTokensAndError(t *testing.T) {
	path := filepath.Join(t.TempDir(), "auth-status.json")
	ttl := int64(-5)
	exp := int64(1700000000)

	err := New(path).Report(domain.StatusReport{
		Status:    domain.StatusRenewFailed,
		UpdatedAt: 1700000100,
		TokenTTL:  &ttl,
		Refreshed: true,
		Error:     "renew did not change tokens",
		Tokens: []domain.TokenDetail{
			{Name: "prfr_bo_tkn", Domain: ".profi.ru", Path: "/", JWTExp: &exp, Fingerprint: "abc123"},
		},
	})
	if err != nil {
		t.Fatalf("report: %v", err)
	}

	status := readStatus(t, path)
	if status["error"] != "renew did not change tokens" {
		t.Errorf("error = %v", status["error"])
	}
	if status["token_ttl"].(float64) != -5 {
		t.Errorf("token_ttl = %v, want -5", status["token_ttl"])
	}
	tokens := status["tokens"].([]any)
	if len(tokens) != 1 {
		t.Fatalf("tokens count = %d, want 1", len(tokens))
	}
	token := tokens[0].(map[string]any)
	if token["fingerprint"] != "abc123" {
		t.Errorf("fingerprint = %v, want abc123", token["fingerprint"])
	}
	if token["cookie_expires"] != nil {
		t.Errorf("cookie_expires = %v, want null", token["cookie_expires"])
	}
}
