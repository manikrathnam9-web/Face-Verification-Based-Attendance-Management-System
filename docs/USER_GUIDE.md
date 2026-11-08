# User Guide & Operations Manual

## Face Verification-Based Smart Attendance System

---

## 1. Quick Start

### 1.1 Activate Environment
Open PowerShell inside the project directory:
```powershell
.\.venv\Scripts\Activate.ps1
```

### 1.2 Launch Master CLI Menu
Run:
```powershell
python main.py
```
This presents the interactive menu covering all features.

---

## 2. Running the Interactive Streamlit Web Dashboard

Launch the browser-based dashboard:
```powershell
python main.py --dashboard
```
Or directly:
```powershell
streamlit run app/dashboard.py
```

### Dashboard Tabs Overview:
1. **📊 Analytics & KPIs:**
   - Filter attendance by calendar date, department, or student.
   - View key metrics: Registered Students, Present on Date, Absent, Attendance Rate %, On-Time Rate %.
   - Inspect Punctuality Distribution (On Time, Late, Very Late) and Department-wise charts.
2. **📸 Live Attendance & Verification:**
   - Choose between **1:N Auto-Match** (recognizes any registered student) or **1:1 Claimed Verification** (validates against a specific ID).
   - Use live webcam (`st.camera_input`) or file upload.
   - Click **Log Attendance Now** to save to SQLite database with duplicate detection.
3. **✍️ Student Enrollment:**
   - Fill in Student ID, Name, Department, Year, and check the Consent agreement.
   - Capture a photo using your webcam or upload a portrait.
   - Real-time extraction of 512-D ArcFace embedding and SQLite registration.
4. **📋 Attendance Records:**
   - Searchable, filterable table of historical attendance records.
   - Registered student directory.
5. **📥 Export Reports:**
   - One-click export to CSV with browser download.
6. **🔬 Model & Biometrics Evaluation:**
   - Visual inspection of the FAR/FRR trade-off curve, similarity score distribution, and confusion matrix.

---

## 3. Real-Time Webcam Attendance Kiosk (OpenCV)

To run a standalone live camera kiosk (e.g. for front-desk or classroom entrance):
```powershell
python main.py --live
```
- **HUD Indicator Legend:**
  - 🟢 **Green Box:** Student recognized & attendance recorded! Displays Name, ID, similarity score, and punctuality status.
  - 🟡 **Amber Box:** Student recognized, but attendance has **already been recorded** for today.
  - 🔴 **Red Box:** Face unrecognized (similarity < 0.58) or not enrolled.
- **Exit:** Press `Q` or `ESC` in the camera window.

---

## 4. Enrolling Students via Command Line

Run:
```powershell
python main.py --enroll
```
Follow the interactive prompts:
1. Enter Roll / Student ID (e.g. `DS003`)
2. Enter Name (e.g. `Alex Johnson`)
3. Enter Department (e.g. `CSE-DS`)
4. Enter Year (e.g. `4`)
5. Confirm Consent (`yes`)
6. Choose image source:
   - `1`: Provide path to an image file.
   - `2`: Capture live portrait with webcam (press `SPACE` to capture, `ESC` to cancel).

---

## 5. Performing 1:1 Face Verification

To test if a photo matches a claimed student ID:
```powershell
python main.py --verify DS001 data/test_images/test_same_person.jpeg
```

---

## 6. Exporting Attendance Data

To export all verified attendance records to a timestamped CSV:
```powershell
python main.py --export
```
Files are saved directly to `data/exports/attendance_report_<timestamp>.csv`.

---

## 7. Running Model Performance Evaluation

To re-run the benchmark tests and generate updated publication plots:
```powershell
python main.py --evaluate
```
This updates:
- `reports/far_frr_tradeoff.png`
- `reports/similarity_distribution.png`
- `reports/confusion_matrix.png`
- `reports/benchmark_metrics.csv`
- `reports/VERIFICATION_EVALUATION_REPORT.md`
