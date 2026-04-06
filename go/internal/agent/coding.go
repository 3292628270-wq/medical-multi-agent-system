package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"github.com/bcefghj/clinical-decision-system/internal/config"
	"github.com/bcefghj/clinical-decision-system/internal/model"
)

const codingSystemPrompt = `You are a certified medical coding specialist (CCS) with expertise in ICD-10-CM and DRGs grouping. Given diagnosis information and treatment details, assign accurate medical codes.

Return a JSON object:
{
  "primary_icd10": {
    "code": "exact ICD-10-CM code (e.g., J18.1)",
    "description": "official code description",
    "confidence": 0.92,
    "category": "category name"
  },
  "secondary_icd10_codes": [
    {
      "code": "ICD-10 code",
      "description": "description",
      "confidence": 0.85,
      "category": "category"
    }
  ],
  "drg_group": {
    "drg_code": "DRG number (e.g., 193)",
    "description": "DRG description",
    "weight": 1.2,
    "mean_los": 4.5
  },
  "coding_notes": "rationale for code selection",
  "coding_confidence": 0.90
}

Rules:
- Use the most specific ICD-10-CM code available (4th-7th character level).
- Primary code should match the principal diagnosis.
- Include comorbidity and complication codes as secondary.
- DRGs weight and mean length of stay should be realistic estimates.
- Confidence reflects how certain the code assignment is.
- Return ONLY valid JSON, no markdown fences.`

// CodingAgent assigns ICD-10 codes and DRGs grouping via LLM.
type CodingAgent struct {
	cfg *config.Config
}

func NewCodingAgent(cfg *config.Config) *CodingAgent {
	return &CodingAgent{cfg: cfg}
}

func (a *CodingAgent) Name() string { return "coding" }

func (a *CodingAgent) Process(ctx context.Context, state *model.ClinicalState) error {
	state.CurrentAgent = a.Name()
	log.Printf("[CodingAgent] start")

	if state.Diagnosis == nil {
		state.Errors = append(state.Errors, "No diagnosis available for coding")
		return fmt.Errorf("no diagnosis available")
	}

	contextData := map[string]interface{}{
		"diagnosis":      state.Diagnosis,
		"treatment_plan": state.TreatmentPlan,
	}
	contextJSON, _ := json.MarshalIndent(contextData, "", "  ")
	userMsg := fmt.Sprintf("Clinical data for coding:\n\n%s\n\nAssign ICD-10 codes and DRGs group.", string(contextJSON))

	var result map[string]interface{}
	if err := callLLMJSON(ctx, a.cfg, codingSystemPrompt, userMsg, 0.1, &result); err != nil {
		state.Errors = append(state.Errors, fmt.Sprintf("Coding error: %v", err))
		return err
	}

	state.CodingResult = result
	if primary, ok := result["primary_icd10"].(map[string]interface{}); ok {
		log.Printf("[CodingAgent] success, primary_code=%v", primary["code"])
	}
	return nil
}
