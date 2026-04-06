package com.medical.controller;

import com.medical.graph.ClinicalPipeline;
import com.medical.model.ClinicalState;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@RestController
@RequestMapping("/api/v1/clinical")
public class ClinicalController {

    private final ClinicalPipeline pipeline;

    public ClinicalController(ClinicalPipeline pipeline) {
        this.pipeline = pipeline;
    }

    @PostMapping("/analyze")
    public ResponseEntity<ClinicalState> analyze(@Valid @RequestBody AnalyzeRequest request) {
        ClinicalState result = pipeline.invoke(request.getPatientDescription());
        return ResponseEntity.ok(result);
    }

    @GetMapping("/health")
    public ResponseEntity<Map<String, String>> health() {
        return ResponseEntity.ok(Map.of(
                "status", "healthy",
                "service", "clinical-decision-system-java",
                "version", "1.0.0"
        ));
    }

    @Data
    public static class AnalyzeRequest {
        @NotBlank(message = "Patient description is required")
        @Size(min = 10, message = "Description must be at least 10 characters")
        private String patientDescription;
    }
}
