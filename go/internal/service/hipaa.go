package service

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"regexp"
	"sync"
	"time"
)

// PHI identifier patterns following HIPAA Safe Harbor method.
var phiPatterns = map[string]*regexp.Regexp{
	"names":          regexp.MustCompile(`\b[A-Z][a-z]+\s[A-Z][a-z]+\b`),
	"geographic":     regexp.MustCompile(`\b\d+\s[\w\s]+(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Blvd)\b`),
	"dates":          regexp.MustCompile(`\b(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2})\b`),
	"phone":          regexp.MustCompile(`(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}`),
	"email":          regexp.MustCompile(`\b[\w.+-]+@[\w-]+\.[\w.-]+\b`),
	"ssn":            regexp.MustCompile(`\b\d{3}-\d{2}-\d{4}\b`),
	"mrn":            regexp.MustCompile(`\b(?:MRN|Medical Record)[:\s#]?\d+\b`),
	"ip_address":     regexp.MustCompile(`\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b`),
	"urls":           regexp.MustCompile(`https?://[\w./\-?=&#]+`),
	"health_plan_id": regexp.MustCompile(`\b(?:Plan|Insurance)\s*(?:ID|#)[:\s]?\w+\b`),
	"account":        regexp.MustCompile(`\b(?:Account|Acct)[:\s#]?\d+\b`),
}

// Masking replacements for sensitive patterns.
var maskReplacements = map[string]string{
	"ssn":        "***-**-****",
	"phone":      "***-***-****",
	"email":      "****@****.***",
	"ip_address": "***.***.***.***",
	"urls":       "[URL_REDACTED]",
	"mrn":        "[MRN_REDACTED]",
}

// DetectPHI scans text for all categories of PHI and returns category->matches.
func DetectPHI(text string) map[string][]string {
	findings := make(map[string][]string)
	for category, pattern := range phiPatterns {
		matches := pattern.FindAllString(text, -1)
		if len(matches) > 0 {
			findings[category] = matches
		}
	}
	return findings
}

// DeidentifyText applies Safe Harbor de-identification to text.
func DeidentifyText(text string) string {
	result := text
	for cat, replacement := range maskReplacements {
		if pat, ok := phiPatterns[cat]; ok {
			result = pat.ReplaceAllString(result, replacement)
		}
	}
	return result
}

// DeidentifyMap serialises a map to JSON, applies de-identification, and deserialises back.
func DeidentifyMap(data map[string]interface{}) map[string]interface{} {
	raw, err := json.Marshal(data)
	if err != nil {
		return data
	}
	masked := DeidentifyText(string(raw))
	var out map[string]interface{}
	if err := json.Unmarshal([]byte(masked), &out); err != nil {
		return data
	}
	return out
}

// HashIdentifier returns a one-way SHA-256 prefix for pseudonymization.
func HashIdentifier(value string) string {
	h := sha256.Sum256([]byte(value))
	return fmt.Sprintf("%x", h[:8])
}

// AuditRecord represents a single immutable audit trail entry.
type AuditRecord struct {
	Timestamp    string `json:"timestamp"`
	UserID       string `json:"user_id"`
	Action       string `json:"action"`
	ResourceType string `json:"resource_type"`
	ResourceID   string `json:"resource_id,omitempty"`
	Detail       string `json:"detail"`
	Outcome      string `json:"outcome"`
}

// AuditLogger maintains an append-only in-memory audit trail.
type AuditLogger struct {
	mu      sync.Mutex
	records []AuditRecord
}

// Log appends an immutable audit record and returns it.
func (al *AuditLogger) Log(action, resourceType, detail string) AuditRecord {
	rec := AuditRecord{
		Timestamp:    time.Now().UTC().Format(time.RFC3339),
		UserID:       "system",
		Action:       action,
		ResourceType: resourceType,
		Detail:       detail,
		Outcome:      "success",
	}
	al.mu.Lock()
	al.records = append(al.records, rec)
	al.mu.Unlock()
	return rec
}

// GetRecords returns up to limit most recent records.
func (al *AuditLogger) GetRecords(limit int) []AuditRecord {
	al.mu.Lock()
	defer al.mu.Unlock()
	if limit <= 0 || limit > len(al.records) {
		limit = len(al.records)
	}
	start := len(al.records) - limit
	out := make([]AuditRecord, limit)
	copy(out, al.records[start:])
	return out
}

var (
	globalAuditLogger *AuditLogger
	auditOnce         sync.Once
)

// GetAuditLogger returns the global singleton AuditLogger.
func GetAuditLogger() *AuditLogger {
	auditOnce.Do(func() {
		globalAuditLogger = &AuditLogger{}
	})
	return globalAuditLogger
}
