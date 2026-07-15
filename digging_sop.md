# Digging Standard Operating Procedure (SOP)

This document outlines the mandatory behavioral standards for all diagnoses, development tasks, and bug fixes on the Finished Goods (FG) Scan Counter & Verification System.

Every corrective action and system change MUST be formulated, executed, and verified strictly based on these steps. Do not skip any phase or implement hotfixes on assumptions.

---

## 1. Detailed Diagnostics Phase
* **Investigate Root Causes**: Trace the codebase, raw logs, database schemas, and data rows to find the true, underlying cause of a failure.
* **No Assumptions**: Never write code or propose fixes based on assumptions or superficial symptoms. Verify constraints (e.g. data types, connection limits, and null states) beforehand.

## 2. Historical & Regression Analysis
* **Inspect Git History**: Before editing, use Git logs (e.g., `git log -S "<symbol_or_keyword>"` or `git log -p`) to understand why existing code was written.
* **Prevent Regressions**: Ensure your changes do not overwrite, downgrade, or duplicate prior fixes, business logic transitions, or data synchronization rules.

## 3. Bulletproof Engineering Design
* **Edge-case Tolerance**: Gracefully handle null states, missing configuration keys, type mismatches, empty API responses, and database schema constraints.
* **Concurrency & Persistence**: Ensure changes are safe under concurrent client operations and persistent across system restarts.

## 4. Multi-Environment & Adverse Testing
* **Stressed Simulations**: Write automated mock scripts (placed in a `scratch/` directory) to simulate off-nominal inputs, data bloat, network timeouts, and load spikes.
* **Offline/Fallback Safety**: Validate that updates do not break local fallback configurations (like local offline database syncs or client caches).

## 5. Traceability and Tracking
* Maintain clear logs of what changed and why. Create or update living documentation (such as implementation plans, task check-lists, and verification walkthroughs) to record technical decisions and manual validation flows.

## 6. Full System Functioning Verification (Post-Change SOP)
Before committing and deploying any change, you must perform full end-to-end verification of all subsystems to guarantee zero regressions. You must check:
* **Backend Verification**: Execute script-based integration tests to ensure that database queries, API endpoints, web server routes, and messaging protocols are functioning properly.
* **Frontend Verification**: Run client-side syntax checks (such as brace-matching, quote-balancing, and syntax parser scripts) on all modified frontend JavaScript files to catch browser runtime parse crashes before they hit production.
* **Subsystem Safety**: Verify that adjacent components (e.g. daily schedulers, data synchronization hooks, background threads, and permissions systems) are completely uncorrupted.
