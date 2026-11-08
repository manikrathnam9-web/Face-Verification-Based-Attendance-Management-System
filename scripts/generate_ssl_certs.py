"""
SSL/TLS Certificate Generator for Face Verification Attendance System
Generates standard X.509 self-signed certificates with Subject Alternative Names (SAN)
for secure local HTTPS development and testing.

Complies with modern browser security requirements:
- 2048-bit RSA Private Key
- SHA-256 Signature Algorithm
- Subject Alternative Names (SAN): DNS:localhost, IP:127.0.0.1, DNS:host.docker.internal
- Server Authentication Extended Key Usage (EKU)
"""

import os
import sys
import ipaddress
import argparse
import datetime
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CERTS_DIR = os.path.join(PROJECT_ROOT, "certs")


def generate_certificates(
    output_dir: str = CERTS_DIR,
    days: int = 365,
    common_name: str = "localhost",
    force: bool = False
) -> tuple:
    """
    Generates a secure RSA private key and self-signed X.509 certificate with SAN.
    Returns (cert_path, key_path).
    """
    os.makedirs(output_dir, exist_ok=True)
    cert_path = os.path.join(output_dir, "cert.pem")
    key_path = os.path.join(output_dir, "key.pem")

    if os.path.exists(cert_path) and os.path.exists(key_path) and not force:
        print(f"[SSL] Certificates already exist at:\n  - Cert: {cert_path}\n  - Key:  {key_path}")
        print("[SSL] Use --force or delete existing files to regenerate.")
        return cert_path, key_path

    print(f"[SSL] Generating 2048-bit RSA private key...")
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    print(f"[SSL] Constructing X.509 certificate for CN={common_name} (valid {days} days)...")
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "IN"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Telangana"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "Hyderabad"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "KPRIT Biometric Attendance"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Department of CSE"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # Modern browsers require SAN (Subject Alternative Names) for HTTPS verification
    san_names = [
        x509.DNSName("localhost"),
        x509.DNSName("host.docker.internal"),
        x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
    ]
    if common_name != "localhost":
        san_names.append(x509.DNSName(common_name))

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=days))
        .add_extension(
            x509.SubjectAlternativeName(san_names),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([
                ExtendedKeyUsageOID.SERVER_AUTH,
                ExtendedKeyUsageOID.CLIENT_AUTH,
            ]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    # Write Private Key with restrictive permissions
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    # Write Certificate
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))

    # Set file permissions if on POSIX
    if hasattr(os, "chmod"):
        try:
            os.chmod(key_path, 0o600)
            os.chmod(cert_path, 0o644)
        except OSError:
            pass

    print("[SSL] Successfully generated TLS certificates:")
    print(f"  - Certificate: {cert_path}")
    print(f"  - Private Key: {key_path}")
    print(f"  - Valid from:  {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  - Expires on:  {(now + datetime.timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  - SAN Entries: localhost, 127.0.0.1, host.docker.internal")
    return cert_path, key_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate self-signed SSL/TLS certificates for local HTTPS.")
    parser.add_argument("--output-dir", default=CERTS_DIR, help="Destination directory for cert.pem and key.pem")
    parser.add_argument("--days", type=int, default=365, help="Validity period in days (default: 365)")
    parser.add_argument("--cn", default="localhost", help="Common Name / domain (default: localhost)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing certificates")

    args = parser.parse_args()
    generate_certificates(
        output_dir=args.output_dir,
        days=args.days,
        common_name=args.cn,
        force=args.force
    )
