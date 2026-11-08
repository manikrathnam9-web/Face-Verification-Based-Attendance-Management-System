# HTTPS & SSL/TLS Deployment and Cybersecurity Architecture Guide

**Project:** Face Verification Based Smart Attendance Management System  
**Institution:** Kommuri Pratap Reddy Institute of Technology (KPRIT) — UGC Autonomous  
**Department:** Department of Computer Science & Engineering (Data Science / AI & ML)  
**Security Classification:** Confidential / Enterprise Biometric Application

---

## 1. Executive Summary & Deployment Context

This document outlines the security architecture, SSL/TLS configuration, and deployment procedures for the **KPRIT Face Verification Smart Attendance System**.

The system operates across two deployment modes:
1. **Local Development & Station Kiosk Mode (Direct Streamlit TLS):** Direct TLS termination powered by Streamlit's internal Tornado server using self-signed X.509 certificates with Subject Alternative Names (SAN).
2. **Enterprise Production Mode (Nginx Reverse Proxy):** High-performance TLS 1.2/1.3 termination, automatic HTTP $\to$ HTTPS redirection, WebSocket stream proxying (`/_stcore/stream`), automated Let's Encrypt renewal, and defense-in-depth HTTP security response headers.

---

## 2. Local Development & Kiosk HTTPS Setup

### 2.1 Certificate Generation (`scripts/generate_ssl_certs.py`)
Modern Chromium browsers (Google Chrome, Microsoft Edge, Brave) and Firefox strictly require:
- A minimum 2048-bit RSA private key or ECDSA P-256.
- SHA-256 signature algorithm.
- `SubjectAlternativeName` (SAN) extensions for `localhost`, `127.0.0.1`, and hostnames.
- `ExtendedKeyUsage` specifying `ServerAuth`.

The project includes an automated certificate generator powered by Python's `cryptography` library:

```bash
# Generate fresh 365-day certificates with SAN into certs/
python scripts/generate_ssl_certs.py --force
```

Generated files:
- `certs/cert.pem`: Public X.509 Certificate (Subject Alternative Name: `DNS:localhost, IP:127.0.0.1, DNS:host.docker.internal`).
- `certs/key.pem`: Unencrypted 2048-bit RSA Private Key (file permissions restricted to 0600 where supported).

### 2.2 Launching the Local HTTPS Server
You can launch the HTTPS server using any of the following methods:

**Method A: Dedicated HTTPS Launcher (Recommended)**
```bash
python run_https.py
```

**Method B: Main Menu Launcher**
```bash
python main.py --dashboard --https
```
Or run `python main.py` and choose **Option 2: 🔒 Launch Streamlit Web Dashboard (HTTPS / TLS Encrypted)**.

**Method C: Direct Streamlit CLI**
```bash
streamlit run app/dashboard.py --server.sslCertFile certs/cert.pem --server.sslKeyFile certs/key.pem
```

The application will bind to `https://localhost:8501`.

### 2.3 Handling Browser Certificate Warnings for Self-Signed Certs
Because a self-signed certificate is not signed by a commercial Public Certificate Authority (CA), your browser will display an initial security notification:

- **Chrome / Edge:** Click **Advanced** $\to$ Click **Proceed to localhost (unsafe)**.
- **Firefox:** Click **Advanced** $\to$ Click **Accept the Risk and Continue**.

#### Optional: Trusting the Certificate in the Windows Root Store (Permanent Trust)
To eliminate the warning entirely on development/kiosk workstations:
1. Open PowerShell as Administrator.
2. Run the following command:
   ```powershell
   Import-Certificate -FilePath "certs\cert.pem" -CertStoreLocation Cert:\LocalMachine\Root
   ```
3. Restart your browser. `https://localhost:8501` will display a green padlock without warnings.

---

## 3. Production Deployment Architecture (Nginx Reverse Proxy)

In production environments (e.g. cloud VMs, campus servers, or container clusters), direct public exposure of Python servers is discouraged. The project uses an **Nginx reverse proxy container** terminating SSL/TLS before routing requests internally.

### 3.1 Network Topology

```
[ User Browser / Terminal ]
           │
           │ (Port 80 HTTP) ──> [ Nginx: Redirect 301 to HTTPS ]
           │
           │ (Port 443 HTTPS - TLS 1.2/1.3)
           ▼
    [ Nginx Reverse Proxy Container ]
      ├── Terminates TLS & Validates Certificates
      ├── Injects Strict Security Headers (HSTS, CSP, Permissions)
      ├── Upgrades WebSockets (/_stcore/stream)
      └── Applies Rate Limiting & Buffer Controls
           │
           │ (Internal Docker Bridge Network)
           ▼
 [ Streamlit Backend (kprit_smart_attendance:8501) ]
      ├── PBKDF2 Hashing (100k iterations)
      ├── Inactivity Session Timeout Guard
      ├── InsightFace / ArcFace 512-D Biometrics
      └── SQLite Attendance Registry
```

### 3.2 Production Nginx Configuration Highlights (`nginx/nginx.conf`)
- **Automatic HTTP $\to$ HTTPS Redirection:** All traffic on Port 80 is redirected to Port 443 with a 301 Permanent Redirect.
- **Modern TLS Protocols:** Restricts negotiations to `TLSv1.2` and `TLSv1.3`. Legacy insecure protocols (SSLv2, SSLv3, TLS 1.0, TLS 1.1) and weak ciphers are disabled.
- **WebSocket Streaming:** Full proxy support for `Connection: upgrade` and `Upgrade: $http_upgrade` ensuring seamless real-time Streamlit HUD updates.
- **Camera Permissions Policy:** Injects `Permissions-Policy: camera=(self), microphone=(), geolocation=(), payment=()`, which allows webcam capture on the host domain while preventing third-party embeds or unauthorized sensor eavesdropping.

### 3.3 Automated Certificate Renewal (Let's Encrypt / Certbot)
For publicly registered domains (e.g. `attendance.kprit.ac.in`), use the official Let's Encrypt Certbot:

```bash
# 1. Obtain certificates using HTTP-01 challenge
sudo certbot certonly --webroot -w /var/www/certbot -d attendance.kprit.ac.in

# 2. Symlink or mount live certificates into Nginx
ln -s /etc/letsencrypt/live/attendance.kprit.ac.in/fullchain.pem certs/cert.pem
ln -s /etc/letsencrypt/live/attendance.kprit.ac.in/privkey.pem certs/key.pem

# 3. Automatic renewal via systemd timer or cron job
0 3 * * * certbot renew --post-hook "docker-compose exec nginx-proxy nginx -s reload"
```

### 3.4 Deploying with Docker Compose
To deploy the complete production stack with TLS termination:

```bash
docker-compose up -d --build
```

---

## 4. Authentication, Session & Browser Security

| Security Layer | Implementation | Mechanism / Standard |
| :--- | :--- | :--- |
| **Password Hashing** | `app/auth.py` | PBKDF2-HMAC-SHA256 with 100,000 iterations and individual 16-byte cryptographically secure salts. |
| **Credential Comparison** | `app/auth.py` | `secrets.compare_digest()` constant-time string comparison to prevent side-channel timing attacks. |
| **Inactivity Session Timeout** | `app/auth.py` & `app/dashboard.py` | Automatically terminates sessions and purges user state after 30 minutes of idle inactivity (configurable via `SESSION_TIMEOUT_MINUTES`). |
| **HSTS** | `nginx/nginx.conf` | `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` enforces browser HTTPS exclusivity. |
| **MIME Sniffing Defense** | `nginx/nginx.conf` | `X-Content-Type-Options: nosniff` stops MIME-type confusion attacks. |
| **Clickjacking Defense** | `nginx/nginx.conf` | `X-Frame-Options: SAMEORIGIN` prevents unauthorized framing. |
| **Cross-Site Request Forgery** | `.streamlit/config.toml` | `enableXsrfProtection = true` and `enableCORS = true` validate request tokens and origin boundaries. |
| **Sensor & Hardware Security**| `nginx/nginx.conf` | `Permissions-Policy: camera=(self), microphone=(), geolocation=()` restricts camera access strictly to first-party biometric verification. |

---

## 5. Biometric Data & Secret Protection

### 5.1 Biometric Template Protection
- **Storage Isolation:** 512-dimensional facial embeddings are stored as binary NumPy arrays in `data/embeddings/<student_id>_embedding.npy`.
- **Informed Consent Enforcement:** Biometric enrollment strictly requires explicit informed student consent (`consent="yes"`). Any attempt to enroll a student without consent is blocked.
- **Privacy & Sanitization:** Facial embeddings and raw feature vectors are never transmitted to external APIs or dumped into logs.

### 5.2 Version Control Guards (`.gitignore`)
The repository includes a comprehensive `.gitignore` configuration preventing accidental commits of:
- Cryptographic private keys (`certs/*.pem`, `certs/*.key`)
- Biometric embeddings (`data/embeddings/*.npy`)
- Enrollment metadata (`data/enrollment/*.json`)
- Attendance databases (`database/*.db`, `database/*.sqlite`)
- Environment secrets (`.env`, `.env.local`)
- Streamlit secrets (`.streamlit/secrets.toml`)

---

## 6. Verification & Audit Results

The cybersecurity and TLS implementation has been verified through automated test suites:
- `tests/test_security_and_https.py`: Verified PBKDF2 hashing, timing safety, session timeout expiration, X.509 certificate validity, SAN entries, `.gitignore` rules, consent checks, and Nginx header definitions (7/7 tests passed).
- `tests/test_https_live_handshake.py`: Verified live TLS handshake on port 8503, valid cipher negotiation, and encrypted 200 OK health response.
- `tests/test_live_attendance.py`: Verified complete backward compatibility for face verification, live webcam processing, duplicate prevention, and punctuality analysis (7/7 tests passed).
- `tests/test_sidebar_and_navigation.py`: Verified UI responsiveness and navigation functionality (5/5 tests passed).
