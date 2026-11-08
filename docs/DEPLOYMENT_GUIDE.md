# Production Deployment Guide
## KPRIT Face Verification-Based Smart Attendance System

---

## Overview

This guide outlines **four deployment options** to launch the Smart Attendance System as a secure, live website:
1. **Option 1: Streamlit Community Cloud (Free, 1-Click Hosting)** — Best for project presentations, external access, and testing.
2. **Option 2: Cloud Virtual Machine (AWS EC2, DigitalOcean, Azure) with Nginx + HTTPS** — Best for official college web hosting with a custom domain (e.g. `attendance.kprit.ac.in`).
3. **Option 3: Docker & Docker Compose** — Best for containerized, portable server hosting.
4. **Option 4: KPRIT Campus LAN / Intranet Hosting** — Best for local campus deployment on college Wi-Fi without internet egress.

---

## 🔒 Security Credentials & Access Management

The system enforces strict role-based authentication (`PBKDF2-HMAC-SHA256` with individual salts and 100,000 iterations). Credentials are read exclusively from environment variables or a `.env` file; no hardcoded default fallback passwords are provided.

| Role | Username Variable | Password Variable | Permissions |
| :--- | :--- | :--- | :--- |
| **Faculty / Admin** | `ADMIN_USERNAME` (`admin`) | `ADMIN_PASSWORD` (Required) | Full administrative access: Analytics, Enrollment, Roster, CSV Export, Threshold Evaluation. |
| **Campus Kiosk** | `KIOSK_USERNAME` (`kiosk`) | `KIOSK_PASSWORD` (Required) | Restricted self-service mode: Camera Attendance only. Student records and admin tools are hidden. |

> [!IMPORTANT]
> **Environment Variables Required:** Before starting the application, set `ADMIN_PASSWORD` and `KIOSK_PASSWORD` in your `.env` file (or host environment). If either variable is missing, the portal will fail safely with an authentication configuration alert rather than allowing unauthorized access or defaulting to known credentials.

---

## Option 1: Free Cloud Deployment (Streamlit Community Cloud)

Streamlit Community Cloud allows free 24/7 web hosting directly from your GitHub repository.

### Step-by-Step:
1. **Push Code to GitHub:**
   ```bash
   git init
   git add .
   git commit -m "KPRIT Smart Attendance Production Release"
   git remote add origin https://github.com/<your-username>/Face_Verification_Attendance.git
   git branch -M main
   git push -u origin main
   ```

2. **Sign in to Streamlit Cloud:**
   - Navigate to [share.streamlit.io](https://share.streamlit.io/) and log in with your GitHub account.

3. **Deploy the App:**
   - Click **"New App"**.
   - Select your repository: `<your-username>/Face_Verification_Attendance`.
   - Set **Branch:** `main`.
   - Set **Main file path:** `app/dashboard.py`.
   - Under **Advanced Settings**, select **Python 3.11**.
   - Click **Deploy!**

4. **Access Your Live Website:**
   - Within 2-3 minutes, your app is live at `https://<your-app-name>.streamlit.app` with automatic HTTPS (SSL enabled for camera permissions).

---

## Option 2: Production Cloud VPS (AWS EC2 / DigitalOcean / Azure)

Deploying on a dedicated Linux VPS (Ubuntu 22.04 / 24.04) with **Nginx Reverse Proxy**, **Systemd Daemon**, and **Let's Encrypt SSL (HTTPS)**.

### Architecture:
```
Client Browser (HTTPS) ---> Nginx Reverse Proxy (Port 443) ---> Streamlit (Port 8501)
```

### Step 1: Server Setup & Dependencies
```bash
# Update Ubuntu packages
sudo apt update && sudo apt upgrade -y

# Install Python, Nginx, Git, and OpenCV libraries
sudo apt install -y python3-pip python3-venv git nginx certbot python3-certbot-nginx \
    libgl1 libglib2.0-0 libgomp1 build-essential
```

### Step 2: Clone Repository & Virtual Environment
```bash
# Clone to /var/www/
cd /var/www
sudo git clone https://github.com/<your-username>/Face_Verification_Attendance.git attendance
sudo chown -R $USER:$USER /var/www/attendance
cd /var/www/attendance

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Systemd Service (Auto-Start & 24/7 Uptime)
Create service file:
```bash
sudo nano /etc/systemd/system/attendance.service
```
Paste configuration:
```ini
[Unit]
Description=KPRIT Smart Attendance Web Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/var/www/attendance
ExecStart=/var/www/attendance/.venv/bin/streamlit run app/dashboard.py --server.port=8501 --server.address=127.0.0.1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```
Enable and start service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable attendance
sudo systemctl start attendance
sudo systemctl status attendance
```

### Step 4: Configure Nginx Reverse Proxy
```bash
sudo nano /etc/nginx/sites-available/attendance
```
Paste configuration (replace `attendance.kprit.ac.in` with your domain or server IP):
```nginx
server {
    listen 80;
    server_name attendance.kprit.ac.in;

    location / {
        proxy_pass http://127.0.0.1:8501;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 86400;
    }
}
```
Enable Nginx site:
```bash
sudo ln -s /etc/nginx/sites-available/attendance /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Step 5: Enable Free HTTPS (SSL Certificate)
> Modern browsers require HTTPS to grant camera permissions!
```bash
sudo certbot --nginx -d attendance.kprit.ac.in
```

Your system is now live at `https://attendance.kprit.ac.in`!

---

## Option 3: Docker & Docker Compose Deployment

If your server has Docker installed, you can launch the entire stack in one command.

### 1. Build and Run Container
```bash
# Clone repository
git clone https://github.com/<your-username>/Face_Verification_Attendance.git
cd Face_Verification_Attendance

# Start in background
docker compose up -d --build
```

### 2. Verify Container Status
```bash
docker compose ps
docker compose logs -f
```

### 3. Access
Open `http://<server-ip>:8501` in your browser. All facial embeddings and attendance databases persist on the host machine in `./data` and `./database`.

---

## Option 4: KPRIT Campus LAN / Intranet Hosting

Run the system on a college laboratory workstation and allow faculty tablets/laptops connected to the **KPRIT Wi-Fi** network to access the portal.

### 1. Find Your Host Machine's Local IP Address
In PowerShell:
```powershell
ipconfig
# Look for IPv4 Address (e.g. 192.168.1.45 or 10.0.x.x)
```

### 2. Allow Inbound Traffic on Port 8501 (Windows Firewall)
Run PowerShell as Administrator:
```powershell
New-NetFirewallRule -DisplayName "KPRIT Smart Attendance" -Direction Inbound -LocalPort 8501 -Protocol TCP -Action Allow
```

### 3. Start the Server
```powershell
.\.venv\Scripts\python.exe -m streamlit run app/dashboard.py --server.port=8501 --server.address=0.0.0.0
```

### 4. Connect from Any Campus Device
From any tablet, phone, or laptop connected to the college Wi-Fi:
```
http://192.168.1.45:8501
```

> [!NOTE]
> **Camera Permission on LAN (HTTP):**
> Chrome blocks camera access over plain HTTP unless it is `localhost` or explicitly allowed.
> To allow camera access on tablets connecting via LAN IP:
> 1. In Chrome on the client device, go to: `chrome://flags/#unsafely-treat-insecure-origin-as-secure`
> 2. Add `http://192.168.1.45:8501` and click **Enable**.
> 3. Restart Chrome.

---

## 🛠️ Maintenance & Backup

### 1. Database Backup
To backup all student profiles, attendance history, and user credentials:
```powershell
# Windows
Copy-Item database/attendance.db "database/backup_$(Get-Date -Format 'yyyyMMdd').db"

# Linux
cp database/attendance.db database/backup_$(date +%Y%m%d).db
```

### 2. Exporting Attendance Data
Use the master CLI to export attendance anytime:
```powershell
python main.py --export
```
Output files are saved to `data/exports/`.
