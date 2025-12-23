# RoboFab: Autonomous Robotic Fabrication & Analysis

Welcome to the **RoboFab** repository. This platform integrates collaborative robotics with additive manufacturing to create an autonomous pipeline for harvesting and characterizing soft robotic actuators.

## 1. System Architecture

The platform utilizes a **Service-Oriented Architecture (SOA)** to decouple hardware drivers from high-level orchestration logic:

* **Orchestration Layer**: Manages the synchronization between 3D print completion and robotic harvest sequences.
* **Hardware Drivers**: Python-based wrappers for the **UR7e** (via RTDE) and **Moonraker/Klipper** HTTP APIs.
* **Vision System**: A real-time analysis suite using **YOLO** for object detection and a calibrated **Eye-in-Hand** camera for characterization.

## 2. Project Structure

```text
Robotic_Fabrication/
├── config/             # Local hardware IPs and safety boundaries
├── models/             # YOLOv8 weights for actuator detection
├── pkg/                # Core logic packages
│   ├── drivers/        # UR_RTDE, Moonraker, and Robotiq drivers
│   ├── utils/          # Spatial safety and coordinate mapping
│   └── vision/         # Eye-in-Hand transformation logic
├── scripts/            # Operational scripts
│   ├── setup/          # Teaching waypoints and camera calibration
│   └── diagnostics/    # Hardware and motion test suites
└── services/           
    └── orchestrator.py # The main RoboFab workcell controller

```

## 3. Getting Started

### 1. Environment Setup

```bash
pip install -r requirements.txt

```

### 2. Hardware Setup (One-Time)

1. **Teach Safety Cage**: Define the printer boundaries to enable the **SpatialManager** safety checks.
```bash
python scripts/setup/01_teach_cage.py

```


2. **Calibrate Vision**: Run the hand-eye calibration to align the TCP with the camera frame.
```bash
python scripts/setup/03_calibrate_camera.py

```



### 3. Running the System

Start the main orchestrator to begin monitoring the printer for harvest-ready actuators:

```bash
python services/orchestrator.py

```
