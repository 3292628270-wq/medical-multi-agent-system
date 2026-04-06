package com.medical.agent;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.medical.model.ClinicalState;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Treatment Agent — Generates evidence-based treatment plans with drug interaction checks.
 */
@Slf4j
@Component
public class TreatmentAgent {

    private final ChatClient chatClient;
    private final ObjectMapper objectMapper;

    private static final String SYSTEM_PROMPT = """
        You are an expert clinical pharmacologist. Given diagnosis and patient data, provide
        a treatment plan as JSON with: diagnosis_addressed, medications (array with drug_name,
        generic_name, dosage, route, frequency, duration, contraindications, side_effects),
        drug_interactions (array with drug_a, drug_b, severity, description, recommendation),
        non_drug_treatments, lifestyle_recommendations, follow_up_plan, warnings,
        evidence_references. Check current medications for interactions. Return ONLY valid JSON.
        """;

    public TreatmentAgent(ChatClient.Builder chatClientBuilder, ObjectMapper objectMapper) {
        this.chatClient = chatClientBuilder.build();
        this.objectMapper = objectMapper;
    }

    public ClinicalState process(ClinicalState state) {
        log.info("TreatmentAgent processing");
        state.setCurrentAgent("treatment");

        if (state.getDiagnosis() == null) {
            state.getErrors().add("No diagnosis available for treatment planning");
            return state;
        }

        try {
            Map<String, Object> context = Map.of(
                    "patient_info", state.getPatientInfo() != null ? state.getPatientInfo() : Map.of(),
                    "diagnosis", state.getDiagnosis()
            );
            String contextJson = objectMapper.writeValueAsString(context);

            String response = chatClient.prompt()
                    .system(SYSTEM_PROMPT)
                    .user("Clinical context:\n\n" + contextJson + "\n\nProvide treatment plan.")
                    .call()
                    .content();

            String content = cleanJsonResponse(response);
            Map<String, Object> treatment = objectMapper.readValue(content, new TypeReference<>() {});
            state.setTreatmentPlan(treatment);

            log.info("TreatmentAgent success");
        } catch (Exception e) {
            log.error("TreatmentAgent error: {}", e.getMessage());
            state.getErrors().add("Treatment error: " + e.getMessage());
        }

        return state;
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
