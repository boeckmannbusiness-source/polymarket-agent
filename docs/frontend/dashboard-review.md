# UX Simplification Pass: Trading Dashboard

## Overview
The goal of this pass is to reduce cognitive load and improve operator decision speed by consolidating redundant status indicators and clarifying the system's "single source of truth."

## Component Analysis

### 1. SystemHealthHeader (Consolidated)
- **Status:** Currently functional but lacks critical details.
- **Role:** Primary status bar.
- **Improvement:** Integrate manual override status, TTL for overrides, and the "Primary Driver" from the `PrimarySignal` component.

### 2. ModeInspector
- **Status:** Redundant.
- **Role:** Shows mode details and overrides.
- **Improvement:** Retire. All essential information (Mode, Override, TTL) will move to the `SystemHealthHeader`.

### 3. InstabilityIndicator
- **Status:** Redundant and visually heavy.
- **Role:** High-level health score.
- **Improvement:** Retire. The `SystemHealthHeader` and `PrimarySignal` logic already cover the score and state.

### 4. PrimarySignal
- **Status:** Redundant layout.
- **Role:** Identifies the main cause of instability.
- **Improvement:** Retire as a standalone block. Move the "Primary Driver" text into a second line or tooltip in the `SystemHealthHeader`.

### 5. SystemNarrative
- **Status:** Redundant.
- **Role:** One-sentence explanation.
- **Improvement:** Retire. This text is already partially present in the `SystemHealthHeader`.

### 6. DecisionBanner
- **Status:** High Value.
- **Role:** Concrete action guidance.
- **Improvement:** Keep. Refine styling to ensure it stands out as the "next step" without competing with the header.

### 7. Metrics & Timeline Panels
- **Status:** High Value (Secondary).
- **Role:** Deep-dive analysis.
- **Improvement:** Keep collapsed in `details` tags to stay out of the "fast path" but remain accessible for incident review.

## Implementation Plan
1.  **Refactor `SystemHealthHeader`**:
    - Add `is_manual_override` and `ttl_seconds` display.
    - Enhance the narrative/explanation area to include the "Primary Driver" from `PrimarySignal`.
2.  **Update `page.tsx`**:
    - Remove `SystemNarrative` and `PrimarySignal`.
    - Ensure the layout flows from **State** (Header) -> **Action** (Decision Banner) -> **Reasoning** (Details).
3.  **Cleanup**:
    - Delete `ModeInspector.tsx`, `InstabilityIndicator.tsx`, `SystemNarrative.tsx`, and `PrimarySignal.tsx`.
