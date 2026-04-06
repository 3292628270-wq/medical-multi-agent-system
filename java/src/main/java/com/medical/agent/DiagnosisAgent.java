package com.medical.agent;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.medical.model.ClinicalState;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Diagnosis Agent — Generates differential diagnosis from structured patient data.
 * Uses GraphRAG knowledge base when available for evidence-based reasoning.
 */
@Slf4j
@Component
public class DiagnosisAgent {

    private final ChatClient chatClient;
    private final ObjectMapper objectMapper;

    private static final String SYSTEM_PROMPT = """
        You are an expert diagnostician. Given structured patient information, provide a
        comprehensive differential diagnosis as JSON with: primary_diagnosis (disease_name,
        icd10_hint, confidence, evidence array, reasoning), differential_list (array),
        recommended_tests (array), clinical_notes, knowledge_sources, needs_more_info (boolean).
        Confidence scores 0-1. Provide at least 2-3 differentials. Return ONLY valid JSON.
        """;

    public DiagnosisAgent(ChatClient.Builder chatClientBuilder, ObjectMapper objectMapper) {
        this.chatClient = chatClientBuilder.build();
        this.objectMapper = objectMapper;
    }

    public ClinicalState process(ClinicalState state) {
        log.info("DiagnosisAgent processing");
        state.setCurrentAgent("diagnosis");

        if (state.getPatientInfo() == null) {
            state.getErrors().add("No patient info available for diagnosis");
            state.setNeedsMoreInfo(true);
            return state;
        }

        try {
            String patientJson = objectMapper.writeValueAsString(state.getPatientInfo());

            String response = chatClient.prompt()
                    .system(SYSTEM_PROMPT)
                    .user("Patient information:\n\n" + patientJson + "\n\nProvide differential diagnosis.")
                    .call()
                    .content();

            String content = cleanJsonResponse(response);
            Map<String, Object> diagnosis = objectMapper.readValue(content, new TypeReference<>() {});

            Boolean needsMore = (Boolean) diagnosis.remove("needs_more_info");
            state.setDiagnosis(diagnosis);
            state.setNeedsMoreInfo(needsMore != null && needsMore);

            log.info("DiagnosisAgent success, primary: {}",
                    getNestedValue(diagnosis, "primary_diagnosis", "disease_name"));
        } catch (Exception e) {
            log.error("DiagnosisAgent error: {}", e.getMessage());
            state.getErrors().add("Diagnosis error: " + e.getMessage());
            state.setNeedsMoreInfo(false);
        }

        return state;
    }

    @SuppressWarnings("unchecked")
    private Object getNestedValue(Map<String, Object> map, String... keys) {
        Object current = map;
        for (String key : keys) {
            if (current instanceof Map) current = ((Map<String, Object>) current).get(key);
            else return null;
        }
        return current;
    }

    private String cleanJsonResponse(String response) {
        String content = response.trim();
        if (content.startsWith("```")) {
            content = content.substring(content.indexOf('\n') + 1);
            int lastFence = content.lastIndexOf("```");
            if (lastFence >= 0) content = content.substring(0, lastFence).trim();
        }
        return content;
    }
}
