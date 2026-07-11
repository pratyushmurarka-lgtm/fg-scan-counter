# FG Scanner Project Workflow & Architecture

This document describes the end-to-end operation, state machine logic, database storage, and reporting architecture of the Finished Goods (FG) Scan Counter & Verification system.

---

## 1. System Overview & Data Flow

The system operates as a real-time event-driven verification loop at the final strapping machine.

```mermaid
sequenceDiagram
    participant Box as FG Box & Proximity Sensor
    participant Scanner as Newland Scanner (COM3)
    participant Backend as Python Backend (fg_scan_counter.py)
    participant DB as Local SQLite (database.db)
    participant UI as Dashboard (fg_scanner.html)

    Box->>Scanner: 1. Blocks Sensor (Trigger)
    Scanner->>Backend: Sends "[START]"
    Backend->>UI: Broadcasts "BOX_PRESENT: True" (UI visual cue)
    
    rect rgb(240, 248, 255)
        note over Scanner, Backend: Case A: Successful Scan
        Scanner->>Backend: Sends Barcode (e.g., "9422")
        Backend->>DB: Queries duplicates & matches product code
        Backend->>DB: Logs scan transaction (isdup=0)
        Backend->>UI: Broadcasts "SCAN_SUCCESS" (Updates UI stats & image)
    end

    rect rgb(255, 235, 235)
        note over Scanner, Backend: Case B: Duplicate Scan
        Scanner->>Backend: Sends Barcode (e.g., "9422")
        Backend->>DB: Queries duplicates (Match found)
        Backend->>DB: Logs duplicate scan (isdup=1)
        Backend->>UI: Broadcasts "SCAN_DUPLICATE" (Rings alarm, red screen)
    end

    Box->>Scanner: 2. Exits Sensor (Clear)
    Scanner->>Backend: Sends "[END]"
    Backend->>UI: Broadcasts "BOX_PRESENT: False"
    
    rect rgb(255, 218, 218)
        note over Backend, UI: Case C: Bypassed Box (No Read)
        Backend->>DB: Logs "NOREAD" transaction
        Backend->>UI: Broadcasts "SCAN_FAILURE" (Full-Screen RED warning, sounds alarm, halts belt)
    end
```

---

## 2. Session State Machine (How Bypassed Boxes are Sensed)

To prevent missed boxes and double-counting, the Python backend tracks the physical state of the strapping machine as a **Read Session**:

1. **Session Start (`[START]`)**:
   * The scanner sensor detects a box blocking the strapping area and sends `[START]` to the virtual COM port.
   * State variables `box_present` is set to `True` and `scanned_this_session` is initialized to `False`.
2. **Scan Window**:
   * If a valid barcode is scanned:
     * System validates against `database.db` for duplicates.
     * Marks `scanned_this_session = True`.
     * Logs the successful transaction.
3. **Session End (`[END]`)**:
   * The box physically leaves the strapping machine, sending `[END]`.
   * **Bypass Detection Rule**: If `scanned_this_session` is still `False`, it means a box passed through the strapping machine without a barcode being read.
     * The system writes a **`NOREAD`** record to the database.
     * Broadcasts `SCAN_FAILURE` to the dashboard, prompting a full-screen red warning, activating the buzzer/alarm, and halting the conveyor belt.

---

## 3. Data Storage & Schema

The data is stored locally in the SQLite database (`database.db`) within the **`inscandata`** table.

### Schema of `inscandata` table:
| Column | Type | Description |
| :--- | :--- | :--- |
| **`id`** | INTEGER | Auto-incrementing primary key |
| **`fgcode`** | TEXT | Resolved Finished Goods code (or `"NOREAD"`/`"DUP"`) |
| **`qrtext`** | TEXT | The raw scanned barcode data |
| **`isdup`** | INTEGER | `0` = Original scan; `1` = Duplicate scan |
| **`scandate`**| DATETIME| Timestamp of the event (local computer time) |
| **`username`**| TEXT | Line Identifier (e.g. `"L04"`) |
| **`scangapsec`**| INTEGER | Time gap (in seconds) between this scan and the previous scan |
| **`prevscandate`**| TEXT | Timestamp of the previous scan |

---

## 4. Reports & Analytics

Reports are provided in two formats:

### A. Real-Time Dashboard UI (Operator)
The operator dashboard (`fg_scanner.html`) calculates and displays the following live:
* **Total Day Count**: Total successful verified scans for today.
* **Scan Gap**: Real-time ticker counting seconds since the last scan (helps detect line stoppages).
* **Current Verification Status**: High-visibility card displaying `VERIFIED`, `DUPLICATE`, `NO READ`, or `WAITING FOR NEXT BOX`.
* **Day Summary Breakdown**: Table categorizing the counts of each product model verified today.
* **Average Hourly Rate**: Displays speed throughput of the line.

### B. Historical Reporting (Supervisors)
Since data is saved in a standard SQLite database, you can export reports using:
1. **Excel / PowerBI Integration**: Connect directly to `database.db` using ODBC drivers to refresh charts.
2. **Custom SQL Exports**: Extract data using command-line scripts. For example, to generate a daily productivity report:
   ```sql
   SELECT fgcode, COUNT(*) as qty 
   FROM inscandata 
   WHERE date(scandate) = date('now') AND fgcode != 'NOREAD' AND isdup = 0
   GROUP BY fgcode;
   ```
3. **No-Read/Audit Report**: List all skipped or bypassed boxes:
   ```sql
   SELECT scandate, username, scangapsec 
   FROM inscandata 
   WHERE fgcode = 'NOREAD';
   ```
