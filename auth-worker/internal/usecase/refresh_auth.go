package usecase

import (
	"fmt"
	"log/slog"

	"auth-worker/internal/domain"
)

// RefreshResult describes a successful auth cycle.
type RefreshResult struct {
	TTLBefore    *int64
	TTLAfter     int64
	Refreshed    bool
	TokensBefore []domain.TokenDetail
	TokensAfter  []domain.TokenDetail
}

// RefreshAuth is the interactor that keeps the session fresh: it loads the jar,
// renews when the token is close to expiry, verifies the renew delivered usable
// tokens, and persists the result. It reports failures as domain errors and
// leaves status reporting to its caller.
type RefreshAuth struct {
	store             CookieStore
	renewer           SessionRenewer
	locker            Locker
	clock             Clock
	log               *slog.Logger
	refreshBeforeSecs int64
}

// NewRefreshAuth wires the interactor with its collaborators.
func NewRefreshAuth(
	store CookieStore,
	renewer SessionRenewer,
	locker Locker,
	clock Clock,
	log *slog.Logger,
	refreshBeforeSecs int64,
) *RefreshAuth {
	return &RefreshAuth{
		store:             store,
		renewer:           renewer,
		locker:            locker,
		clock:             clock,
		log:               log,
		refreshBeforeSecs: refreshBeforeSecs,
	}
}

// Execute runs one auth cycle under the cookie lock.
func (uc *RefreshAuth) Execute() (RefreshResult, error) {
	release, err := uc.locker.Acquire()
	if err != nil {
		return RefreshResult{}, err
	}
	defer uc.release(release)

	jar, url, err := uc.store.Load()
	if err != nil {
		return RefreshResult{}, err
	}

	before := uc.snapshot(jar)

	refreshed, err := uc.refreshIfNeeded(jar, before)
	if err != nil {
		return RefreshResult{}, err
	}

	final, err := uc.finalTokens(jar)
	if err != nil {
		return RefreshResult{}, err
	}

	if err := uc.store.Save(jar, url); err != nil {
		return RefreshResult{}, err
	}

	return RefreshResult{
		TTLBefore:    before.ttlPointer(),
		TTLAfter:     final.ttl,
		Refreshed:    refreshed,
		TokensBefore: before.details,
		TokensAfter:  final.details,
	}, nil
}

// tokenSnapshot captures the token state of the jar at a point in time.
type tokenSnapshot struct {
	ttl     int64
	hasTTL  bool
	tokens  map[string]domain.TokenInfo
	details []domain.TokenDetail
}

func (s tokenSnapshot) ttlPointer() *int64 {
	if !s.hasTTL {
		return nil
	}
	ttl := s.ttl
	return &ttl
}

func (uc *RefreshAuth) snapshot(jar *domain.Jar) tokenSnapshot {
	now := uc.clock.Now()
	ttl, hasTTL := jar.TokenTTL(now)
	return tokenSnapshot{
		ttl:     ttl,
		hasTTL:  hasTTL,
		tokens:  jar.LatestTokens(),
		details: jar.TokenDetails(now),
	}
}

func (uc *RefreshAuth) refreshIfNeeded(jar *domain.Jar, before tokenSnapshot) (bool, error) {
	if !domain.NeedsRefresh(before.ttl, before.hasTTL, uc.refreshBeforeSecs) {
		uc.log.Info("token still valid, skipping renew", "ttl", before.ttl)
		return false, nil
	}

	uc.log.Info("token missing or expiring soon, renewing", "ttl", before.ttl, "has_ttl", before.hasTTL)

	outcome, err := uc.renewer.Renew(jar)
	if err != nil {
		return false, err
	}

	if err := uc.verifyRenew(jar, before, outcome); err != nil {
		return false, err
	}

	uc.dropStaleDuplicates(jar)
	return true, nil
}

func (uc *RefreshAuth) verifyRenew(jar *domain.Jar, before tokenSnapshot, outcome RenewOutcome) error {
	now := uc.clock.Now()
	ttl, hasTTL := jar.TokenTTL(now)
	changed := domain.ChangedTokens(before.tokens, jar.LatestTokens())

	if !hasTTL {
		return &domain.RenewFailedError{
			Message: "renew returned success but no JWT token cookies were found",
			Tokens:  jar.TokenDetails(now),
		}
	}

	if ttl <= 0 {
		return &domain.RenewFailedError{
			Message:  fmt.Sprintf("renew returned success but tokens remain expired: ttl=%d, response cookies: %v", ttl, outcome.ResponseCookieNames),
			TokenTTL: &ttl,
			Tokens:   jar.TokenDetails(now),
		}
	}

	if len(changed) == 0 {
		return &domain.RenewFailedError{
			Message:  "renew returned success but token values and expiry did not change",
			TokenTTL: &ttl,
			Tokens:   jar.TokenDetails(now),
		}
	}

	uc.log.Info("tokens refreshed", "changed", changed, "ttl", ttl)
	return nil
}

func (uc *RefreshAuth) dropStaleDuplicates(jar *domain.Jar) {
	for _, cookie := range jar.RemoveOldTokenDuplicates() {
		uc.log.Info("removed stale token duplicate",
			"name", cookie.Name,
			"domain", cookie.Domain,
			"path", cookie.Path,
		)
	}
}

// finalTokens is the terminal snapshot after any renew; it must contain a live
// token or the session is considered expired.
type finalTokens struct {
	ttl     int64
	details []domain.TokenDetail
}

func (uc *RefreshAuth) finalTokens(jar *domain.Jar) (finalTokens, error) {
	now := uc.clock.Now()
	ttl, hasTTL := jar.TokenTTL(now)
	details := jar.TokenDetails(now)

	if !hasTTL {
		return finalTokens{}, &domain.AuthExpiredError{Message: "no JWT tokens present in cookie jar"}
	}

	if ttl <= 0 {
		return finalTokens{}, &domain.AuthExpiredError{Message: fmt.Sprintf("JWT tokens expired: ttl=%d", ttl)}
	}

	return finalTokens{ttl: ttl, details: details}, nil
}

func (uc *RefreshAuth) release(release func() error) {
	if err := release(); err != nil {
		uc.log.Error("failed to release cookie lock", "error", err)
	}
}
