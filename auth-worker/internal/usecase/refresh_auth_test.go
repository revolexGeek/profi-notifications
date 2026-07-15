package usecase

import (
	"errors"
	"testing"

	"auth-worker/internal/domain"
)

const (
	testNow       = int64(1_000_000)
	refreshBefore = int64(180)
)

func newInteractor(store *fakeStore, renewer *fakeRenewer, locker *fakeLocker) *RefreshAuth {
	return NewRefreshAuth(store, renewer, locker, fixedClock{now: testNow}, discardLogger(), refreshBefore)
}

func TestExecuteSkipsRenewWhenTokenFresh(t *testing.T) {
	store := &fakeStore{jar: domain.NewJar([]domain.Cookie{tokenCookie(testNow + 3600)}), url: "https://profi.ru"}
	renewer := &fakeRenewer{}
	locker := &fakeLocker{}

	result, err := newInteractor(store, renewer, locker).Execute()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if renewer.calls != 0 {
		t.Errorf("renew called %d times, want 0", renewer.calls)
	}
	if result.Refreshed {
		t.Error("result should not be marked refreshed")
	}
	if result.TTLAfter != 3600 {
		t.Errorf("ttl after = %d, want 3600", result.TTLAfter)
	}
	if store.saveCall != 1 {
		t.Errorf("save called %d times, want 1", store.saveCall)
	}
	if locker.released != 1 {
		t.Errorf("lock released %d times, want 1", locker.released)
	}
}

func TestExecuteRenewsAndPersistsFreshToken(t *testing.T) {
	store := &fakeStore{jar: domain.NewJar([]domain.Cookie{tokenCookie(testNow + 60)}), url: "https://profi.ru"}
	renewer := &fakeRenewer{
		onRenew: func(jar *domain.Jar) {
			jar.Set(tokenCookie(testNow + 7200))
		},
		outcome: RenewOutcome{ResponseCookieNames: []string{"prfr_bo_tkn"}},
	}
	locker := &fakeLocker{}

	result, err := newInteractor(store, renewer, locker).Execute()

	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if renewer.calls != 1 {
		t.Errorf("renew called %d times, want 1", renewer.calls)
	}
	if !result.Refreshed {
		t.Error("result should be marked refreshed")
	}
	if result.TTLAfter != 7200 {
		t.Errorf("ttl after = %d, want 7200", result.TTLAfter)
	}
	if store.saveCall != 1 {
		t.Error("refreshed jar should be persisted")
	}
}

func TestExecuteFailsWhenRenewProducesNoToken(t *testing.T) {
	store := &fakeStore{jar: emptyTokenJar(), url: "https://profi.ru"}
	renewer := &fakeRenewer{} // renew changes nothing
	locker := &fakeLocker{}

	_, err := newInteractor(store, renewer, locker).Execute()

	assertRenewFailed(t, err)
	if store.saveCall != 0 {
		t.Error("nothing should be persisted on renew failure")
	}
}

func TestExecuteFailsWhenRenewedTokenExpired(t *testing.T) {
	store := &fakeStore{jar: domain.NewJar([]domain.Cookie{tokenCookie(testNow + 60)}), url: "https://profi.ru"}
	renewer := &fakeRenewer{
		onRenew: func(jar *domain.Jar) {
			jar.Set(tokenCookie(testNow - 10)) // already expired
		},
	}

	_, err := newInteractor(store, renewer, &fakeLocker{}).Execute()

	assertRenewFailed(t, err)
}

func TestExecuteFailsWhenTokensUnchanged(t *testing.T) {
	same := tokenCookie(testNow + 60)
	store := &fakeStore{jar: domain.NewJar([]domain.Cookie{same}), url: "https://profi.ru"}
	renewer := &fakeRenewer{
		onRenew: func(jar *domain.Jar) {
			jar.Set(same) // identical value and expiry
		},
	}

	_, err := newInteractor(store, renewer, &fakeLocker{}).Execute()

	assertRenewFailed(t, err)
}

func TestExecutePropagatesLoadError(t *testing.T) {
	store := &fakeStore{loadErr: &domain.CookieFileError{Message: "missing"}}

	_, err := newInteractor(store, &fakeRenewer{}, &fakeLocker{}).Execute()

	var cookieErr *domain.CookieFileError
	if !errors.As(err, &cookieErr) {
		t.Fatalf("error = %v, want CookieFileError", err)
	}
}

func TestExecutePropagatesLockError(t *testing.T) {
	locker := &fakeLocker{acquireErr: errors.New("locked")}

	_, err := newInteractor(&fakeStore{}, &fakeRenewer{}, locker).Execute()

	if err == nil {
		t.Fatal("expected lock error to propagate")
	}
}

func TestExecuteReleasesLockAfterFailure(t *testing.T) {
	store := &fakeStore{loadErr: &domain.CookieFileError{Message: "missing"}}
	locker := &fakeLocker{}

	_, _ = newInteractor(store, &fakeRenewer{}, locker).Execute()

	if locker.released != 1 {
		t.Errorf("lock released %d times, want 1 even on failure", locker.released)
	}
}

func emptyTokenJar() *domain.Jar {
	return domain.NewJar([]domain.Cookie{
		{Name: "sid", Value: "session", Domain: ".profi.ru", Path: "/"},
	})
}

func assertRenewFailed(t *testing.T, err error) {
	t.Helper()
	var renewErr *domain.RenewFailedError
	if !errors.As(err, &renewErr) {
		t.Fatalf("error = %v, want RenewFailedError", err)
	}
}
