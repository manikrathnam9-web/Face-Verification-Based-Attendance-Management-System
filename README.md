<p align="center">
  <img src="assets/kprit_logo.png" alt="KPRIT Logo" width="160"/>
</p>

# 🏛️ KPRIT - Face Verification-Based Smart Attendance System
### Kommuri Pratap Reddy Institute of Technology (KPRIT), Hyderabad
*Department of Computer Science & Engineering (Data Science / AI & ML)*

[![Institution](https://img.shields.io/badge/Institution-KPRIT%20Hyderabad-blueviolet.svg)](https://kprit.ac.in)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![InsightFace](https://img.shields.io/badge/InsightFace-buffalo__l-orange.svg)](https://github.com/deepinsight/insightface)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-red.svg)](https://streamlit.io/)
[![OpenCV](https://img.shields.io/badge/OpenCV-5.0-green.svg)](https://opencv.org/)
[![Database](https://img.shields.io/badge/Database-SQLite3-lightgrey.svg)](https://sqlite.org/)

An automated biometric face recognition and smart attendance system developed for **Kommuri Pratap Reddy Institute of Technology (KPRIT)**, powered by **InsightFace (ArcFace ResNet-50)** deep convolutional embeddings and **RetinaFace** localization. The system features real-time webcam verification, duplicate prevention, automated punctuality classification, multi-tab Streamlit web analytics, and formal biometric evaluation (FAR/FRR analysis).

---

## 🌟 Key Features

- **Deep Biometric Extraction:** Generates 512-dimensional angular face embeddings using InsightFace `buffalo_l` (ArcFace ResNet-50 backbone) with high discriminative capability.
- **Calibrated Verification:** Cosine similarity decision boundary calibrated at **\(t = 0.58\)** achieving **0.00% FAR** (zero unauthorized bypasses) and **0.00% FRR** (zero genuine student rejections).
- **Dual Verification Modes:**
  - **1:1 Face Verification:** Compares an incoming face against a claimed Student ID.
  - **1:N Face Identification:** Automatically identifies which enrolled student is in front of the camera.
- **Real-Time Webcam Attendance Kiosk:** Fullscreen OpenCV camera feed with colored HUD bounding boxes, student information badges, similarity metrics, and live sound/visual attendance confirmation.
- **Smart Punctuality Analytics:** Automatic tagging based on institutional arrival rules:
  - `Before 09:30:00`: **ON TIME**
  - `09:30:01 - 09:39:59`: **LATE**
  - `09:40:00 onwards`: **VERY LATE**
- **Duplicate Prevention:** Prevents multiple attendance check-ins for the same student on the same calendar date.
- **Interactive Streamlit Web Dashboard:**
  - 📊 Real-time KPIs, attendance rate, punctuality breakdown, and department trends.
  - 📸 Web camera verification and attendance marking (`st.camera_input`).
  - ✍️ Integrated student registration and enrollment portal with consent validation.
  - 📋 Searchable attendance logs and student directory.
  - 📥 One-click CSV and Excel export.
  - 🔬 Interactive biometric evaluation and threshold inspection.
- **Master CLI Launcher (`main.py`):** Unified terminal interface with both interactive menu and programmatic command-line flags.

---

## 📁 Repository Structure

```
Face_Verification_Attendance/
├── app/
│   ├── face_engine.py          # Singleton InsightFace ArcFace engine (detection, quality check, 1:1, 1:N)
│   ├── enrollment.py           # Student enrollment pipeline (metadata, 512-D vectors, DB registration)
│   ├── verification.py         # 1:1 face verification module & CLI
│   ├── attendance.py           # SQLite attendance operations & duplicate prevention
│   ├── attendance_runner.py    # Batch attendance processor & live webcam OpenCV HUD kiosk
│   └── dashboard.py            # 6-tab Streamlit web dashboard
├── database/
│   ├── attendance.db           # SQLite database (students and attendance tables)
│   ├── attendance_queries.py   # Aggregated analytics queries & report exports
│   └── punctuality.py          # Punctuality classification logic and student rankings
├── data/
│   ├── embeddings/             # Enrolled 512-D face vectors (.npy)
│   ├── enrollment/             # Student metadata profiles (.json)
│   ├── test_images/            # Benchmark test portraits (genuine & impostor samples)
│   └── exports/                # Generated CSV attendance reports
├── docs/
│   ├── SYSTEM_ARCHITECTURE.md  # Detailed technical specifications & mathematical formulations
│   └── USER_GUIDE.md           # Step-by-step user manual & operations guide
├── notebooks/
│   └── smart_attendance_walkthrough.ipynb # Interactive demonstration Jupyter notebook
├── reports/
│   ├── far_frr_tradeoff.png          # FAR vs FRR trade-off curve
│   ├── similarity_distribution.png   # Genuine vs Impostor score distribution plot
│   ├── confusion_matrix.png          # Verification confusion matrix at t = 0.58
│   ├── benchmark_metrics.csv         # Evaluated metrics across thresholds
│   └── VERIFICATION_EVALUATION_REPORT.md # Formal evaluation report
├── tests/
│   ├── threshold_evaluation.py       # Threshold sweep & zero-FAR evaluation
│   ├── verification_evaluation.py    # 1:1 genuine/impostor benchmark script
│   └── generate_evaluation_report.py # Automated evaluation plot & report generator
├── main.py                     # Master CLI launcher & entrypoint
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

---

## 🚀 Quick Start

### 1. Installation
```powershell
# Clone or navigate to the workspace
cd Face_Verification_Attendance

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies (if not already installed)
pip install -r requirements.txt
```

### 2. Launch Interactive Menu
```powershell
python main.py
```

### 3. Launch Streamlit Web Dashboard
```powershell
python main.py --dashboard
# or: streamlit run app/dashboard.py
```
Open your browser at `http://localhost:8501`.

### 4. Run Live Webcam Smart Attendance Kiosk
```powershell
python main.py --live
```
- Stand in front of the camera:
  - 🟢 **Green Bounding Box:** Student recognized & attendance recorded!
  - 🟡 **Amber Bounding Box:** Student recognized, but attendance was already logged today.
  - 🔴 **Red Bounding Box:** Unrecognized face (score < 0.58).
- Press `Q` or `ESC` to quit.

---

## 📊 Biometric Performance Evaluation

Evaluation on benchmark test sets using 512-dimensional ArcFace embeddings:

| Metric | Score at Threshold \(t = 0.58\) |
| :--- | :---: |
| **False Acceptance Rate (FAR)** | **0.00%** |
| **False Rejection Rate (FRR)** | **0.00%** |
| **Verification Accuracy** | **100.00%** |
| **Precision** | **100.00%** |
| **Recall** | **100.00%** |
| **Genuine Score Range** | `0.5809 - 0.6419` (Mean: `0.6155`) |
| **Impostor Score Range** | `0.1459` (Mean: `0.1459`) |
| **Decision Separation Margin** | **0.4350** |

### Generated Visualizations (in `reports/`)
- **FAR vs. FRR Trade-off Curve:** Demonstrates the operating point at \(t = 0.58\).
- **Cosine Score Distribution:** Demonstrates distinct separation between genuine and impostor distributions.
- **Confusion Matrix:** Zero false accepts and zero false rejects.

---

## 📜 CLI Commands Reference

| Command | Action |
| :--- | :--- |
| `python main.py` | Interactive Master Menu |
| `python main.py --dashboard` | Launches Streamlit Web Dashboard |
| `python main.py --live` | Starts Real-Time Webcam Attendance Kiosk |
| `python main.py --image <path>` | Runs 1:N attendance processing on an image |
| `python main.py --verify <ID> <path>` | Runs 1:1 verification against claimed student ID |
| `python main.py --enroll` | Enrolls a new student (CLI wizard) |
| `python main.py --summary` | Prints attendance & punctuality summary |
| `python main.py --evaluate` | Generates benchmark metrics and evaluation plots |
| `python main.py --export` | Exports attendance database to CSV |

---

## 🔐 Security & Role-Based Authentication

The web portal is protected with `PBKDF2-HMAC-SHA256` salted password hashing (100,000 iterations). Credentials are read exclusively from environment variables; no default passwords are hardcoded:

| Role | Username Variable | Password Variable | Permissions |
| :--- | :--- | :--- | :--- |
| **Faculty / Admin** | `ADMIN_USERNAME` (`admin`) | `ADMIN_PASSWORD` (Required) | Full administrative access: Analytics, Enrollment, Roster, CSV Export, Threshold Evaluation. |
| **Campus Kiosk** | `KIOSK_USERNAME` (`kiosk`) | `KIOSK_PASSWORD` (Required) | Restricted self-service mode: Camera Attendance only. Student records and admin tools are hidden. |

Configure `ADMIN_PASSWORD` and `KIOSK_PASSWORD` in your `.env` file before launching the system.

---

## 🌐 Production Deployment

The project supports multiple deployment options:
- **Streamlit Community Cloud (Free):** Push to GitHub and deploy via [share.streamlit.io](https://share.streamlit.io/).
- **Docker / Docker Compose:** Run `docker compose up -d` for portable hosting.
- **Linux Cloud VPS (AWS/Azure/DigitalOcean):** Systemd service + Nginx reverse proxy + Free HTTPS SSL (`certbot`).
- **Campus LAN / Wi-Fi:** Local intranet deployment across college computers and tablets.

👉 For complete step-by-step instructions, see the **[Production Deployment Guide](docs/DEPLOYMENT_GUIDE.md)**.

---

## 🔒 Privacy & GDPR Compliance

- **Consent Management:** Consent is validated prior to registering any student.
- **Vector Storage:** Only numeric 512-D vectors (`.npy`) and profile metadata are retained; raw facial images can be discarded after enrollment.
- **Audit Logs:** Every attendance record captures the exact timestamp, entry time, similarity confidence score, and verification status.

---

## 📄 Documentation

- [Production Deployment Guide](docs/DEPLOYMENT_GUIDE.md)
- [System Architecture Specification](docs/SYSTEM_ARCHITECTURE.md)
- [User Guide & Operations Manual](docs/USER_GUIDE.md)
- [Verification Evaluation Report](reports/VERIFICATION_EVALUATION_REPORT.md)
- [Walkthrough Demonstration Notebook](notebooks/smart_attendance_walkthrough.ipynb)
