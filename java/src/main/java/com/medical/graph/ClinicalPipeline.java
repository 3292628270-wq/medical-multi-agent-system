package com.medical.graph;

import com.medical.agent.*;
import com.medical.model.ClinicalState;
import org.springframework.stereotype.Component;

/**
 * LangGraph4j-style pipeline orchestrator for the 5-agent clinical workflow.
 *
 * Pipeline flow:
 *   Intake -> Diagnosis --(needs more info?)--> Intake (loop)
 *                       \--(ready)-----------> Treatment -> Coding -> Audit
 *
 * In a full LangGraph4j integration, this would use StateGraph<ClinicalState>.
 * This implementation demonstrates the pattern with direct method chaining.
 */
@Component
public class ClinicalPipeline {

    private final IntakeAgent intakeAgent;
    private final DiagnosisAgent diagnosisAgent;
    private final TreatmentAgent treatmentAgent;
    private final CodingAgent codingAgent;
    private final AuditAgent auditAgent;

    private static final int MAX_DIAGNOSIS_RETRIES = 2;

    public ClinicalPipeline(
            IntakeAgent intakeAgent,
            DiagnosisAgent diagnosisAgent,
            TreatmentAgent treatmentAgent,
            CodingAgent codingAgent,
            AuditAgent auditAgent) {
        this.intakeAgent = intakeAgent;
        this.diagnosisAgent = diagnosisAgent;
        this.treatmentAgent = treatmentAgent;
        this.codingAgent = codingAgent;
        this.auditAgent = auditAgent;
    }

    /**
     * Execute the full clinical decision pipeline.
     *
     * @param rawInput Raw patient description text
     * @return Final ClinicalState with all agent outputs
     */
    public ClinicalState invoke(String rawInput) {
        ClinicalState state = ClinicalState.builder()
                .rawInput(rawInput)
                .build();

        // Step 1: Intake
        state = intakeAgent.process(state);

        // Step 2: Diagnosis (with retry loop if more info needed)
        int retries = 0;
        do {
            state = diagnosisAgent.process(state);
            if (state.isNeedsMoreInfo() && retries < MAX_DIAGNOSIS_RETRIES) {
                state = intakeAgent.process(state);
            }
            retries++;
        } while (state.isNeedsMoreInfo() && retries <= MAX_DIAGNOSIS_RETRIES);

        // Step 3: Treatment
        state = treatmentAgent.process(state);

        // Step 4: Coding
        state = codingAgent.process(state);

        // Step 5: Audit
        state = auditAgent.process(state);

        return state;
    }
}
