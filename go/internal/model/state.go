package model

// ClinicalState is the shared state flowing through the agent pipeline.
// Each agent reads specific fields and writes its output fields.
type ClinicalState struct {
	RawInput      string                 `json:"raw_input"`
	PatientInfo   map[string]interface{} `json:"patient_info,omitempty"`
	Diagnosis     map[string]interface{} `json:"diagnosis,omitempty"`
	NeedsMoreInfo bool                   `json:"needs_more_info"`
	TreatmentPlan map[string]interface{} `json:"treatment_plan,omitempty"`
	CodingResult  map[string]interface{} `json:"coding_result,omitempty"`
	AuditResult   map[string]interface{} `json:"audit_result,omitempty"`
	CurrentAgent  string                 `json:"current_agent"`
	Errors        []string               `json:"errors"`
}

// AnalyzeRequest is the API request body for the analyze endpoint.
type AnalyzeRequest struct {
	PatientDescription string `json:"patient_description" binding:"required,min=10"`
}

// HealthResponse is the health check response.
type HealthResponse struct {
	Status  string `json:"status"`
	Service string `json:"service"`
	Version string `json:"version"`
}
