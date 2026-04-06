package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/bcefghj/clinical-decision-system/internal/config"
	"github.com/bcefghj/clinical-decision-system/internal/model"
)

const diagnosisSystemPrompt = `You are an expert diagnostician performing differential diagnosis. Given structured patient information, provide a comprehensive differential diagnosis.

Return a JSON object with this structure:
{
  "primary_diagnosis": {
    "disease_name": "most likely diagnosis",
    "icd10_hint": "approximate ICD-10 code (e.g., J18.9)",
    "confidence": 0.85,
    "evidence": ["supporting finding 1", "supporting finding 2"],
    "reasoning": "clinical reasoning explanation"
  },
  "differential_list": [
    {
      "disease_name": "alternative diagnosis",
      "icd10_hint": "ICD-10 code",
      "confidence": 0.6,
      "evidence": ["evidence 1"],
      "reasoning": "why this is considered"
    }
  ],
  "recommended_tests": ["test 1 to confirm/rule out", "test 2"],
  "clinical_notes": "overall clinical impression",
  "knowledge_sources": ["source 1", "source 2"],
  "needs_more_info": false
}

Rules:
- Confidence scores must be between 0 and 1.
- Provide at least 2-3 differential diagnoses.
- List evidence from the patient data that supports each diagnosis.
- If critical information is missing, set needs_more_info to true.
- Use standard medical terminology and ICD-10 code hints.
- Return ONLY valid JSON, no markdown fences.`

// DiagnosisAgent generates differential diagnosis from structured patient data via LLM.
type DiagnosisAgent struct {
	cfg *config.Config
}

func NewDiagnosisAgent(cfg *config.Config) *DiagnosisAgent {
	return &DiagnosisAgent{cfg: cfg}
}

func (a *DiagnosisAgent) Name() string { return "diagnosis" }

func (a *DiagnosisAgent) Process(ctx context.Context, state *model.ClinicalState) error {
	state.CurrentAgent = a.Name()
	log.Printf("[DiagnosisAgent] start")

	if state.PatientInfo == nil {
		state.NeedsMoreInfo = true
		state.Errors = append(state.Errors, "No patient info available for diagnosis")
		return fmt.Errorf("no patient info")
	}

	patientJSON, _ := json.MarshalIndent(state.PatientInfo, "", "  ")
	userMsg := fmt.Sprintf("Patient information:\n\n%s\n\nProvide your differential diagnosis.", string(patientJSON))

	var result map[string]interface{}
	if err := callLLMJSON(ctx, a.cfg, diagnosisSystemPrompt, userMsg, 0.2, &result); err != nil {
		state.Errors = append(state.Errors, fmt.Sprintf("Diagnosis error: %v", err))
		return err
	}

	if needsMore, ok := result["needs_more_info"].(bool); ok {
		state.NeedsMoreInfo = needsMore
		delete(result, "needs_more_info")
	} else {
		state.NeedsMoreInfo = false
	}

	state.Diagnosis = result
	primary, _ := result["primary_diagnosis"].(map[string]interface{})
	if primary != nil {
		log.Printf("[DiagnosisAgent] success, primary=%v", primary["disease_name"])
	}
	return nil
}
