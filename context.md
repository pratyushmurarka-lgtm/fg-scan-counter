# Project Context: Finished Goods (FG) Scan Counter & Verification System

This repository is dedicated to the Finished Goods (FG) Scan Counter & Verification System project.

## Git Repository Policy
Whenever instructions or prompts are given to push, pull, or sync code for this project on GitHub, it must be done exclusively with the following repository:

- **Repository URL**: `https://github.com/pratyushmurarka-lgtm/fg-scan-counter.git`

Ensure that your local git configuration is set up to authenticate with this repository (e.g., using a personal access token or credentials manager) without hardcoding credentials in the code or documentation.

## Hardware & Connection Details
- **Connection Type**: USB RS-232 Cable (emulates a Virtual COM Port, specifically `COM3` on Windows).
- **Proximity Sensor & Triggering**:
  - The proximity sensor is not directly connected to the PC; it is an integrated part of the physical scanner.
  - When the sensor detects an object/box, it automatically triggers the scanner's camera to scan.
  - The scanner is configured (e.g., via the Newland NSet utility) to send prefix `[START]` and suffix `[END]` around the barcode read window to define the read session.
