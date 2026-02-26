"""Token counting utilities for Gemini API."""

def extract_total_tokens(count_response):
    """Extract total_tokens from count_tokens API response (handle multiple formats)."""
    if hasattr(count_response, "total_tokens"):
        return count_response.total_tokens
    if isinstance(count_response, dict) and "total_tokens" in count_response:
        return count_response["total_tokens"]
    if isinstance(count_response, dict) and "totalTokens" in count_response:
        return count_response["totalTokens"]
    raise ValueError("Unable to read total_tokens from count_tokens response.")

def count_tokens(client, model_name, prompt):
    """Count tokens in a prompt for a given model."""
    response = client.models.count_tokens(model=model_name, contents=prompt)
    return extract_total_tokens(response)
