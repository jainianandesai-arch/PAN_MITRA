from . import litellm_provider, openai_compatible

PROVIDER_CALLERS = {
    "openai_compatible": openai_compatible.call,
    "litellm": litellm_provider.call,
}
