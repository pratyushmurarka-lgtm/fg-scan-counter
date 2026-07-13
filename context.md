# Project Context: Finished Goods (FG) Scan Counter & Verification System

This repository contains the code and configuration for the Finished Goods (FG) Scan Counter & Verification System, which is used at the final strapping machine stage of water heater production lines to count and verify packages.

## 1. Git Repository Policy
All updates, bug fixes, and feature developments must be pushed exclusively to the following repository:

- **GitHub Repository URL**: `https://github.com/pratyushmurarka-lgtm/fg-scan-counter.git`
- **Branch**: `main`

Ensure your local environment is configured with appropriate Git credentials (e.g., Personal Access Token or SSH keys) to read from and write to this repository without exposing secret tokens in the code.

---

## 2. Core Architecture & Components
The system is built as a lightweight, real-time, event-driven conveyor monitoring loop:

1. **`fg_scan_counter.py`** (Backend Server):
   - Written in Python (standard library only; no heavy dependencies except optional `pyserial`).
   - Runs a multithreaded HTTP Server (default port `5001`) and serves:
     - The operator HTML dashboard (`/` and `/fg_scanner`).
     - A Server-Sent Events (SSE) stream (`/stream`) to broadcast real-time scanner events.
     - A REST API (`/api/items` and `/api/manual_override`) for manual model overrides.
   - Listens to physical barcode scanner inputs on a configurable serial COM port.

2. **`fg_scanner.html`** (Operator Dashboard):
   - A high-visibility, responsive HTML/JS web dashboard designed for a tablet or monitor at the strapping station.
   - Listens to the SSE stream `/stream` and dynamically updates stats (total count, physical count, scan gap timer, average hourly rate, product image).
   - Generates synthesized sound alarms and displays full-screen visual overlays for warnings (`DUPLICATE QR CODE` or `MISSED SCAN / NOREAD`).
   - Provides a sidebar for manually forcing specific brands (Usha / V-Guard) and products.

3. **`simulate_multi_scanner.py`** (Interactive Simulator):
   - A CLI tool to prototype and test the conveyor belt state machine without physical hardware.
   - Runs the HTTP web server in a background thread and prompts for commands (`start <line>`, `scan <line> <qr>`, `end <line>`).

4. **`database.db`** (Local SQLite Database):
   - Stores master product data (`ItemMaster`) and local transaction logs (`inscandata` and `ESJOBSCANDATA`).

---

## 3. Session-Based Conveyor State Machine
To ensure each physical box passing through the strapping machine is correctly verified exactly once, the system uses a **Proximity Sensor Read Session**:

```
[START] (Box blocks sensor) -> [SCAN WINDOW] (Barcode read & validated) -> [END] (Box clears sensor)
```

- **`[START]` Event:** Triggered when a box physically blocks the conveyor sensor. The system initializes `scanned_this_session = False` and sets `box_present = True`.
- **Scan Attempt:** When a barcode is read:
  - Checked for duplicates in `inscandata` (local scans) and `ESJOBSCANDATA` (replicated transactions).
  - If a duplicate is detected $\rightarrow$ system logs it with `isdup = 1`, flashes a yellow/red **Duplicate Alert Overlay** on the dashboard, triggers a buzzer, and stops the belt.
  - If original $\rightarrow$ resolves the product details, records `isdup = 0`, updates stats, displays the product photo, and marks `scanned_this_session = True`.
- **`[END]` Event:** Triggered when the box leaves the strapping area.
  - **Bypass Rule:** If the box left but `scanned_this_session` is still `False`, it implies the box passed through without a scan. The system writes a **`NOREAD`** record to the database, flashes a full-screen **Missed Scan Alert Overlay**, sounds a siren, and stops the belt.

---

## 4. SQLite Schema (`database.db`)
The transaction table **`inscandata`** has the following structure:

| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | INTEGER | Auto-incrementing primary key |
| `fgcode` | TEXT | Resolved Finished Goods item code (e.g. `1062`, `NOREAD`, or `DUP`) |
| `qrtext` | TEXT | Raw scanned barcode serial number |
| `isdup` | INTEGER | `0` = Original scan; `1` = Duplicate scan |
| `scandate` | DATETIME | Timestamp of the scan transaction |
| `username` | TEXT | Conveyor Line Identifier (e.g., `L04`) |
| `scangapsec` | INTEGER | Time gap in seconds since the previous scan |
| `prevscandate`| TEXT | Timestamp of the previous scan |

---

## 5. Deployment & Execution
1. **Physical Setup:** Connect the photoelectric sensor to the scanner's external trigger input. Set the scanner to Level Trigger mode, configuring prefix `[START]` and suffix `[END]`.
2. **Launch Server:**
   ```bash
   python3 fg_scan_counter.py --line <LINE_ID> --port <COM_PORT>
   # Example: python3 fg_scan_counter.py --line L04 --port /dev/tty.usbserial
   ```
3. **Open Dashboard:** Navigate to `http://localhost:5001/fg_scanner?line=L04` on the display device.
