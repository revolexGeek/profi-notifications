package usecase

import (
	"errors"
	"log/slog"
	"time"

	"auth-worker/internal/domain"
)

// Intervals configures how long the worker waits before the next cycle,
// depending on the previous outcome.
type Intervals struct {
	Check       time.Duration
	AuthExpired time.Duration
	Error       time.Duration
}

// AuthRefresher runs a single auth cycle. RefreshAuth satisfies it; the
// interface exists so the worker's error handling can be tested in isolation.
type AuthRefresher interface {
	Execute() (RefreshResult, error)
}

// Worker turns the outcome of an auth cycle into a persisted status and the
// delay before the next cycle. It is the single place that writes status, so
// success and every failure mode are reported consistently.
type Worker struct {
	refresher AuthRefresher
	reporter  StatusReporter
	clock     Clock
	log       *slog.Logger
	intervals Intervals
}

// NewWorker wires the worker with its collaborators.
func NewWorker(
	refresher AuthRefresher,
	reporter StatusReporter,
	clock Clock,
	log *slog.Logger,
	intervals Intervals,
) *Worker {
	return &Worker{
		refresher: refresher,
		reporter:  reporter,
		clock:     clock,
		log:       log,
		intervals: intervals,
	}
}

// RunOnce executes one auth cycle, records its status, and returns how long to
// wait before the next cycle.
func (w *Worker) RunOnce() time.Duration {
	result, err := w.refresher.Execute()
	if err != nil {
		return w.reportFailure(err)
	}
	return w.reportSuccess(result)
}

func (w *Worker) reportSuccess(result RefreshResult) time.Duration {
	ttl := result.TTLAfter
	w.report(domain.StatusReport{
		Status:    domain.StatusOK,
		UpdatedAt: w.clock.Now(),
		TokenTTL:  &ttl,
		Refreshed: result.Refreshed,
		Tokens:    result.TokensAfter,
	})
	w.log.Info("authorization confirmed", "ttl", result.TTLAfter, "refreshed", result.Refreshed)
	return w.intervals.Check
}

func (w *Worker) reportFailure(err error) time.Duration {
	var renewFailed *domain.RenewFailedError
	var authExpired *domain.AuthExpiredError
	var cookieFile *domain.CookieFileError
	var network *domain.RenewNetworkError

	switch {
	case errors.As(err, &renewFailed):
		return w.onRenewFailed(renewFailed)
	case errors.As(err, &authExpired):
		return w.onAuthExpired(authExpired)
	case errors.As(err, &cookieFile):
		return w.onCookieFile(cookieFile)
	case errors.As(err, &network):
		return w.onNetwork(network)
	default:
		return w.onUnexpected(err)
	}
}

func (w *Worker) onRenewFailed(err *domain.RenewFailedError) time.Duration {
	w.log.Error("renew did not refresh tokens", "error", err)
	w.report(domain.StatusReport{
		Status:    domain.StatusRenewFailed,
		UpdatedAt: w.clock.Now(),
		TokenTTL:  err.TokenTTL,
		Refreshed: true,
		Error:     err.Error(),
		Tokens:    err.Tokens,
	})
	return w.intervals.AuthExpired
}

func (w *Worker) onAuthExpired(err *domain.AuthExpiredError) time.Duration {
	w.log.Error("authorization expired", "error", err)
	w.report(domain.StatusReport{
		Status:    domain.StatusRequiresLogin,
		UpdatedAt: w.clock.Now(),
		Error:     err.Error(),
	})
	return w.intervals.AuthExpired
}

func (w *Worker) onCookieFile(err *domain.CookieFileError) time.Duration {
	w.log.Error("cookie file error", "error", err)
	w.report(domain.StatusReport{
		Status:    domain.StatusMissingCookies,
		UpdatedAt: w.clock.Now(),
		Error:     err.Error(),
	})
	return w.intervals.Error
}

func (w *Worker) onNetwork(err *domain.RenewNetworkError) time.Duration {
	status := domain.StatusNetworkError
	message := "network error"
	if err.Timeout {
		status = domain.StatusNetworkTimeout
		message = "request timeout"
	}

	w.log.Error(message, "error", err)
	w.report(domain.StatusReport{
		Status:    status,
		UpdatedAt: w.clock.Now(),
		Error:     err.Error(),
	})
	return w.intervals.Error
}

func (w *Worker) onUnexpected(err error) time.Duration {
	w.log.Error("unexpected auth-worker error", "error", err)
	w.report(domain.StatusReport{
		Status:    domain.StatusError,
		UpdatedAt: w.clock.Now(),
		Error:     err.Error(),
	})
	return w.intervals.Error
}

func (w *Worker) report(report domain.StatusReport) {
	if err := w.reporter.Report(report); err != nil {
		w.log.Error("failed to write status", "error", err)
	}
}
