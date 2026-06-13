# PRD: Visual Stage Grouping and Alignment in Model Allocation Panel

## Problem Statement

From the user's perspective, the current model allocation panel displays model override selectors as a flat, sequentially numbered list (numbered 1 to 5 for primary tasks, and 6 to 8 for fallback models). This layout is misleading and confusing because these steps do not execute in that exact sequential order. Rather, the NewsAgent pipeline operates in distinct, logical stages: **News Pre-processing** (Stage 1), **AI Analysis** (Stage 2), and a shared **Vector Indexing Service**. 

Users need a clearer visual structure that groups the primary models with their corresponding fallback models by pipeline stage, aligning directly with the news processing pipeline's logical stages.

## Solution

Refactor the model override selector form inputs in the frontend settings card (`ModelQuotasTab`) to structure them into visually grouped, color-coded stage blocks matching the flowchart visualization at the top of the tab:
1. **Stage 1: Pre-processing Models** (subtle indigo border & background): Contains the Relevance Filter Model and its cheap failover Lightweight Fallback Model.
2. **Stage 2: AI Analysis Models** (subtle violet border & background): Contains the Summarization, Classification, and Deep Analysis Task Models, along with their powerful failover Reasoning Fallback Model.
3. **Shared: Vector Indexing Service** (subtle emerald border & background): Contains the Primary Embedding Model and its Fallback Embedding Model.
4. **Pacing & Safety Controls** (subtle muted border & background): Contains spend limit, pacing delay, max analysis duration, and analysis batch size controls.

This resolves the misleading sequential numbers and groups primary models and their respective fallbacks together under their respective stages.

## User Stories

1. As an administrator configuring model settings, I want to see the model overrides grouped by the logical stages of the NewsAgent pipeline (Pre-processing, AI Analysis, and Vector Indexing), so that I can easily understand which model applies to which part of the workflow.
2. As an administrator, I want primary models and their corresponding fallback models to be grouped in the same visual container, so that I can manage primary and failover models for each stage in a single place instead of scanning two separate lists.
3. As an administrator, I want the sequential numbering (e.g., 1 to 8) to be removed from labels and code comments, so that I am not misled into thinking all models are executed in a strict sequential order.
4. As an administrator, I want the color coding of the configuration sections to match the pipeline flowchart visualizer, so that the page feels cohesive and intuitive.

## Implementation Decisions

- **Settings Component Refactoring**: Modify the model allocation configuration form in the settings page dashboard (`ModelQuotasTab`).
- **Visual Grouping**: Reorganize the select dropdown inputs and their custom text inputs into four styled sections:
  - Stage 1: Pre-processing Models
  - Stage 2: AI Analysis Models
  - Shared: Vector Indexing Service
  - Pacing & Safety Controls
- **Translucent Borders and Backgrounds**: Style each section container with a colored left-border (indigo, violet, emerald, and muted) and a subtle matching translucent background to match the design tokens of the settings flowchart.
- **Label Cleanups**: Remove leading numbers from select input labels (e.g. `Relevance Filter Model` instead of `1. Relevance Filter Model`) and update inline comments.
- **Flat Payload Preservation**: Ensure that the PUT payload sent to the backend remains a flat object containing all settings fields, maintaining 100% compatibility with the existing API.

## Testing Decisions

- **Visual Verification**: Verify that the settings tab renders the new grouped layout correctly in the browser without any overlapping styles or spacing issues.
- **Unit Tests**: Update the existing Vitest unit tests in `model-quotas.test.tsx` to verify that all form elements, labels, and the submit button remain fully functional under the new visual grouping.
- **Payload Correctness**: Verify that submitting the form still puts the correct flat JSON payload to the backend FastAPI system route.

## Out of Scope

- Backend database schema migrations or config schema changes.
- Modifying the scheduler background job logic or changing how fallback models are loaded/invoked in Python.
- Adding new model parameters or additional configuration options beyond the existing ones.

## Further Notes

- The React compiler is enabled, so no manual hooks optimization is needed.
- Make sure that Tailwind CSS v4 class nesting and alignment rules are respected.
