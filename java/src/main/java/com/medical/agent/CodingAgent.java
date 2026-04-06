package com.medical.agent;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.medical.model.ClinicalState;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Coding Agent — ICD-10 automatic coding and DRGs grouping.
 */
@Slf4j
@Component
public class CodingAgent {

    private final ChatClient chatClient;
    private final ObjectMapper objectMapper;

    private static final String SYSTEM_PROMPT = """
        You are a certified medical coding specialist. Given diagnosis and treatment data,
        assign accurate ICD-10-CM codes and DRGs grouping as JSON with: primary_icd10
        (code, description, confidence, category), secondary_icd10_codes (array),
        drg_group (drg_code, description, weight, mean_los), coding_notes,
        coding_confidence. Use most specific ICD-10 codes available. Return ONLY valid JSON.
        """;

    public CodingAgent(ChatClient.Builder chatClientBuilder, ObjectMapper objectMapper) {
        this.chatClient = chatClientBuilder.build();
        this.objectMapper = objectMapper;
    }

    public ClinicalState process(ClinicalState state) {
        log.info("CodingAgent processing");
        state.setCurrentAgent("coding");

        if (state.getDiagnosis() == null) {
            state.getErrors().add("No diagnosis available for coding");
            return state;
        }

        try {
            Map<String, Object> context = Map.of(
                    "diagnosis", state.getDiagnosis(),
                    "treatment_plan", state.getTreatmentPlan() != null ? state.getTreatmentPlan() : Map.of()
            );
            String contextJson = objectMapper.writeValueAsString(context);

            String response = chatClient.prompt()
                    .system(SYSTEM_PROMPT)
                    .user("Clinical data:\n\n" + contextJson + "\n\nAssign ICD-10 codes and DRGs.")
                    .call()
                    .content();

            String content = cleanJsonResponse(response);
            Map<String, Object> coding = objectMapper.readValue(content, new TypeReference<>() {});
            state.setCodingResult(coding);

            log.info("CodingAgent success");
        } catch (Exception e) {
            log.error("CodingAgent error: {}", e.getMessage());
            state.getErrors().add("Coding error: " + e.getMessage());
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
