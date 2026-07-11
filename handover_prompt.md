# Project Handover: Python FG Scan Counter & Verification System

This document serves as the context transfer prompt for the next AI Agent on the new PC.

---

## 📋 Context & Project Overview
We are building a **Python-based Finished Goods (FG) Scan Counter & Verification system** for water heater production lines. The system runs at the final strapping machine stage where boxes physically stop to get strapped. 

### Core Components:
1. **`fg_scan_counter.py`**: A multi-threaded Python backend. It listens to scanner inputs (serial/COM ports or TCP/IP sockets), handles session state logic, queries a local database (`ItemMaster`) for duplicates and details, and broadcasts real-time events via an SSE (Server-Sent Events) web server on port `5001`.
2. **`fg_scanner.html`**: A high-visibility web display dashboard for the operator. Shows live counts, hourly averages, current status (VERIFIED, DUPLICATE, NO READ), a recent scans grid, a manual select panel, and product photos.
3. **`simulate_multi_scanner.py`**: An interactive CLI tool used to test and simulate scanner/proximity sensor events (box entry, scan, exit).
4. **`database.db`**: SQLite database containing replication tables (`ItemMaster`, `ESJOBSCANDATA`) for local lookups and scan counters.

---

## ⚙️ How the Session-Based Verification Works
To avoid double-counting on scan retries, we track the proximity sensor's state as a **Read Session**:
1. When a box blocks the sensor $\rightarrow$ The scanner triggers and sends **`[START]`**.
2. During the session $\rightarrow$ Barcodes are read (e.g. `9422`). If V-Guard/Usha is active, the system skips auto-detection and logs under the pre-selected model, cleaning V-Guard strings to digits-only.
3. When the box exits the sensor $\rightarrow$ The scanner sends **`[END]`**. If no scan succeeded during the session, it logs `"NOREAD"`, flashes a **Full-Screen Red Overlay Alert**, rings an alarm, and halts the belt.
4. If a duplicate QR code is scanned $\rightarrow$ Flashes a **Full-Screen Duplicate Red Overlay Alert**.

---

## 🚀 Next Steps for the New Agent
1. **Set Up the Environment:**
   * Install python serial library: `pip install pyserial`.
   * Ensure `database.db`, `fg_scan_counter.py`, `fg_scanner.html`, and `simulate_multi_scanner.py` are placed in the working directory.
2. **Configure the Physical Scanner:**
   * Help the user check their physical COM/USB port name (e.g. `COM4` on Windows or `/dev/tty.usbserial` on Mac/Linux).
   * Set up the Newland NSet utility to send prefix `[START]` and suffix `[END]` around the barcode read window when the proximity sensor is triggered.
3. **Run & Test:**
   * Start the script in production mode: `python3 fg_scan_counter.py --line L04 --port COM4` (or matching port).
   * Open the dashboard on the line's tablet or monitor: `http://localhost:5001/fg_scanner?line=L04`.
