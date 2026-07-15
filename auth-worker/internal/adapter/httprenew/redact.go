package httprenew

import "regexp"

const maxBodyPreview = 1000

// jwtPattern matches the three dot-separated segments of a JWT so secrets never
// reach the logs.
var jwtPattern = regexp.MustCompile(`eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+`)

// redactBody removes JWTs from a response body and truncates it for logging.
func redactBody(text string) string {
	redacted := jwtPattern.ReplaceAllString(text, "[JWT_REDACTED]")
	if len(redacted) > maxBodyPreview {
		redacted = redacted[:maxBodyPreview] + "..."
	}
	return redacted
}
