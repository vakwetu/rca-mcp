# Copyright © 2025 Red Hat
# SPDX-License-Identifier: Apache-2.0

import dspy  # type: ignore[import-untyped]
import os


def get_lm(name: str, max_tokens: int) -> dspy.LM:
    return dspy.LM(
        f"gemini/{name}",
        temperature=0.5,
        max_tokens=max_tokens,
        api_key=os.environ["LLM_GEMINI_KEY"],
    )


def init_dspy() -> None:
    dspy.settings.configure(track_usage=True)
    dspy.configure(lm=get_lm("gemini-2.5-pro", max_tokens=1024 * 1024))


async def emit_dspy_usage(result, worker):
    usages = result.get_lm_usage()
    if usages:
        for model, usage in usages.items():
            await worker.emit(
                dict(
                    model=model,
                    input=usage.get("prompt_tokens"),
                    output=usage.get("completion_tokens"),
                ),
                event="usage",
            )


def get_dspy_history():
    """Get DSPy interaction history for debugging and tracing."""
    try:
        import dspy

        # Try the standard inspect_history first
        history = dspy.inspect_history()
        if history is not None:
            return history

        # If inspect_history() returns None, try to get trace from settings
        settings = dspy.settings
        if hasattr(settings, "trace") and settings.trace:
            return settings.trace

        return []
    except Exception as e:
        print(f"Error getting DSPy history: {e}")
        return []


def extract_llm_interactions(history):
    """Extract LLM interactions from DSPy history."""
    interactions = []

    for i, entry in enumerate(history):
        # Handle trace format: (Predict, input_dict, Prediction)
        if isinstance(entry, tuple) and len(entry) == 3:
            predict_module, input_dict, prediction = entry

            # Extract the signature and input/output
            if hasattr(predict_module, "signature"):
                signature = predict_module.signature

                # Build prompt from signature and input
                prompt_parts = []
                if hasattr(signature, "instructions"):
                    prompt_parts.append(signature.instructions)

                # Add input fields
                for field_name, field_value in input_dict.items():
                    if hasattr(signature, "fields") and field_name in signature.fields:
                        field_info = signature.fields[field_name]
                        if (
                            hasattr(field_info, "json_schema_extra")
                            and "prefix" in field_info.json_schema_extra
                        ):
                            prefix = field_info.json_schema_extra["prefix"]
                            prompt_parts.append(f"{prefix} {field_value}")

                prompt = "\n".join(prompt_parts)

                # Extract response from prediction
                response = ""
                if hasattr(prediction, "report"):
                    response = str(prediction.report)
                elif hasattr(prediction, "completions"):
                    response = str(prediction.completions)

                # Try to get usage information from the prediction
                usage = {}
                if hasattr(prediction, "usage"):
                    usage = prediction.usage
                elif hasattr(prediction, "lm_usage"):
                    usage = prediction.lm_usage

                # Get model from the current LM
                model = "unknown"
                try:
                    import dspy

                    if hasattr(dspy.settings, "lm") and hasattr(
                        dspy.settings.lm, "model"
                    ):
                        model = dspy.settings.lm.model
                except Exception:
                    pass

                if prompt or response:
                    interaction = {
                        "prompt": prompt,
                        "response": response,
                        "usage": usage,
                        "model": model,
                    }
                    interactions.append(interaction)

        # Handle traditional lm_calls format
        elif hasattr(entry, "lm_calls") and entry.lm_calls:
            for call in entry.lm_calls:
                # Extract prompt from messages
                prompt_parts = []
                if hasattr(call, "messages") and call.messages:
                    for message in call.messages:
                        if hasattr(message, "content"):
                            prompt_parts.append(str(message.content))
                        elif isinstance(message, dict) and "content" in message:
                            prompt_parts.append(str(message["content"]))
                        elif isinstance(message, str):
                            prompt_parts.append(message)

                prompt = "\n".join(prompt_parts) if prompt_parts else ""

                # Extract response
                response = ""
                if hasattr(call, "response"):
                    response = str(call.response)
                elif hasattr(call, "completions") and call.completions:
                    response = str(call.completions[0])

                # Extract usage information
                usage = {}
                if hasattr(call, "usage") and call.usage:
                    usage = call.usage
                elif hasattr(call, "token_usage") and call.token_usage:
                    usage = call.token_usage
                elif hasattr(call, "usage_info") and call.usage_info:
                    usage = call.usage_info

                # Extract model information
                model = getattr(call, "model", "unknown")
                if hasattr(call, "lm") and hasattr(call.lm, "model"):
                    model = call.lm.model

                if prompt or response:
                    interactions.append(
                        {
                            "prompt": prompt,
                            "response": response,
                            "usage": usage,
                            "model": model,
                        }
                    )

    return interactions
