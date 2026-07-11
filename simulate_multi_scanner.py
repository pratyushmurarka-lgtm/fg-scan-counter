#!/usr/bin/env python3
import sys
import time
import threading
import fg_scan_counter

def print_help():
    print("""
================================================================
INTECH FG Scan Counter - Interactive Simulator
================================================================
Use this tool to simulate physical events from the conveyor.

Commands:
  start <line>       -> Simulate box entering sensor (Sends '[START]')
  end <line>         -> Simulate box exiting sensor (Sends '[END]')
  scan <line> <qr>   -> Simulate barcode scan (Sends QR text)
  help               -> Show this help guide
  exit               -> Exit the simulator

Examples:
  * Good Scan:
    > start L04
    > scan L04 0422-RACOLD
    > end L04

  * Missed Scan (Failure Alert):
    > start L04
    > end L04

  * Duplicate Scan:
    > start L04
    > scan L04 0422-RACOLD
    > end L04
================================================================
""")

def run_interactive_sim():
    print_help()
    
    # Initialize SQLite database
    fg_scan_counter.init_database()
    
    # Start web server in a background thread so the dashboard functions
    threading.Thread(target=fg_scan_counter.start_http_server, daemon=True).start()
    
    # Simple CLI event loop
    while True:
        try:
            line = input("sim> ").strip()
            if not line:
                continue
                
            parts = line.split()
            cmd = parts[0].lower()
            
            if cmd == "exit":
                print("Exiting simulator...")
                sys.exit(0)
                
            elif cmd == "help":
                print_help()
                
            elif cmd == "start":
                if len(parts) < 2:
                    print("Usage: start <line_id> (e.g. start L04)")
                    continue
                line_id = parts[1].upper()
                fg_scan_counter.process_incoming_data(line_id, "[START]")
                
            elif cmd == "end":
                if len(parts) < 2:
                    print("Usage: end <line_id> (e.g. end L04)")
                    continue
                line_id = parts[1].upper()
                fg_scan_counter.process_incoming_data(line_id, "[END]")
                
            elif cmd == "scan":
                if len(parts) < 3:
                    print("Usage: scan <line_id> <qr_text>")
                    continue
                line_id = parts[1].upper()
                qr_text = " ".join(parts[2:])
                fg_scan_counter.process_incoming_data(line_id, qr_text)
                
            else:
                print(f"Unknown command: '{cmd}'. Type 'help' for options.")
                
        except (KeyboardInterrupt, EOFError):
            print("\nExiting simulator...")
            break
        except Exception as e:
            print(f"Error executing command: {e}")

if __name__ == "__main__":
    run_interactive_sim()
