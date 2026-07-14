#!/usr/bin/env python3
import time
import sys
import argparse
import re
import requests
import serial

DEFAULT_BAUD = 115200

def main():
    parser = argparse.ArgumentParser(description="INTECH FG Scanner Serial Port Forwarder")
    parser.add_argument("--port", type=str, default="COM3", help="Serial COM port of scanner (e.g. COM3)")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD, help="Baud rate (default: 115200)")
    parser.add_argument("--line", type=str, default="L04", help="Line ID (e.g. L04)")
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
