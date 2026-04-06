package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/bcefghj/clinical-decision-system/internal/config"
	"github.com/bcefghj/clinical-decision-system/internal/model"
)

const treatmentSystemPrompt = `You are an expert clinical pharmacologist and treatment specialist. Given a patient's diagnosis and clinical data, provide a comprehensive, evidence-based treatment plan.

Return a JSON object:
{
  "diagnosis_addressed": "the primary diagnosis being treated",
  "medications": [
    {
      "drug_name": "brand name",
      "generic_name": "generic name",
      "dosage": "e.g., 500mg",
      "route": "oral|iv|im|topical|etc",
      "frequency": "e.g., twice daily",
      "duration": "e.g., 7 days",
      "contraindications": ["list any relevant"],
      "side_effects": ["common side effects"]
    }
  ],
  "drug_interactions": [
    {
      "drug_a": "drug 1",
      "drug_b": "drug 2 (can be current medication)",
      "severity": "none|minor|moderate|major|contraindicated",
      "description": "interaction details",
      "recommendation": "what to do"
    }
  ],
  "non_drug_treatments": ["physical therapy", "dietary changes", "etc."],
  "lifestyle_recommendations": ["exercise", "sleep hygiene", "etc."],
  "follow_up_plan": "when and what to check",
  "warnings": ["critical warnings for this treatment"],
  "evidence_references": ["guideline or study reference"]
}

Rules:
- ALWAYS check the patient's current medications for interactions.
- ALWAYS check allergies before recommending any drug.
- Flag any major or contraindicated interactions prominently.
- Provide at least one non-drug treatment option.
- Return ONLY valid JSON, no markdown fences.`

// TreatmentAgent generates evidence-based treatment plans via LLM.
type TreatmentAgent struct {
	cfg *config.Config
}

func NewTreatmentAgent(cfg *config.Config) *TreatmentAgent {
	return &TreatmentAgent{cfg: cfg}
}

func (a *TreatmentAgent) Name() string { return "treatment" }

func (a *TreatmentAgent) Process(ctx context.Context, state *model.ClinicalState) error {
	state.CurrentAgent = a.Name()
	log.Printf("[TreatmentAgent] start")

	if state.Diagnosis == nil {
		state.Errors = append(state.Errors, "No diagnosis available for treatment planning")
		return fmt.Errorf("no diagnosis available")
	}

	contextData := map[string]interface{}{
		"patient_info": state.PatientInfo,
		"diagnosis":    state.Diagnosis,
	}
	contextJSON, _ := json.MarshalIndent(contextData, "", "  ")
	userMsg := fmt.Sprintf("Clinical context:\n\n%s\n\nProvide a comprehensive treatment plan with drug interaction checks.", string(contextJSON))

	var result map[string]interface{}
	if err := callLLMJSON(ctx, a.cfg, treatmentSystemPrompt, userMsg, 0.2, &result); err != nil {
		state.Errors = append(state.Errors, fmt.Sprintf("Treatment error: %v", err))
		return err
	}

	state.TreatmentPlan = result
	if meds, ok := result["medications"].([]interface{}); ok {
		log.Printf("[TreatmentAgent] success, medications_count=%d", len(meds))
	}
	return nil
}
