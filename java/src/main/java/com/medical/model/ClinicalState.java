package com.medical.model;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Shared state flowing through the LangGraph4j clinical pipeline.
 * Each agent reads specific fields and writes its output.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class ClinicalState {

    /** Raw patient description text input */
    @Builder.Default
    private String rawInput = "";

    /** Structured patient info (from Intake Agent) */
    private Map<String, Object> patientInfo;

    /** Differential diagnosis result (from Diagnosis Agent) */
    private Map<String, Object> diagnosis;

    /** Whether diagnosis agent needs more information */
    @Builder.Default
    private boolean needsMoreInfo = false;

    /** Treatment plan (from Treatment Agent) */
    private Map<String, Object> treatmentPlan;

    /** ICD-10 / DRGs coding result (from Coding Agent) */
    private Map<String, Object> codingResult;

    /** HIPAA compliance audit result (from Audit Agent) */
    private Map<String, Object> auditResult;

    /** Name of currently executing agent */
    @Builder.Default
    private String currentAgent = "";

    /** Errors accumulated during pipeline execution */
    @Builder.Default
    private List<String> errors = new ArrayList<>();
}
