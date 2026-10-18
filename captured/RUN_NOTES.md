# PipeGen Execution Notes & Verified Hardware Specs

## Environment & Hardware
- **Host OS:** Windows 11 Home Single Language (Build 26100)
- **Linux Environment:** WSL2 Ubuntu 24.04 LTS
- **GPU:** NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM, 60W TGP)
- **NVIDIA Driver:** 591.74
- **CUDA Version:** 13.1 (Driver) / 12.6 (Runtime)
- **TensorRT Version:** 10.3.0
- **PipeGen Container:** `craftifaidocker/deepstream:7.1-amd64-v3`
- **PipeGen GUI:** Electron / WebKit (`/opt/PipeGen/PipeGenApp`) via WSLg
- **Project UUID:** `65fb2507-da6e-4502-b2ed-4c8f644d736d`

## Input Footage
- **File:** `/home/tanishk_ji/videos/demo.mp4`
- **Resolution:** 2560 x 1440
- **Duration:** 16 seconds (395 frames @ ~24.4 fps)

## Pipeline Architecture & Models
1. **Source / Stream Mux:**
   - `nvurisrcbin` -> `nvstreammux` (2560x1440, batch-size=1)
2. **Primary Detector (Person):**
   - ONNX: `yolo11s.onnx` (RestrictedAreaMonitoring)
   - Compiled TensorRT Plan: `yolo11s.fp32.plan` (234 TRT layers, 49.1 MB)
   - Measured Latency: **32.525 ms** (trtexec end-to-end), compute: **31.350 ms**, power: **32.44 W** (nvidia-smi)
   - Throughput: **~30.75 FPS**
3. **Tracker:**
   - `nvtracker` (`libnvds_nvmultiobjecttracker.so`, 640x384)
4. **Secondary Detector (PPE - Hard Hat & Safety Vest):**
   - ONNX: `best.onnx` (ppe-kit)
   - Compiled TensorRT Plan: `best.fp32.plan` (196 TRT layers, 17.9 MB)
   - Measured Latency: **15.105 ms** (trtexec end-to-end), compute: **14.306 ms**, power: **32.87 W** (nvidia-smi)
   - Throughput: **~66.2 FPS**
5. **Custom Processors:**
   - `libzone_ppe_process.so`: Hazard zone polygon `[[256, 432], [1280, 432], [1280, 1152], [256, 1152]]`, dwell timing, and PPE compliance tagging
   - `libmqtt_publish.so`: High-throughput per-frame telemetry to Mosquitto (`localhost:1883`, topic `pipegen/detection/demo`)
   - `libmeta_json.so`: Structured metadata sink writing to `metadata.json`

## Execution Summary
- **Frames Processed:** 395 frames
- **Total Objects Detected:** 2,801 objects
- **Messages Published:** 395 MQTT messages (average 18.6 - 24.4 msg/s)
- **DeepStream Execution Time:** 18.34 seconds
- **Result:** Successfully reached EOS with 0 crashes.
