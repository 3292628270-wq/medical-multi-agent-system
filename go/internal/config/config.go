package config

import "os"

// Config holds all application configuration loaded from environment variables.
type Config struct {
	OpenAIAPIKey string
	OpenAIModel  string
	ServerPort   string
	PostgresDSN  string
	Neo4jURI     string
	RedisAddr    string
}

// Load reads configuration from environment variables with sensible defaults.
func Load() *Config {
	return &Config{
		OpenAIAPIKey: getEnv("OPENAI_API_KEY", ""),
		OpenAIModel:  getEnv("OPENAI_MODEL", "gpt-4o-mini"),
		ServerPort:   getEnv("SERVER_PORT", "8090"),
		PostgresDSN:  getEnv("POSTGRES_DSN", "postgres://postgres:postgres@localhost:5432/clinical_decision"),
		Neo4jURI:     getEnv("NEO4J_URI", "bolt://localhost:7687"),
		RedisAddr:    getEnv("REDIS_ADDR", "localhost:6379"),
	}
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
