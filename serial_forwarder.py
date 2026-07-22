#!/usr/bin/env python3
import time
import sys
import argparse
import re
import requests
import serial
import os
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

DEFAULT_BAUD = 115200

def get_line_from_config():
    config_path = "C:\\dbconfig.txt"
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip().upper()
                        v = v.strip()
                        if k == "LIVE_LINENO":
                            return v.upper()
        except Exception as e:
            print(f"[WARNING] Error reading dbconfig.txt: {e}")
    return "L04"

class LocalConfigHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress console log spam

    def do_GET(self):
        if self.path == "/api/line":
            line_id = get_line_from_config()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"line": line_id}).encode("utf-8"))
            return
        self.send_response(404)
        self.end_headers()

def start_local_server():
    try:
        server = HTTPServer(("127.0.0.1", 5002), LocalConfigHandler)
        server.serve_forever()
    except Exception as e:
        print(f"[WARNING] Could not start local config API server: {e}")

def main():
    # Start local config API server in daemon thread
    threading.Thread(target=start_local_server, daemon=True).start()

    parser = argparse.ArgumentParser(description="INTECH FG Scanner Serial Port Forwarder")
    parser.add_argument("--port", type=str, default="COM3", help="Serial COM port of scanner (e.g. COM3)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="Baud rate (default: 115200)")
    
    detected_line = get_line_from_config()
    parser.add_argument("--line", type=str, default=detected_line, help="Line ID (e.g. L04)")
    parser.add_argument("--server", type=str, default="http://localhost:5001", help="Central server URL (e.g. http://192.168.1.218:5001)")
    args = parser.parse_args()

    server_url = args.server.rstrip('/')
    event_endpoint = f"{server_url}/api/event"

    print("==========================================================")
    print("      INTECH FG Scanner Serial Port Forwarder Client      ")
    print("==========================================================")
    print(f"Target Line ID : {args.line}")
    print(f"Serial Port    : {args.port}")
    print(f"Baud Rate      : {args.baud}")
    print(f"Central Server : {event_endpoint}")
    print("==========================================================")

    # Reconnection loop for serial port
    while True:
        try:
            print(f"[INFO] Attempting to open serial port {args.port}...")
            ser = serial.Serial(args.port, baudrate=args.baud, timeout=1.0)
            print(f"[SUCCESS] Connected to {args.port}. Listening for barcode scanner events...")
            
            buffer = ""
            last_recv_time = 0.0
            while True:
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting).decode("utf-8", errors="ignore")
                    buffer += data
                    last_recv_time = time.time()
                
                if buffer:
                    has_newline = "\r" in buffer or "\n" in buffer
                    silence_timeout = (time.time() - last_recv_time) > 0.15
                    
                    if has_newline or silence_timeout:
                        if has_newline:
                            packets = re.split(r"[\r\n]+", buffer)
                            if not buffer.endswith("\n") and not buffer.endswith("\r") and not silence_timeout:
                                pkts_to_process = packets[:-1]
                                buffer = packets[-1]
                            else:
                                pkts_to_process = packets
                                buffer = ""
                        else:
                            pkts_to_process = [buffer]
                            buffer = ""
                        
                        for pkt in pkts_to_process:
                            pkt = pkt.strip()
                            if pkt:
                                timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
                                print(f"[{timestamp}] Scanned: '{pkt}'")
                                
                                # Forward event to central server
                                try:
                                    payload = {"line": args.line, "data": pkt}
                                    res = requests.post(event_endpoint, json=payload, timeout=2.0)
                                    if res.status_code == 200:
                                        print(f"[{timestamp}] [OK] Event forwarded to central server.")
                                    else:
                                        print(f"[{timestamp}] [WARNING] Server error {res.status_code}: {res.text}")
                                except requests.exceptions.RequestException as req_err:
                                    print(f"[{timestamp}] [ERROR] Network connection failed: {req_err}")
                
                time.sleep(0.05)
                
        except serial.SerialException as ser_err:
            print(f"[ERROR] Serial port error: {ser_err}")
            print("[INFO] Reconnecting in 5 seconds...")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n[INFO] Exiting forwarder client. Goodbye!")
            sys.exit(0)
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            print("[INFO] Retrying in 5 seconds...")
            time.sleep(5)

if __name__ == "__main__":
    main()
