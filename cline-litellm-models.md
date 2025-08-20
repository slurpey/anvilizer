# Cline LiteLLM Model Names

This document provides a comprehensive list of LiteLLM model names available for use with Cline, specifically focusing on SAP GenAI models.

## Overview

These model names are used to configure LiteLLM for integration with Cline. All models listed below use the `sapgenai-` prefix, indicating they are part of SAP's GenAI offering.

## Available Models

### Claude Models (Anthropic)

| Model Name                   | Description                                          |
|------------------------------|------------------------------------------------------|
| `sapgenai-claude-4-opus`     | Claude 4 Opus - Latest flagship model with superior performance |
| `sapgenai-claude-4-sonnet`   | Claude 4 Sonnet - Balanced performance and speed     |
| `sapgenai-claude-3.7-sonnet` | Claude 3.7 Sonnet - Enhanced version of Claude 3.5   |
| `sapgenai-claude-3.5-sonnet` | Claude 3.5 Sonnet - Popular balanced model           |

### Gemini Models (Google)

| Model Name                   | Description                                          |
|------------------------------|------------------------------------------------------|
| `sapgenai-gemini-2.5-flash`  | Gemini 2.5 Flash - Fast inference optimized model    |
| `sapgenai-gemini-2.5-pro`    | Gemini 2.5 Pro - Professional grade model with enhanced capabilities |

### GPT Models (OpenAI)

| Model Name                 | Description                                |
|----------------------------|--------------------------------------------|
| `sapgenai-gpt-4.1`         | GPT-4.1 - Latest iteration of GPT-4        |
| `sapgenai-gpt-4.1-mini`    | GPT-4.1 Mini - Lightweight version of GPT-4.1 |

### O-Series Models (OpenAI)

| Model Name             | Description                      |
|------------------------|----------------------------------|
| `sapgenai-o3`          | O3 - Advanced reasoning model    |
| `sapgenai-o4-mini`     | O4 Mini - Compact version of O4 model |

### Embedding Models

| Model Name                       | Description                          |
|----------------------------------|--------------------------------------|
| `sapgenai-text-embedding-3-small`| Text Embedding 3 Small - Compact embedding model |
| `sapgenai-text-embedding-3-large`| Text Embedding 3 Large - Large-scale embedding model |

---

## Usage in Cline

To use these models with Cline:

1. Configure your LiteLLM setup with the appropriate SAP GenAI credentials
2. Use any of the model names listed above in your Cline configuration
3. Ensure proper authentication and access permissions are set up for SAP GenAI services

---

## Model Categories

### Chat/Completion Models
- All Claude models (4-opus, 4-sonnet, 3.7-sonnet, 3.5-sonnet)
- All Gemini models (2.5-flash, 2.5-pro)
- All GPT models (4.1, 4.1-mini)
- All O-series models (o3, o4-mini)

### Embedding Models
- `sapgenai-text-embedding-3-small`
- `sapgenai-text-embedding-3-large`

---

## Cline Plan & Act Model Pairings Cheat Sheet

| Price Level     | Plan Model                         | Act Model                          | Notes                                              |
|-----------------|------------------------------------|------------------------------------|----------------------------------------------------|
| Cheapest Pair   | sapgenai-o3 / sapgenai-o4-mini     | sapgenai-o3 / sapgenai-o4-mini     | Fast, for small/bulk jobs, lowest cost             |
| Good Pair       | sapgenai-gemini-2.5-pro            | sapgenai-gpt-4.1                   | Handles bigger files and most work reliably        |
| Expensive Pair  | sapgenai-claude-4-opus             | sapgenai-claude-4-opus             | For big changes, deep code reasoning, highest cost |

- Use Claude models (`-opus`) only when you need strongest planning or most reliable edits.
- Prefer Gemini Pro + GPT-4.1 for good balance on day-to-day usage.
- O3/O4-mini are best for prototypes, bulk changes, or when cost is critical.

---

## Notes

- All models require proper SAP GenAI authentication
- Model availability may vary based on your SAP GenAI subscription
- Performance and capabilities may differ between model variants
- Embedding models are specifically designed for text embedding tasks, not chat completion

---

## Last Updated

Document created: January 2025  
Cheat Sheet updated: August 2025
