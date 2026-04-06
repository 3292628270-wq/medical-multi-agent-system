package graph

import (
	"context"
	"fmt"
	"log"

	"github.com/bcefghj/clinical-decision-system/internal/agent"
	"github.com/bcefghj/clinical-decision-system/internal/config"
	"github.com/bcefghj/clinical-decision-system/internal/model"
)

// maxDiagnosisRetries is the maximum number of times the pipeline will loop
// back from Diagnosis to Intake when needs_more_info is true.
const maxDiagnosisRetries = 2

// Pipeline orchestrates the sequential execution of clinical agents with
// conditional routing (Diagnosis -> Intake loop on needs_more_info).
//
// Flow: Intake -> Diagnosis --(needs_more_info?)--> Intake (max 2 retries)
//
//	\--(ready)-----------> Treatment -> Coding -> Audit -> END
type Pipeline struct {
	intake    agent.Agent
	diagnosis agent.Agent
	treatment agent.Agent
	coding    agent.Agent
	audit     agent.Agent
}

// NewPipeline constructs a pipeline with all five clinical agents.
func NewPipeline(cfg *config.Config) *Pipeline {
	return &Pipeline{
		intake:    agent.NewIntakeAgent(cfg),
		diagnosis: agent.NewDiagnosisAgent(cfg),
		treatment: agent.NewTreatmentAgent(cfg),
		coding:    agent.NewCodingAgent(cfg),
		audit:     agent.NewAuditAgent(),
	}
}

// Run executes the full clinical decision pipeline on the given state.
func (p *Pipeline) Run(ctx context.Context, state *model.ClinicalState) error {
	// Step 1: Intake
	if err := p.runAgent(ctx, p.intake, state); err != nil {
		log.Printf("[Pipeline] Intake failed: %v (continuing)", err)
	}

	// Step 2: Diagnosis with conditional routing back to Intake
	retries := 0
	for {
		if err := p.runAgent(ctx, p.diagnosis, state); err != nil {
			log.Printf("[Pipeline] Diagnosis failed: %v (continuing)", err)
			break
		}

		if state.NeedsMoreInfo && retries < maxDiagnosisRetries {
			retries++
			log.Printf("[Pipeline] needs_more_info=true, routing back to Intake (attempt %d/%d)", retries, maxDiagnosisRetries)
			if err := p.runAgent(ctx, p.intake, state); err != nil {
				log.Printf("[Pipeline] Intake retry failed: %v (continuing)", err)
				break
			}
			continue
		}
		break
	}

	// Step 3: Treatment
	if err := p.runAgent(ctx, p.treatment, state); err != nil {
		log.Printf("[Pipeline] Treatment failed: %v (continuing)", err)
	}

	// Step 4: Coding
	if err := p.runAgent(ctx, p.coding, state); err != nil {
		log.Printf("[Pipeline] Coding failed: %v (continuing)", err)
	}

	// Step 5: Audit (pure rule engine, should not fail)
	if err := p.runAgent(ctx, p.audit, state); err != nil {
		log.Printf("[Pipeline] Audit failed: %v", err)
	}

	log.Printf("[Pipeline] completed, errors=%d", len(state.Errors))
	return nil
}

func (p *Pipeline) runAgent(ctx context.Context, a agent.Agent, state *model.ClinicalState) error {
	log.Printf("[Pipeline] running agent: %s", a.Name())
	if err := a.Process(ctx, state); err != nil {
		return fmt.Errorf("agent %s: %w", a.Name(), err)
	}
	return nil
}
