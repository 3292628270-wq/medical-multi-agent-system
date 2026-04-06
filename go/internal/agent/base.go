package agent

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/bcefghj/clinical-decision-system/internal/config"
	"github.com/bcefghj/clinical-decision-system/internal/model"
	openai "github.com/sashabaranov/go-openai"
)

// Agent is the interface that all clinical pipeline agents must implement.
type Agent interface {
	Name() string
	Process(ctx context.Context, state *model.ClinicalState) error
}

// callLLM sends a system+user message pair to the OpenAI API and returns
// the raw response content. It strips markdown code fences if present.
func callLLM(ctx context.Context, cfg *config.Config, systemPrompt, userMessage string, temperature float32) (string, error) {
	if cfg.OpenAIAPIKey == "" {
		return "", fmt.Errorf("OPENAI_API_KEY is not configured")
	}

	client := openai.NewClient(cfg.OpenAIAPIKey)

	resp, err := client.CreateChatCompletion(ctx, openai.ChatCompletionRequest{
		Model:       cfg.OpenAIModel,
		Temperature: temperature,
		Messages: []openai.ChatCompletionMessage{
			{Role: openai.ChatMessageRoleSystem, Content: systemPrompt},
			{Role: openai.ChatMessageRoleUser, Content: userMessage},
		},
	})
	if err != nil {
		return "", fmt.Errorf("OpenAI API error: %w", err)
	}

	if len(resp.Choices) == 0 {
		return "", fmt.Errorf("OpenAI returned no choices")
	}

	content := strings.TrimSpace(resp.Choices[0].Message.Content)
	content = stripMarkdownFences(content)
	return content, nil
}

// callLLMJSON calls the LLM and unmarshals the JSON response into dest.
func callLLMJSON(ctx context.Context, cfg *config.Config, systemPrompt, userMessage string, temperature float32, dest interface{}) error {
	raw, err := callLLM(ctx, cfg, systemPrompt, userMessage, temperature)
	if err != nil {
		return err
	}
	if err := json.Unmarshal([]byte(raw), dest); err != nil {
		return fmt.Errorf("JSON parse error: %w (raw response: %.200s)", err, raw)
	}
	return nil
}

func stripMarkdownFences(s string) string {
	s = strings.TrimSpace(s)
	if strings.HasPrefix(s, "```") {
		if idx := strings.Index(s, "\n"); idx >= 0 {
			s = s[idx+1:]
		}
		if idx := strings.LastIndex(s, "```"); idx >= 0 {
			s = s[:idx]
		}
		s = strings.TrimSpace(s)
	}
	return s
}
