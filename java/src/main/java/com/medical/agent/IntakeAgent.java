package com.medical.agent;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.medical.model.ClinicalState;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Intake Agent — Extracts structured patient information from raw clinical text.
 *
 * Input:  state.rawInput (free-text patient narrative)
 * Output: state.patientInfo (structured JSON)
 */
@Slf4j
@Component
public class IntakeAgent {

    private final ChatClient chatClient;
    private final ObjectMapper objectMapper;

    private static final String SYSTEM_PROMPT = """
        You are an expert medical intake specialist. Extract structured patient information
        from the clinical narrative as a JSON object with fields: name, age, gender,
        chief_complaint, symptoms (array), medical_history (array), allergies (array),
        current_medications (array), vital_signs (object), lab_results (array).
        Return ONLY valid JSON, no markdown fences.
        """;

    public IntakeAgent(ChatClient.Builder chatClientBuilder, ObjectMapper objectMapper) {
        this.chatClient = chatClientBuilder.build();
        this.objectMapper = objectMapper;
    }

    public ClinicalState process(ClinicalState state) {
        log.info("IntakeAgent processing, input length: {}", state.getRawInput().length());
        state.setCurrentAgent("intake");

        if (state.getRawInput() == null || state.getRawInput().isBlank()) {
            state.getErrors().add("No raw input provided to Intake Agent");
            return state;
        }

        try {
            String response = chatClient.prompt()
                    .system(SYSTEM_PROMPT)
                    .user("Patient narrative:\n\n" + state.getRawInput())
                    .call()
                    .content();

            String content = cleanJsonResponse(response);
            Map<String, Object> patientInfo = objectMapper.readValue(
                    content, new TypeReference<>() {});

            state.setPatientInfo(patientInfo);
            log.info("IntakeAgent success, patient: {}", patientInfo.getOrDefault("name", "Unknown"));
        } catch (Exception e) {
            log.error("IntakeAgent error: {}", e.getMessage());
            state.getErrors().add("Intake error: " + e.getMessage());
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
