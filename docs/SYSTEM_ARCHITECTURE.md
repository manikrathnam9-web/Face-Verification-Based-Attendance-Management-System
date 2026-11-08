# System Architecture & Technical Specification

## Face Verification-Based Smart Attendance System

---

## 1. High-Level Architecture

The system operates across four primary layers:
1. **Sensory & Input Layer:** Standard webcams (OpenCV VideoCapture) and digital image uploads.
2. **Biometric Deep Learning Layer:** InsightFace `buffalo_l` multi-task deep neural network (RetinaFace for localization and ArcFace ResNet-50 for 512-dimensional hyperspherical feature embedding extraction).
3. **Decision & Business Logic Layer:** Cosine similarity comparison engine, threshold gating (\(t = 0.58\)), punctuality classification rules, and duplicate check mechanisms.
4. **Persistence & Presentation Layer:** SQLite relational database (`attendance.db`), Streamlit multi-tab reactive web dashboard, and CLI management interface.

```
       +---------------------------------------------+
       |         Image / Webcam Stream Capture       |
       +---------------------------------------------+
                              |
                              v
       +---------------------------------------------+
       |   RetinaFace Face Detection & Alignment     |
       +---------------------------------------------+
                              |
                              v
       +---------------------------------------------+
       |  ArcFace ResNet-50 512-D Embedding Vector   |
       +---------------------------------------------+
                              |
                              v
       +---------------------------------------------+
       |          Cosine Similarity Evaluation       |
       |     S(u, v) = (u . v) / (||u|| * ||v||)     |
       +---------------------------------------------+
                              |
               +--------------+--------------+
               |                             |
       S >= 0.58 (Match)             S < 0.58 (Mismatch)
               |                             |
               v                             v
   +-----------------------+     +-----------------------+
   | Check Duplicate Today |     | Tag: REJECTED         |
   +-----------------------+     | No Attendance Logged  |
       |               |         +-----------------------+
    New Log       Duplicate
       |               |
       v               v
+-------------+ +--------------------+
| Classify    | | Notify Already Log |
| Punctuality | +--------------------+
+-------------+
       |
       v
+-------------------------------+
| Record to SQLite attendance.db|
+-------------------------------+
```

---

## 2. Deep Face Recognition Pipeline (InsightFace ArcFace)

### 2.1 Detection & Landmark Alignment
- **Model:** RetinaFace (`det_10g.onnx`) with Feature Pyramid Networks (FPN) and single-stage pixel-wise face localization.
- **Landmarks:** 5-point facial landmarks (left eye, right eye, nose tip, left mouth corner, right mouth corner) mapped to canonical coordinates using affine similarity transform.
- **Normalization:** Crop and affine align the facial crop to a standard \(112 \times 112\) dimension.

### 2.2 Feature Representation (ArcFace)
- **Backbone:** Deep Residual Network (ResNet-50, `w600k_r50.onnx`).
- **Loss Function:** Additive Angular Margin Loss (ArcFace):
  \[
  L_{\text{ArcFace}} = -\log \frac{e^{s(\cos(\theta_{y_i} + m))}}{e^{s(\cos(\theta_{y_i} + m))} + \sum_{j \neq y_i} e^{s \cos \theta_j}}
  \]
  where \(s = 64\) is the feature scale and \(m = 0.5\) is the additive angular margin, enforcing compact intra-class variance and maximized inter-class angular discrepancy.
- **Output:** A 512-dimensional real vector \(\mathbf{x} \in \mathbb{R}^{512}\).

---

## 3. Mathematical Verification Metric: Cosine Similarity

Given enrolled reference template embedding \(\mathbf{u} \in \mathbb{R}^{512}\) and incoming query face embedding \(\mathbf{v} \in \mathbb{R}^{512}\):

\[
\text{Similarity}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2} = \frac{\sum_{i=1}^{512} u_i v_i}{\sqrt{\sum_{i=1}^{512} u_i^2} \sqrt{\sum_{i=1}^{512} v_i^2}}
\]

### Verification Rule:
\[
\text{Decision} = \begin{cases}
\text{VERIFIED}, & \text{if } \text{Similarity}(\mathbf{u}, \mathbf{v}) \ge 0.58 \\
\text{REJECTED}, & \text{if } \text{Similarity}(\mathbf{u}, \mathbf{v}) < 0.58
\end{cases}
\]

---

## 4. Database Schema Specification

The database utilizes SQLite located at `database/attendance.db`.

### 4.1 `students` Table (Identity Registry)
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `student_id` | TEXT | PRIMARY KEY | Unique student roll / matriculation ID |
| `name` | TEXT | NOT NULL | Student's full legal name |
| `department` | TEXT | NOT NULL | Academic department (e.g. CSE-DS) |
| `year` | TEXT | NOT NULL | Academic year (1, 2, 3, 4) |
| `consent_status` | TEXT | NOT NULL | Biometric consent ('yes' / 'no') |
| `created_at` | TEXT | NOT NULL | ISO datetime stamp of registration |

### 4.2 `attendance` Table (Event Logs)
| Column Name | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique log transaction identifier |
| `student_id` | TEXT | NOT NULL | Foreign key referencing `students.student_id` |
| `name` | TEXT | NOT NULL | Denormalized student name for fast queries |
| `department` | TEXT | NOT NULL | Academic department |
| `attendance_date` | TEXT | NOT NULL | Date formatted as `YYYY-MM-DD` |
| `entry_time` | TEXT | NOT NULL | 24-hour timestamp formatted as `HH:MM:SS` |
| `similarity_score` | REAL | NOT NULL | Computed cosine similarity value |
| `verification_status`| TEXT | NOT NULL | Status ('VERIFIED' or 'REJECTED') |

---

## 5. Punctuality Classification Rules

Entry timestamps are mapped into operational punctuality categories:

\[
\text{Punctuality}(T) = \begin{cases}
\text{ON TIME}, & T \le 09:30:00 \\
\text{LATE}, & 09:30:01 \le T \le 09:39:59 \\
\text{VERY LATE}, & T \ge 09:40:00
\end{cases}
\]

---

## 6. Security, Anti-Fraud, & Privacy Considerations

1. **Anti-Proxy Protection:** Face embeddings are derived from live face landmarks and depth representations. Verification requires \(\ge 0.58\) angular similarity.
2. **Duplicate Prevention:** A composite query `(student_id, attendance_date, verification_status='VERIFIED')` prevents multiple attendance entries on the same date.
3. **GDPR / Privacy Compliance:** Informed consent (`consent_status = 'yes'`) is mandatory prior to embedding generation or verification. Raw biometric face images can be safely discarded after vector extraction, as only 512-D numeric vectors (`.npy`) are retained.
