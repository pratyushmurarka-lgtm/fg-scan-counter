# Agent Rules & Guidelines

## Web App Updates & Cache-Busting
* Ensure web app assets are updated with cache-busting version queries to avoid stale browser cache issues.

### Single-Instance Module Version Alignment
* **Context**: When importing Javascript modules (like database managers, state adapters, or auth utilities) that execute background sync loops, register intervals, or write to shared browser storage (localStorage, IndexedDB), having different view files import different cache-buster query version strings (e.g. `db.js?v=83` vs `db.js?v=96`) causes the browser to load and execute multiple distinct instances of the module concurrently in the same session.
* **Instruction**: Whenever you modify a core shared module or database manager script:
  1. Run a repository-wide search to locate all import references to that file.
  2. You MUST update every single import statement across all scripts/views to reference the exact same version query string (e.g. `db.js?v=XX`).
  3. Ensure no stale imports are left running concurrently in the background.

## MANDATORY 7-LAYER DIGGING SOP PROTOCOL

Adhere strictly to the 7-Layer Digging SOP Protocol for all diagnostics, development, refactoring, and code audits. Never implement patches based on superficial errors or assumptions.

### 1. Mandatory Global Symbol Search (Grep-on-Edit)
Before modifying any HTML element ID, CSS class, variable name, function signature, or API route in any file:
- You **MUST** run a global codebase search (`grep_search`) across the entire repository.
- You **MUST** list all consumer files and line numbers found before editing the target file.

### 2. Full 7-Layer Pipeline Trace
For any feature or bug investigation, do not edit code in a single file silo. You **MUST** explicitly trace all 7 layers of the pipeline in order:
1. **HTML DOM Element**: Verify ID, attribute, and visibility in `index.html` (or `fg_scanner.html`).
2. **JS DOM Selector**: Verify `document.getElementById` (or similar selector) matches the exact HTML ID.
3. **JS Event Listener**: Verify listener is attached and `preventDefault()` or key event data is correctly handled.
4. **API Request Payload**: Verify the exact JSON payload structure sent via `fetch()` / AJAX.
5. **Server Endpoint & SQL**: Verify backend request parsing, routing, SQL query, and database column names.
6. **API Response Schema**: Verify side-by-side that exact key names returned by the backend match the exact key names read by the frontend (e.g. `resData.daily_data` vs `resData.data`). Never assume property names match!
7. **UI Render & Storage**: Verify state persistence (`localStorage`/`sessionStorage`) and DOM updates/rendering.

### 3. Data Schema Mirror Verification
When inspecting API communication, view both sides of the network boundary side-by-side:
- **Server Side**: The exact dictionary/JSON keys returned in the HTTP response.
- **Client Side**: The exact property names read by the JavaScript client.
Never assume property names match without inspecting both source lines side-by-side.

### 4. Multi-Bug Exhaustion Rule (Never Stop at Bug #1)
Locating a single syntax error or obvious bug is **NEVER** a reason to conclude an investigation. Assume at least 3 independent errors exist across different layers (DOM, JS, Server, Database, Cache) and complete the entire 7-layer audit loop.

### 5. Static Cache & Infrastructure Delivery Verification
When editing static frontend files (`.js`, `.html`, `.css`), verify that the web server sends appropriate `Cache-Control: no-cache` headers (or similar config) to prevent mobile browsers and PWAs from executing stale, disk-cached files.

### 6. Empirical Verification Requirement
No task can be declared complete based on syntax compilation or static code inspection alone. You **MUST** demonstrate empirical end-to-end runtime verification output proving that all 7 layers execute cleanly.
