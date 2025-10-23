# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0
import os

try:
    SF_DOMAIN = os.environ["SF_DOMAIN"]
except KeyError:
    raise ValueError("The SF_DOMAIN environment variable must be set") from None


SF_URL = f"https://{SF_DOMAIN}"
CA_BUNDLE_PATH = os.environ.get(
    "CA_BUNDLE_PATH", "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
)
COOKIE_FILE = os.environ.get("COOKIE_FILE", ".cookie")
DATABASE_FILE = os.environ.get("DATABASE_FILE", ".db.sqlite3")
JOB_DESCRIPTION_FILE = os.environ.get("JOB_DESCRIPTION_FILE")
