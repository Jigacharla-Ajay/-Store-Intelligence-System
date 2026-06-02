# Dashboard Implementation Plan (Phase 7)

This plan details the construction of the real-time React dashboard to visualize the Purplle Store Intelligence System's metrics, funnels, heatmaps, and anomalies.

## Goal
Build a modern, premium, responsive React (Vite) application that connects to our FastAPI backend via REST and WebSockets to provide a live operational view of the store.

> [!IMPORTANT]  
> User Review Required: I will proceed with standard CSS (no Tailwind) to ensure maximum flexibility and adherence to the system prompts unless you specifically request Tailwind. The design will feature a premium dark mode aesthetic with Purplle's brand colors (purples/pinks), glassmorphism, and micro-animations.

## Design Mockup
Here is a visual mockup of the premium aesthetic we are targeting for the dashboard:
![Purplle Dashboard Mockup](C:\Users\jigac\.gemini\antigravity\brain\6bd9a79c-3906-4946-9a0b-5d20e2fe745a\purplle_dashboard_mockup_1780246770277.png)

## Proposed Changes

### 1. Project Initialization
- Scaffold a new Vite + React project in the `dashboard/` directory.
- Install necessary dependencies: `lucide-react` (icons), `recharts` (charts), and `clsx` (utility).

### 2. Core Infrastructure
#### [NEW] `dashboard/src/services/api.js`
- Functions to fetch initial data (metrics, funnel, heatmap, anomalies, health).
#### [NEW] `dashboard/src/hooks/useStoreData.js`
- A custom hook to manage the WebSocket connection to `ws://localhost:8000/ws/stores/{store_id}`.
- Handles incoming messages (`EVENT`, `ANOMALY`, `METRICS_UPDATE`) and merges them with the initial state.

### 3. UI Components & Layout
#### [NEW] `dashboard/src/App.jsx` & `index.css`
- Main layout wrapper with a premium dark theme.
- CSS variables for the color palette, typography (Inter font), and glassmorphism utilities.

#### [NEW] `dashboard/src/components/Header.jsx`
- Displays store name, current date/time, and a live WebSocket connection status indicator.

#### [NEW] `dashboard/src/components/MetricsGrid.jsx`
- KPI cards for: Unique Visitors, Total Entries, Conversion Rate, Avg Dwell Time, and Current Queue Depth.

#### [NEW] `dashboard/src/components/FunnelChart.jsx`
- Visualizes the 4-stage conversion funnel (STORE_ENTRY -> ZONE_VISIT -> BILLING_REACH -> PURCHASE) with drop-off percentages.

#### [NEW] `dashboard/src/components/ZoneHeatmap.jsx`
- Visual representation of the store zones with color intensity based on `visit_score` and `dwell_score` (0-100).

#### [NEW] `dashboard/src/components/AnomalyFeed.jsx`
- A live feed of active anomalies (e.g., DEAD_ZONE, STALE_FEED) categorized by severity (INFO, WARN, CRITICAL).

## Verification Plan

### Automated / API Tests
- The backend API and WebSocket endpoints are already verified via the Python test suite.

### Manual Verification
1. Start the FastAPI backend.
2. Start the Vite dev server (`npm run dev`).
3. Verify that the dashboard loads the initial state via REST APIs.
4. Run the detection pipeline (`python -m pipeline.run`) to simulate live events.
5. Verify that the dashboard UI updates in real-time via WebSockets without requiring a page refresh.
6. Check the design aesthetics (dark mode, glassmorphism, animations) to ensure a premium look.
