"""Manual price snapshot for per-call cost. Check the AWS pricing pages when
numbers look off — these drift.

ponytail: hardcoded USD constants, no live pricing API. Update by hand; if
Bedrock/Transcribe pricing changes materially, edit here and re-run the cost
dashboard. A pricing-API lookup is not worth it for a portfolio demo.
"""

# AWS Transcribe streaming — tier 1, USD per second (=$0.02400/min), us-east-1.
TRANSCRIBE_USD_PER_SEC = 0.024 / 60

# LLM rates, USD per 1M tokens (input, output). Manual snapshots — verify on the
# provider pricing pages if the /costs numbers look off.
#   bedrock : Claude Haiku 4.5, us-east-1 on-demand
#   gemini  : gemini-3.6-flash on Vertex AI, introductory rate (through 2026-12-31;
#             standard is 1.50/7.50) — https://cloud.google.com/vertex-ai/generative-ai/pricing
LLM_RATES = {
    "bedrock": (0.80, 4.00),
    "gemini": (0.75, 3.75),
}


def stt_cost(seconds: float) -> float:
    return seconds * TRANSCRIBE_USD_PER_SEC


def llm_cost(input_tokens: int, output_tokens: int, backend: str = "bedrock") -> float:
    in_rate, out_rate = LLM_RATES.get(backend, LLM_RATES["bedrock"])
    return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000


def demo() -> None:
    # 8-min call, ~3k input + ~500 output tokens per extraction x ~16 turns.
    assert abs(stt_cost(480) - 0.192) < 1e-6
    c = llm_cost(3000 * 16, 500 * 16, "bedrock")
    assert 0.06 < c < 0.08, c
    g = llm_cost(3000 * 16, 500 * 16, "gemini")
    assert 0.05 < g < 0.07, g
    assert llm_cost(100, 100, "unknown") == llm_cost(100, 100, "bedrock")  # safe fallback
    print("pricing demo ok:", round(stt_cost(480) + c, 4), "USD / 8-min call (bedrock)")


if __name__ == "__main__":
    demo()
