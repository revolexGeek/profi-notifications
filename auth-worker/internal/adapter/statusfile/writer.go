// Package statusfile implements usecase.StatusReporter by writing the auth
// status as JSON. It owns the on-disk status shape so the inner layers stay free
// of serialisation concerns.
package statusfile

import (
	"auth-worker/internal/domain"
	"auth-worker/internal/platform/atomicjson"
)

// Writer persists status reports to a JSON file.
type Writer struct {
	path string
}

// New creates a Writer bound to the given file path.
func New(path string) *Writer {
	return &Writer{path: path}
}

// Report writes the status report atomically.
func (w *Writer) Report(report domain.StatusReport) error {
	return atomicjson.Write(w.path, dtoFromReport(report))
}

// statusDTO is the on-disk status shape. Pointer fields serialise as JSON null
// when absent, matching the original worker's output.
type statusDTO struct {
	Status    string     `json:"status"`
	UpdatedAt int64      `json:"updated_at"`
	TokenTTL  *int64     `json:"token_ttl"`
	Refreshed bool       `json:"refreshed"`
	Error     *string    `json:"error"`
	Tokens    []tokenDTO `json:"tokens"`
}

type tokenDTO struct {
	Name          string `json:"name"`
	Domain        string `json:"domain"`
	Path          string `json:"path"`
	JWTExp        *int64 `json:"jwt_exp"`
	JWTTTL        *int64 `json:"jwt_ttl"`
	CookieExpires *int64 `json:"cookie_expires"`
	Fingerprint   string `json:"fingerprint"`
}

func dtoFromReport(report domain.StatusReport) statusDTO {
	return statusDTO{
		Status:    string(report.Status),
		UpdatedAt: report.UpdatedAt,
		TokenTTL:  report.TokenTTL,
		Refreshed: report.Refreshed,
		Error:     errorPointer(report.Error),
		Tokens:    tokensFromDetails(report.Tokens),
	}
}

func tokensFromDetails(details []domain.TokenDetail) []tokenDTO {
	tokens := make([]tokenDTO, 0, len(details))
	for _, detail := range details {
		tokens = append(tokens, tokenDTO{
			Name:          detail.Name,
			Domain:        detail.Domain,
			Path:          detail.Path,
			JWTExp:        detail.JWTExp,
			JWTTTL:        detail.JWTTTL,
			CookieExpires: detail.CookieExpires,
			Fingerprint:   detail.Fingerprint,
		})
	}
	return tokens
}

func errorPointer(message string) *string {
	if message == "" {
		return nil
	}
	return &message
}
