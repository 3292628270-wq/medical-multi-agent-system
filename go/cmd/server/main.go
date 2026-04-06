package main

import (
	"log"

	"github.com/bcefghj/clinical-decision-system/internal/config"
	"github.com/bcefghj/clinical-decision-system/internal/handler"
	"github.com/gin-gonic/gin"
)

func main() {
	cfg := config.Load()

	if cfg.OpenAIAPIKey == "" {
		log.Println("WARNING: OPENAI_API_KEY is not set — LLM-based agents will fail")
	}

	r := gin.Default()

	r.Use(func(c *gin.Context) {
		c.Header("Access-Control-Allow-Origin", "*")
		c.Header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
		c.Header("Access-Control-Allow-Headers", "Content-Type, Authorization")
		if c.Request.Method == "OPTIONS" {
			c.AbortWithStatus(204)
			return
		}
		c.Next()
	})

	h := handler.NewClinicalHandler(cfg)
	h.RegisterRoutes(r)

	addr := ":" + cfg.ServerPort
	log.Printf("Clinical Decision System (Go) starting on %s", addr)
	if err := r.Run(addr); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
}
