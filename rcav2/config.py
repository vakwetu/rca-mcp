# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0
import os

SF_DOMAIN = os.environ["SF_DOMAIN"]
SF_URL = f"https://{SF_DOMAIN}"
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_SYSTEM_PROMPT = (
    "You are a CI engineer, your goal is to find the RCA of this build failure."
)
