# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

"""
This module defines the system configuration from the process os.environ.
"""

import os

SF_DOMAIN = os.environ.get("SF_DOMAIN")

SF_URL = f"https://{SF_DOMAIN}"

# JIRA configuration (optional - only needed if using JIRA tools)
JIRA_URL = os.environ.get("JIRA_URL")
JIRA_API_KEY = os.environ.get("JIRA_API_KEY")
# Comma-separated list of projects to search for related tickets during RCA
JIRA_RCA_PROJECTS = os.environ.get("JIRA_RCA_PROJECTS")

# Slack configuration (optional - only needed if using slack tools)
SLACK_API_KEY = os.environ.get("SLACK_API_KEY")
SLACK_SEARCH_CHANNELS = os.environ.get("SLACK_SEARCH_CHANNELS")

CA_BUNDLE_PATH = os.environ.get(
    "CA_BUNDLE_PATH", "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem"
)
COOKIE_FILE = os.environ.get("COOKIE_FILE", ".cookie")
DATABASE_FILE = os.environ.get("DATABASE_FILE", ".db.sqlite3")
JOB_DESCRIPTION_FILE = os.environ.get("JOB_DESCRIPTION_FILE")

# Opik configuration
OPIK_PROJECT_NAME = os.environ.get("OPIK_PROJECT_NAME", "rca-api")
OPIK_URL_OVERRIDE = os.environ.get("OPIK_URL_OVERRIDE")


# LLM configuration
def _get_temperature() -> float:
    """Get LLM temperature from environment variable, defaulting to 0.5."""
    temp_str = os.environ.get("LLM_TEMPERATURE", "0.5")
    try:
        temperature = float(temp_str)
        if temperature < 0.0:
            print(
                f"Warning: LLM_TEMPERATURE={temperature} is negative. Using default 0.5."
            )
            return 0.5
        return temperature
    except ValueError:
        print(
            f"Warning: LLM_TEMPERATURE={temp_str} is not a valid float. Using default 0.5."
        )
        return 0.5


LLM_TEMPERATURE = _get_temperature()
