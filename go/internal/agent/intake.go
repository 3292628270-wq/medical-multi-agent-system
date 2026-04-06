package agent

import (
	"context"
	"fmt"
	"log"

	"github.com/bcefghj/clinical-decision-system/internal/config"
	"github.com/bcefghj/clinical-decision-system/internal/model"
)

const intakeSystemPrompt = `You are an expert medical intake specialist. Your job is to extract structured patient information from the provided clinical narrative.

Extract the following fields as a JSON object:
{
  "name": "patient name or 'Unknown'",
  "age": <integer>,
  "gender": "male|female|other|unknown",
  "chief_complaint": "main reason for visit",
  "symptoms": [
    {"name": "symptom name", "duration_days": <int or null>, "severity": "mild|moderate|severe|critical", "description": "details"}
  ],
  "medical_history": ["list of past conditions"],
  "family_history": ["list of family conditions"],
  "allergies": [
    {"substance": "name", "reaction": "description", "severity": "mild|moderate|severe"}
  ],
  "current_medications": [
    {"name": "drug name", "dosage": "dose", "frequency": "how often"}
  ],
  "vital_signs": {
    "temperature": <float or null>,
    "heart_rate": <int or null>,
    "blood_pressure_systolic": <int or null>,
    "blood_pressure_diastolic": <int or null>,
    "respiratory_rate": <int or null>,
    "oxygen_saturation": <float or null>
  },
  "lab_results": [
    {"test_name": "name", "value": "result", "unit": "unit", "reference_range": "range", "is_abnormal": true/false}
  ]
}

Rules:
- If a field is not mentioned, use reasonable defaults or null.
- Age must be a positive integer. If unclear, estimate from context.
- Always identify the chief complaint even if not explicitly stated.
- Return ONLY valid JSON, no markdown fences.`

// IntakeAgent parses raw patient description into structured patient info via LLM.
type IntakeAgent struct {
	cfg *config.Config
}

func NewIntakeAgent(cfg *config.Config) *IntakeAgent {
	return &IntakeAgent{cfg: cfg}
}

func (a *IntakeAgent) Name() string { return "intake" }

func (a *IntakeAgent) Process(ctx context.Context, state *model.ClinicalState) error {
	state.CurrentAgent = a.Name()
	log.Printf("[IntakeAgent] processing input (len=%d)", len(state.RawInput))

	if state.RawInput == "" {
		state.Errors = append(state.Errors, "No raw input provided to Intake Agent")
		return fmt.Errorf("empty raw input")
	}

	userMsg := fmt.Sprintf("Patient narrative:\n\n%s", state.RawInput)

	var result map[string]interface{}
	if err := callLLMJSON(ctx, a.cfg, intakeSystemPrompt, userMsg, 0.1, &result); err != nil {
		state.Errors = append(state.Errors, fmt.Sprintf("Intake error: %v", err))
		return err
	}

	state.PatientInfo = result
	log.Printf("[IntakeAgent] success, patient_name=%v", result["name"])
	return nil
}
