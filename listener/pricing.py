"""Manual price snapshot for per-call cost. Check the AWS pricing pages when
numbers look off — these drift.

ponytail: hardcoded USD constants, no live pricing API. Update by hand; if
Bedrock/Transcribe pricing changes materially, edit here and re-run the cost
dashboard. A pricing-API lookup is not worth it for a portfolio demo.
"""

# AWS Transcribe streaming — tier 1, USD per second (=$0.02400/min), us-east-1.
TRANSCRIBE_USD_PER_SEC = 0.024 / 60

# Bedrock Claude 3.5 Haiku — USD per token, us-east-1 on-demand.
BEDROCK_HAIKU_USD_PER_INPUT_TOKEN = 0.80 / 1_000_000
BEDROCK_HAIKU_USD_PER_OUTPUT_TOKEN = 4.00 / 1_000_000


def stt_cost(seconds: float) -> float:
    return seconds * TRANSCRIBE_USD_PER_SEC


def llm_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens * BEDROCK_HAIKU_USD_PER_INPUT_TOKEN
        + output_tokens * BEDROCK_HAIKU_USD_PER_OUTPUT_TOKEN
    )


def demo() -> None:
    # 8-min call, ~3k input + ~500 output tokens per extraction x ~16 turns.
    assert abs(stt_cost(480) - 0.192) < 1e-6
    c = llm_cost(3000 * 16, 500 * 16)
    assert 0.06 < c < 0.08, c
    print("pricing demo ok:", round(stt_cost(480) + c, 4), "USD / 8-min call")


if __name__ == "__main__":
    demo()
