package usecase

import (
	"errors"
	"testing"
	"time"

	"auth-worker/internal/domain"
)

var testIntervals = Intervals{
	Check:       60 * time.Second,
	AuthExpired: 300 * time.Second,
	Error:       30 * time.Second,
}

func newWorker(refresher AuthRefresher, reporter *fakeReporter) *Worker {
	return NewWorker(refresher, reporter, fixedClock{now: testNow}, discardLogger(), testIntervals)
}

func TestWorkerReportsSuccess(t *testing.T) {
	reporter := &fakeReporter{}
	refresher := &fakeRefresher{result: RefreshResult{TTLAfter: 900, Refreshed: true}}

	sleep := newWorker(refresher, reporter).RunOnce()

	if sleep != testIntervals.Check {
		t.Errorf("sleep = %s, want %s", sleep, testIntervals.Check)
	}
	report := reporter.last()
	if report.Status != domain.StatusOK {
		t.Errorf("status = %q, want ok", report.Status)
	}
	if report.TokenTTL == nil || *report.TokenTTL != 900 {
		t.Errorf("token ttl = %v, want 900", report.TokenTTL)
	}
	if !report.Refreshed {
		t.Error("report should mark refreshed")
	}
}

func TestWorkerMapsErrorsToStatuses(t *testing.T) {
	ttl := int64(-5)

	cases := []struct {
		name         string
		err          error
		wantStatus   domain.Status
		wantInterval time.Duration
	}{
		{
			name:         "renew failed",
			err:          &domain.RenewFailedError{Message: "no change", TokenTTL: &ttl},
			wantStatus:   domain.StatusRenewFailed,
			wantInterval: testIntervals.AuthExpired,
		},
		{
			name:         "auth expired",
			err:          &domain.AuthExpiredError{Message: "gone"},
			wantStatus:   domain.StatusRequiresLogin,
			wantInterval: testIntervals.AuthExpired,
		},
		{
			name:         "cookie file",
			err:          &domain.CookieFileError{Message: "missing"},
			wantStatus:   domain.StatusMissingCookies,
			wantInterval: testIntervals.Error,
		},
		{
			name:         "network timeout",
			err:          &domain.RenewNetworkError{Err: errors.New("deadline"), Timeout: true},
			wantStatus:   domain.StatusNetworkTimeout,
			wantInterval: testIntervals.Error,
		},
		{
			name:         "network error",
			err:          &domain.RenewNetworkError{Err: errors.New("reset"), Timeout: false},
			wantStatus:   domain.StatusNetworkError,
			wantInterval: testIntervals.Error,
		},
		{
			name:         "unexpected",
			err:          errors.New("boom"),
			wantStatus:   domain.StatusError,
			wantInterval: testIntervals.Error,
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			reporter := &fakeReporter{}
			refresher := &fakeRefresher{err: tc.err}

			sleep := newWorker(refresher, reporter).RunOnce()

			if sleep != tc.wantInterval {
				t.Errorf("sleep = %s, want %s", sleep, tc.wantInterval)
			}
			if got := reporter.last().Status; got != tc.wantStatus {
				t.Errorf("status = %q, want %q", got, tc.wantStatus)
			}
		})
	}
}

func TestWorkerRenewFailedCarriesTokenDetails(t *testing.T) {
	ttl := int64(-5)
	details := []domain.TokenDetail{{Name: "prfr_bo_tkn", Fingerprint: "abc"}}
	reporter := &fakeReporter{}
	refresher := &fakeRefresher{err: &domain.RenewFailedError{Message: "no change", TokenTTL: &ttl, Tokens: details}}

	newWorker(refresher, reporter).RunOnce()

	report := reporter.last()
	if len(report.Tokens) != 1 {
		t.Fatalf("token details count = %d, want 1", len(report.Tokens))
	}
	if !report.Refreshed {
		t.Error("renew_failed report should mark refreshed true")
	}
	if report.TokenTTL == nil || *report.TokenTTL != -5 {
		t.Errorf("token ttl = %v, want -5", report.TokenTTL)
	}
}
