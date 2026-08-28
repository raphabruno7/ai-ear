"""Smoke test: are the AWS creds live and can we reach Bedrock?

    python smoke_aws.py

Checks STS identity + one Bedrock `converse` call with the configured model.
Transcribe/SES get exercised in Fase 1 / Fase 4.
"""

import os
import sys

import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

REGION = os.environ["AWS_REGION"]
MODEL = os.environ["BEDROCK_MODEL_ID"]


def main() -> int:
    sts = boto3.client("sts", region_name=REGION)
    who = sts.get_caller_identity()
    print(f"✓ STS identity: {who['Arn']}")

    br = boto3.client("bedrock-runtime", region_name=REGION)
    try:
        resp = br.converse(
            modelId=MODEL,
            messages=[{"role": "user", "content": [{"text": "Reply with the single word: pong"}]}],
            inferenceConfig={"maxTokens": 10, "temperature": 0},
        )
    except ClientError as e:
        code = e.response["Error"]["Code"]
        msg = e.response["Error"]["Message"]
        if "verif" in msg.lower():
            print(f"⏳ Bedrock blocked: account still being verified — retry later.\n   ({msg})")
            return 2
        print(f"✗ Bedrock {code}: {msg}")
        return 1

    text = resp["output"]["message"]["content"][0]["text"].strip()
    usage = resp["usage"]
    print(f"✓ Bedrock {MODEL} → {text!r}  (in={usage['inputTokens']} out={usage['outputTokens']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
