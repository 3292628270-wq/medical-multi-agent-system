package handler

import (
	"net/http"

	"github.com/bcefghj/clinical-decision-system/internal/config"
	"github.com/bcefghj/clinical-decision-system/internal/graph"
	"github.com/bcefghj/clinical-decision-system/internal/model"
	"github.com/bcefghj/clinical-decision-system/internal/service"
	"github.com/gin-gonic/gin"
)

// ClinicalHandler holds dependencies for the HTTP handlers.
type ClinicalHandler struct {
	pipeline *graph.Pipeline
}

// NewClinicalHandler creates a new handler backed by a clinical decision pipeline.
func NewClinicalHandler(cfg *config.Config) *ClinicalHandler {
	return &ClinicalHandler{
		pipeline: graph.NewPipeline(cfg),
	}
}

// RegisterRoutes wires all endpoints onto the provided Gin engine.
func (h *ClinicalHandler) RegisterRoutes(r *gin.Engine) {
	api := r.Group("/api/v1")
	{
		api.POST("/clinical/analyze", h.Analyze)
		api.POST("/clinical/icd10/search", h.SearchICD10)
		api.GET("/clinical/icd10/:code", h.GetICD10)
		api.POST("/clinical/ddi/check", h.CheckDDI)
	}
	r.GET("/health", h.Health)
}

// Analyze runs the full 5-agent clinical decision pipeline.
func (h *ClinicalHandler) Analyze(c *gin.Context) {
	var req model.AnalyzeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	state := &model.ClinicalState{
		RawInput: req.PatientDescription,
	}

	if err := h.pipeline.Run(c.Request.Context(), state); err != nil {
		c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{
		"patient_info":   state.PatientInfo,
		"diagnosis":      state.Diagnosis,
		"treatment_plan": state.TreatmentPlan,
		"coding_result":  state.CodingResult,
		"audit_result":   state.AuditResult,
		"errors":         state.Errors,
	})
}

// --- ICD-10 endpoints ---

type icd10SearchRequest struct {
	Query string `json:"query" binding:"required,min=2"`
}

// SearchICD10 searches ICD-10 codes by text description.
func (h *ClinicalHandler) SearchICD10(c *gin.Context) {
	var req icd10SearchRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	results := service.SearchICD10ByText(req.Query)
	c.JSON(http.StatusOK, gin.H{
		"query":   req.Query,
		"results": results,
		"count":   len(results),
	})
}

// GetICD10 looks up a specific ICD-10 code.
func (h *ClinicalHandler) GetICD10(c *gin.Context) {
	code := c.Param("code")
	result := service.LookupICD10(code)
	if result == nil {
		c.JSON(http.StatusNotFound, gin.H{"error": "ICD-10 code not found: " + code})
		return
	}

	drg := service.GetDRGGroup(code)
	c.JSON(http.StatusOK, gin.H{
		"icd10":     result,
		"drg_group": drg,
	})
}

// --- DDI endpoints ---

type ddiCheckRequest struct {
	NewDrugs     []string `json:"new_drugs" binding:"required,min=1"`
	CurrentDrugs []string `json:"current_drugs"`
}

// CheckDDI checks drug-drug interactions.
func (h *ClinicalHandler) CheckDDI(c *gin.Context) {
	var req ddiCheckRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
		return
	}

	interactions := service.CheckInteractions(req.NewDrugs, req.CurrentDrugs)
	hasMajor := false
	for _, i := range interactions {
		if i.Severity == "major" || i.Severity == "contraindicated" {
			hasMajor = true
			break
		}
	}

	c.JSON(http.StatusOK, gin.H{
		"new_drugs":             req.NewDrugs,
		"current_drugs":        req.CurrentDrugs,
		"interactions":          interactions,
		"interaction_count":     len(interactions),
		"has_major_interaction": hasMajor,
	})
}

// Health returns service health status.
func (h *ClinicalHandler) Health(c *gin.Context) {
	c.JSON(http.StatusOK, model.HealthResponse{
		Status:  "healthy",
		Service: "clinical-decision-system",
		Version: "1.0.0",
	})
}
