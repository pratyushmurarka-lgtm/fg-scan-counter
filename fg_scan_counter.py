#!/usr/bin/env python3
import os
import sys
import time
import json
import sqlite3
import threading
import argparse
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

from socketserver import ThreadingMixIn

# Configuration & Defaults
DEFAULT_DB = "database.db"
DEFAULT_BAUD = 115200
HTTP_PORT = 5001

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

# Global State Dictionary for all active lines
line_states = {}
state_lock = threading.Lock()

# Event listeners (clients connected to SSE streams)
clients = []
clients_lock = threading.Lock()


def get_db_connection():
    return sqlite3.connect(DEFAULT_DB)


def init_database():
    """Ensure the local scan counter table exists in SQLite database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inscandata (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fgcode TEXT,
            qrtext TEXT,
            isdup INTEGER,
            scandate DATETIME DEFAULT CURRENT_TIMESTAMP,
            istank INTEGER DEFAULT 0,
            username TEXT,
            scangapsec INTEGER,
            prevscandate TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("[INFO] SQLite 'inscandata' table initialized/verified.")


def extract_numbers(txt):
    """Strip all non-digit characters (for V-Guard serial cleaning)."""
    return re.sub(r"\D", "", txt)


def broadcast_event(line_id, event_type, data):
    """Send real-time updates to all connected web dashboard clients via SSE."""
    payload = {
        "line_id": line_id,
        "event_type": event_type,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data": data
    }
    msg = f"data: {json.dumps(payload)}\n\n"
    
    with clients_lock:
        active_clients = []
        for client in clients:
            try:
                client.write(msg.encode("utf-8"))
                client.flush()
                active_clients.append(client)
            except Exception:
                pass
        clients[:] = active_clients


def check_duplicate(qr):
    """Check if the QR has been scanned in either inscandata or ESJOBSCANDATA."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    fgcode = None
    scandate = None
    qr_details = qr
    item_name = "Unknown Product"
    
    # 1. Check local inscandata
    cursor.execute("SELECT fgcode, datetime(scandate, 'localtime'), qrtext FROM inscandata WHERE qrtext = ? OR fgcode = ?", (qr, qr))
    row = cursor.fetchone()
    if row:
        fgcode = row[0]
        scandate = row[1]
        qr_details = row[2] or qr
    else:
        # 2. Check ESJOBSCANDATA (using SQLite-safe columns if running on replica)
        try:
            cursor.execute("""
                SELECT ITEM, datetime(DATE, 'localtime'), ITEM FROM ESJOBSCANDATA 
                WHERE (ITEM = ? OR ITEM = ?) AND ISDUP = 0
            """, (qr, qr))
            row = cursor.fetchone()
            if row:
                fgcode = row[0]
                scandate = row[1]
                qr_details = row[2] or qr
        except sqlite3.OperationalError:
            pass
            
    if fgcode:
        # Resolve Item Name from ItemMaster
        try:
            cursor.execute("SELECT name FROM ItemMaster WHERE code = ? OR codestr = ?", (fgcode, fgcode))
            im_row = cursor.fetchone()
            if im_row and im_row[0]:
                item_name = im_row[0]
        except sqlite3.OperationalError:
            pass
            
        conn.close()
        return True, fgcode, item_name, scandate, qr_details
        
    conn.close()
    return False, None, None, None, None


def save_scan(line_id, qr, fgcode, is_dup, prev_scan_date, gap_sec):
    """Save scan transaction to database tables."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get masterp multiplier from ItemMaster if column exists
    masterp = 1
    try:
        cursor.execute("SELECT masterp FROM ItemMaster WHERE code = ?", (fgcode,))
        row = cursor.fetchone()
        if row and row[0]:
            masterp = row[0]
    except sqlite3.OperationalError:
        pass
    
    # Insert to local inscandata
    cursor.execute("""
        INSERT INTO inscandata (fgcode, qrtext, isdup, username, scangapsec, prevscandate)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (fgcode, qr, is_dup, line_id, gap_sec, prev_scan_date))
    
    # Insert to ESJOBSCANDATA
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO ESJOBSCANDATA (ITEM, UserName, DATE, ISDUP, IsConsume)
            VALUES (?, ?, datetime('now'), ?, 0)
        """, (fgcode, line_id, is_dup))
    except sqlite3.OperationalError:
        pass
        
    conn.commit()
    conn.close()


def query_duplicate_log(line_id):
    """Get all duplicate scans recorded today for a line."""
    conn = get_db_connection()
    cursor = conn.cursor()
    dup_rows = []
    try:
        cursor.execute("""
            SELECT ims.fgcode, COALESCE(im.name, 'Unknown Item'), ims.prevscandate, ims.qrtext, datetime(ims.scandate, 'localtime')
            FROM inscandata ims
            LEFT JOIN ItemMaster im ON im.code = ims.fgcode OR im.codestr = ims.fgcode
            WHERE date(ims.scandate) = date('now')
              AND ims.username = ?
              AND ims.isdup = 1
            ORDER BY ims.id DESC
        """, (line_id,))
        for r in cursor.fetchall():
            dup_rows.append({
                "fgcode": r[0] or "N/A",
                "name": r[1] or "N/A",
                "prev_date": str(r[2]) if r[2] else "N/A",
                "qr": r[3] or "N/A",
                "dup_date": str(r[4]) if r[4] else "N/A"
            })
    except Exception as e:
        print("Error querying duplicate log:", e)
    conn.close()
    return dup_rows


def query_tally_summary(line_id):
    """Get today's total physical count vs successful scans count for a line."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Total sessions / physical count (excluding duplicates)
    cursor.execute("""
        SELECT COUNT(*) FROM inscandata 
        WHERE date(scandate) = date('now') AND username = ? AND isdup = 0
    """, (line_id,))
    total_physical = cursor.fetchone()[0]
    
    # Total successful scans
    cursor.execute("""
        SELECT COUNT(*) FROM inscandata 
        WHERE date(scandate) = date('now') 
          AND username = ? 
          AND qrtext != 'NOREAD' 
          AND isdup = 0
    """, (line_id,))
    total_scans = cursor.fetchone()[0]
    
    # Table breakdown by item (handling SQLite column name variations)
    summary_rows = []
    try:
        cursor.execute("""
            SELECT im.name, COUNT(ims.qrtext) 
            FROM inscandata ims
            JOIN ItemMaster im ON im.code = ims.fgcode OR im.codestr = ims.fgcode
            WHERE date(ims.scandate) = date('now')
              AND ims.username = ? 
              AND ims.qrtext != 'NOREAD' 
              AND ims.isdup = 0
            GROUP BY im.name
        """, (line_id,))
        summary_rows = [{"name": r[0], "qty": r[1]} for r in cursor.fetchall()]
    except sqlite3.OperationalError:
        pass
        
    conn.close()
    dup_log = query_duplicate_log(line_id)
    return total_physical, total_scans, summary_rows, dup_log


# --- Session State Machine Processor ---
def process_incoming_data(line_id, clean_data):
    """Handle scanner serial buffer stream."""
    global line_states
    
    with state_lock:
        if line_id not in line_states:
            line_states[line_id] = {
                "box_present": False,
                "scanned_this_session": False,
                "last_qr": "",
                "last_scan_time": 0.0,
                "manual_mode": False,
                "manual_fgcode": "",
                "manual_brand": "",
                "manual_itemname": ""
            }
        state = line_states[line_id]

    print(f"[{line_id}] Received data: '{clean_data}'")

    # 1. Handle START of presence session
    if clean_data == "[START]":
        state["box_present"] = True
        state["scanned_this_session"] = False
        broadcast_event(line_id, "BOX_PRESENT", {"status": True})
        return

    # 2. Handle END of presence session
    if clean_data == "[END]":
        state["box_present"] = False
        broadcast_event(line_id, "BOX_PRESENT", {"status": False})
        
        # If box cleared but no successful scan occurred
        if not state["scanned_this_session"]:
            gap_sec = 0
            curr_time = time.time()
            if state["last_scan_time"] > 0:
                gap_sec = int(curr_time - state["last_scan_time"])
            state["last_scan_time"] = curr_time
            
            # Save failed scan to DB
            save_scan(line_id, "NOREAD", "NOREAD", 0, None, gap_sec)
            
            phys, scans, summary, dup_log = query_tally_summary(line_id)
            broadcast_event(line_id, "SCAN_FAILURE", {
                "message": "BARCODE NOT SCANNED",
                "physical_count": phys,
                "scan_count": scans,
                "summary": summary,
                "duplicate_log": dup_log
            })
        return

    # 3. Handle barcode scan
    curr_time = time.time()
    if clean_data == state["last_qr"] and (curr_time - state["last_scan_time"]) < 2.0:
        print(f"[{line_id}] Duplicate scan ignored (Time gap too short)")
        return

    state["last_qr"] = clean_data
    gap_sec = 0
    if state["last_scan_time"] > 0:
        gap_sec = int(curr_time - state["last_scan_time"])
    state["last_scan_time"] = curr_time

    # Clean V-Guard serial if manual override is active
    processed_qr = clean_data
    if state["manual_mode"] and state["manual_brand"] == "V-GUARD":
        processed_qr = extract_numbers(clean_data)

    # Check database duplicates
    is_dup, dup_code, dup_name, dup_date, dup_qr_details = check_duplicate(processed_qr)
    
    if is_dup:
        save_scan(line_id, processed_qr, dup_code or "DUP", 1, dup_date, gap_sec)
        phys, scans, summary, dup_log = query_tally_summary(line_id)
        broadcast_event(line_id, "SCAN_DUPLICATE", {
            "qr": processed_qr,
            "fgcode": dup_code or "Unknown Code",
            "itemname": dup_name or "Unknown Item",
            "scandate": str(dup_date) if dup_date else "N/A",
            "qr_details": dup_qr_details or processed_qr,
            "physical_count": phys,
            "scan_count": scans,
            "summary": summary,
            "duplicate_log": dup_log
        })
        return

    # Resolve Item Code
    fgcode = ""
    itemname = "Unknown Product"
    brandname = "Unknown Brand"

    if state["manual_mode"]:
        fgcode = state["manual_fgcode"]
        itemname = state["manual_itemname"]
        brandname = state["manual_brand"]
    else:
        # Auto-detect from ItemMaster (with column fallback safety)
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT code, name, CodeStr FROM ItemMaster")
            items = cursor.fetchall()
            for it in items:
                code, name, codestr = it[0], it[1], it[2] if len(it) > 2 else ""
                
                # Check match against codestr (long identifier) or exact/word-boundary code
                if codestr and len(str(codestr)) >= 4 and str(codestr) in clean_data:
                    fgcode = code
                    itemname = name
                    brandname = "Detected Brand"
                    break
                elif code and str(code) == clean_data:
                    fgcode = code
                    itemname = name
                    brandname = "Detected Brand"
                    break
                elif name:
                    # Match any 7-digit model suffix in name (e.g., '3803311' for CDR DLX 15V)
                    match = re.search(r'\d{7}', name)
                    if match and match.group(0) in clean_data:
                        fgcode = code
                        itemname = name
                        brandname = "Detected Brand"
                        break
        except sqlite3.OperationalError:
            pass
        conn.close()

    if not fgcode:
        # Auto-resolve failed, broadcast request for manual override selection
        broadcast_event(line_id, "MANUAL_REQUIRED", {"qr": clean_data})
        return

    # Log successful scan
    save_scan(line_id, processed_qr, fgcode, 0, None, gap_sec)
    state["scanned_this_session"] = True

    phys, scans, summary, dup_log = query_tally_summary(line_id)
    broadcast_event(line_id, "SCAN_SUCCESS", {
        "qr": processed_qr,
        "fgcode": fgcode,
        "itemname": itemname,
        "brandname": brandname,
        "gap_sec": gap_sec,
        "physical_count": phys,
        "scan_count": scans,
        "summary": summary,
        "duplicate_log": dup_log
    })


# --- Serial Comm Port Reader Thread ---
def serial_listener_thread(line_id, port_name):
    """Listen for incoming data on a serial/COM port."""
    import serial
    print(f"[INFO] Thread started for Line {line_id} on Serial Port {port_name}...")
    
    try:
        ser = serial.Serial(port_name, baudrate=DEFAULT_BAUD, timeout=1.0)
        buffer = ""
        while True:
            if ser.in_waiting > 0:
                data = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
                buffer += data
                
                if "\r" in buffer or "\n" in buffer:
                    packets = re.split(r"[\r\n]+", buffer)
                    for pkt in packets[:-1]:
                        pkt = pkt.strip()
                        if pkt:
                            process_incoming_data(line_id, pkt)
                    buffer = packets[-1]
            time.sleep(0.05)
    except Exception as e:
        print(f"[ERROR] Serial port {port_name} disconnected or failed: {e}")


# --- Dashboard HTTP & SSE Server ---
class DashboardServer(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        if path == "/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            with clients_lock:
                clients.append(self.wfile)
            
            while True:
                try:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    time.sleep(15)
                except Exception:
                    break
            return

        if path in ["/", "/fg_scanner"]:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            
            html_path = "fg_scanner.html"
            if os.path.exists(html_path):
                with open(html_path, "r", encoding="utf-8") as f:
                    self.wfile.write(f.read().encode("utf-8"))
            else:
                self.wfile.write(b"<h1>Error: fg_scanner.html file not found!</h1>")
            return

        if path == "/api/summary":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            query = parse_qs(parsed_url.query)
            line = query.get("line", ["L04"])[0]
            phys, scans, summary, dup_log = query_tally_summary(line)
            
            self.wfile.write(json.dumps({
                "physical_count": phys,
                "scan_count": scans,
                "summary": summary,
                "duplicate_log": dup_log
            }).encode("utf-8"))
            return

        if path == "/api/items":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            query = parse_qs(parsed_url.query)
            brand = query.get("brand", [""])[0]
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Retrieve Finished Goods (ItemType = 81)
            # Brand IDs: 69 (Usha), 71 (V-Guard)
            # Local Replica Fallback Brand IDs: 76 (Usha), 78 (V-Guard)
            items = []
            try:
                brand_upper = brand.upper()
                if brand_upper == "USHA":
                    grps = (69, 76)
                elif brand_upper == "V-GUARD":
                    grps = (71, 78)
                else:
                    grps = ()
                
                if grps:
                    cursor.execute("""
                        SELECT Code, Name FROM ItemMaster 
                        WHERE ItemType = 81 AND ItemGrp IN (?, ?)
                    """, grps)
                else:
                    cursor.execute("""
                        SELECT Code, Name FROM ItemMaster 
                        WHERE Name LIKE ?
                    """, (f"%{brand}%",))
                items = [{"code": r[0], "name": r[1]} for r in cursor.fetchall()]
            except sqlite3.OperationalError:
                pass
            conn.close()
            
            self.wfile.write(json.dumps(items).encode("utf-8"))
            return

        if path.startswith("/images/"):
            img_code = path.split("/")[-1].replace(".jpg", "").replace(".jpeg", "")
            img_path = f"C:/Images/{img_code}.jpeg"
            if not os.path.exists(img_path):
                img_path = "inf.jpeg"
                
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.end_headers()
            if os.path.exists(img_path):
                with open(img_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.wfile.write(b"")
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        if path == "/api/event":
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length).decode("utf-8")
            params = json.loads(body)
            
            line_id = params.get("line_id") or params.get("line")
            clean_data = params.get("data") or params.get("clean_data")
            
            if line_id and clean_data:
                process_incoming_data(line_id, clean_data)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
            else:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": "Missing line_id or data"}).encode("utf-8"))
            return

        if path == "/api/manual_override":
            content_length = int(self.headers["Content-Length"])
            body = self.rfile.read(content_length).decode("utf-8")
            params = json.loads(body)
            
            line_id = params.get("line_id")
            brand = params.get("brand")
            code = params.get("code")
            itemname = params.get("name", "")
            enabled = params.get("enabled", False)
            
            with state_lock:
                if line_id not in line_states:
                    line_states[line_id] = {
                        "box_present": False,
                        "scanned_this_session": False,
                        "last_qr": "",
                        "last_scan_time": 0.0,
                        "manual_mode": False,
                        "manual_fgcode": "",
                        "manual_brand": "",
                        "manual_itemname": ""
                    }
                
                state = line_states[line_id]
                state["manual_mode"] = enabled
                state["manual_brand"] = brand
                state["manual_fgcode"] = code
                state["manual_itemname"] = itemname
                
            print(f"[INFO] Manual override set on {line_id}: Enabled={enabled}, Brand={brand}, Code={code}")
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode("utf-8"))
            return


def start_http_server():
    server = ThreadingHTTPServer(("0.0.0.0", HTTP_PORT), DashboardServer)
    print(f"[INFO] Web Dashboard server listening at http://localhost:{HTTP_PORT}/")
    server.serve_forever()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="INTECH FG Scan Counter & Verification Server")
    parser.add_argument("--line", type=str, help="Single Line ID to run (e.g. L04)")
    parser.add_argument("--port", type=str, help="Serial COM port for single line mode (e.g. COM4)")
    args = parser.parse_args()
    
    init_database()
    
    threading.Thread(target=start_http_server, daemon=True).start()
    
    if args.line and args.port:
        serial_listener_thread(args.line, args.port)
    else:
        print("[INFO] Scanner engine active. Waiting for dashboard HTTP/SSE events...")
        while True:
            time.sleep(1)
