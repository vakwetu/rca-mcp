import os
import logging

import dspy
import opik
import opik.integrations.dspy


# Configure logging to align with existing app logging style
logging.getLogger("dspy").setLevel(logging.INFO)


# Basic DSPy configuration; allow environment to override
def configure_default_lm():
    # Back-compat: support legacy env var LLM_GEMINI_KEY by mapping it to
    # the variables expected by LiteLLM / Gemini providers.
    # If either GEMINI_API_KEY or GOOGLE_API_KEY is already set, we don't override.
    legacy_key = os.environ.get("LLM_GEMINI_KEY")
    if legacy_key:
        os.environ.setdefault("GEMINI_API_KEY", legacy_key)
        os.environ.setdefault("GOOGLE_API_KEY", legacy_key)

    # Choose a default LM compatible with existing DEFAULT_MODEL semantics
    # Fallback to a generic openai adapter if env provides OPENAI_BASE_URL
    model = os.environ.get("RCAV2_DSPY_LM", "gemini/gemini-2.5-flash")

    # Allow overriding max tokens via env; otherwise set a high, model-aware default.
    # DSPy/LiteLLM will clamp to provider limits when necessary.
    max_tokens_env = os.environ.get("RCAV2_DSPY_MAX_TOKENS")
    if max_tokens_env:
        try:
            max_tokens = int(max_tokens_env)
        except ValueError:
            max_tokens = None
    else:
        max_tokens = 8192 if model.startswith("gemini/") else None

    return dspy.LM(model, **({"max_tokens": max_tokens} if max_tokens is not None else {}))


def configure_callbacks():
    try:
        project_name = f"{os.environ.get('USER', 'rca')}-RCAv2"
        opik.configure(url=os.environ.get("OPIK_URL", "http://localhost:5173/api/"), use_local=True, force=True)
        return [opik.integrations.dspy.callback.OpikCallback(project_name=project_name, log_graph=True)]
    except Exception:
        return []


def configure_dspy():
    dspy.configure_cache(enable_disk_cache=False, enable_memory_cache=False)
    dspy.configure(lm=configure_default_lm(), callbacks=configure_callbacks())


class RCAAnalysis(dspy.Signature):
    """
    You are a CI engineer. Analyze the provided build error report and produce
    a concise root cause analysis with likely failure points, implicated
    components, and suggested next steps.
    """
    prompt: str = dspy.InputField(desc="A compiled error report including context from logs")
    analysis: str = dspy.OutputField(desc="Root cause analysis and suggested remediation steps")


async def analyze_report(prompt: str):
    """Async generator that yields (message, event) to mirror rcav2.model.query.

    - event "chunk": streaming content
    - event "usage": cost/usage metadata if available
    """
    configure_dspy()

    # Create a simple ReAct agent with no external tools for now
    agent = dspy.ReAct(RCAAnalysis, tools=[], max_iters=64)

    # DSPy does not stream tokens by default; emulate chunking by splitting paragraphs
    result = await agent.acall(prompt=prompt)
    text = getattr(result, "analysis", None) or str(result)

    for para in text.split("\n\n"):
        # Maintain similar semantics to existing model.query
        yield (para + "\n\n", "chunk")

    # If the underlying LM exposes usage via dspy, surface a minimal structure
    try:
        lm = dspy.settings.lm
        usage = getattr(lm, "last_usage", None)
        if usage:
            yield (dict(input=usage.get("input", 0), output=usage.get("output", 0)), "usage")
    except Exception:
        pass 