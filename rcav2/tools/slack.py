# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import logging

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackClient:
    def __init__(self, token: str, channels: list[str] | None = None):
        self.client = WebClient(token=token)
        self.channels = channels or []

    def search_messages(self, query: str, count: int = 20) -> str:
        """Search Slack messages and return formatted text for LLM consumption.

        Returns a formatted string with Slack messages that can be easily
        read and used by the LLM, rather than a list of dicts.
        """
        all_messages: dict[str, dict] = {}

        logging.debug(
            f"Slack search: query='{query}', channels={self.channels}, count={count}"
        )

        for channel in self.channels:
            if not channel:
                continue

            # remove '#' from channel name if present
            channel_name = channel.strip().lstrip("#")
            search_query = f"{query} in:#{channel_name}"

            logging.debug(
                f"Searching Slack channel '{channel_name}' with query: '{search_query}'"
            )

            try:
                result = self.client.search_messages(query=search_query, count=count)
            except SlackApiError as e:
                logging.error(f"Error searching slack in channel {channel}: {e}")
                logging.debug(
                    f"Slack API error details: {e.response if hasattr(e, 'response') else 'N/A'}"
                )
                continue

            messages_for_log: dict = result.get("messages", {})
            matches_count = (
                len(messages_for_log.get("matches", []))
                if isinstance(messages_for_log, dict)
                else 0
            )
            logging.debug(
                f"Slack API response: ok={result.get('ok')}, matches={matches_count}"
            )

            if result["ok"]:
                messages_dict: dict = result.get("messages", {})
                matches = (
                    messages_dict.get("matches", [])
                    if isinstance(messages_dict, dict)
                    else []
                )
                logging.debug(f"Found {len(matches)} matches in channel {channel_name}")
                for match in matches:
                    permalink = match.get("permalink")
                    if permalink and permalink not in all_messages:
                        all_messages[permalink] = {
                            "text": match.get("text"),
                            "user": match.get("user"),
                            "permalink": permalink,
                            "channel": match.get("channel", {}).get("name"),
                        }
            else:
                error = result.get("error", "Unknown error")
                logging.warning(
                    f"Slack search failed for channel {channel_name}: {error}"
                )

        result_count = len(all_messages)
        logging.info(
            f"Slack search completed: query='{query}', total_results={result_count}"
        )

        # Format results as readable text for LLM
        if not all_messages:
            return "No Slack messages found matching the query."

        results_list = list(all_messages.values())

        # Sort by channel name for consistency
        results_list.sort(key=lambda x: (x.get("channel", ""), x.get("permalink", "")))

        # Format as text
        formatted = f"Found {len(results_list)} Slack messages:\n\n"
        for i, msg in enumerate(results_list[:10], 1):  # Limit to top 10
            channel = msg.get("channel", "unknown")
            text = msg.get("text", "")
            permalink = msg.get("permalink", "")

            # Truncate long messages
            text_preview = text[:300] if len(text) > 300 else text

            formatted += f"{i}. Channel: #{channel}\n"
            formatted += f"   Message: {text_preview}\n"
            if len(text) > 300:
                formatted += (
                    "   (message truncated, full text available at link below)\n"
                )
            formatted += f"   Link: {permalink}\n\n"

        if len(results_list) > 10:
            formatted += f"\n(Showing top 10 of {len(results_list)} results. Use the links to view full messages.)\n"

        return formatted
