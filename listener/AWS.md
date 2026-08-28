# AWS setup — one-time, ~20 min

The listener needs one IAM user with access to **Bedrock** (extraction),
**Transcribe** (streaming STT) and **SES** (briefing email). All in **one region**
— use `us-east-1` (has Bedrock + all Anthropic models, and the biggest free tier).

## 1. Create the account
- https://aws.amazon.com → "Create an AWS Account". Card required (verification hold, refunded).
- New accounts get the **Free Tier** (12 months) + a promotional credit on many services.
- Transcribe: 60 audio-minutes/month free for 12 months. SES: 3,000 messages/month free forever.
- Bedrock has **no free tier**, but Claude 3.5 Haiku is ~$0.80/1M input, $4/1M output —
  the whole golden-set + demo runs for **cents**. Set a billing alert anyway (step 5).

## 2. Enable Bedrock model access
- Console → **Bedrock** → region `us-east-1` → left nav **Model access** → **Manage model access**.
- Request access to **Anthropic → Claude 3.5 Haiku** (and Claude 3 Haiku as a fallback).
- Approval is usually instant. `BEDROCK_MODEL_ID` in `.env` is
  `anthropic.claude-3-5-haiku-20241022-v1:0`.

## 3. Verify an SES sender
- Console → **SES** → **Verified identities** → create identity → email address →
  click the link in the confirmation email. Use this as `SES_FROM_EMAIL`.
- New SES accounts are in the **sandbox**: you can only send *to* verified addresses.
  For the demo that's fine — verify your own address as `SES_TO_EMAIL` too.
  (Production would request sandbox removal; out of scope here.)

## 4. Create the IAM user
- Console → **IAM** → Users → Create user → name `call-copilot-listener`,
  **no** console access.
- Attach a **customer inline policy** (paste below), then
  **Security credentials → Create access key → Application running outside AWS**.
- Put the key id / secret into `.env` as `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "Bedrock",
      "Effect": "Allow",
      "Action": ["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-haiku-*"
    },
    {
      "Sid": "Transcribe",
      "Effect": "Allow",
      "Action": ["transcribe:StartStreamTranscription", "transcribe:StartStreamTranscriptionWebSocket"],
      "Resource": "*"
    },
    {
      "Sid": "SES",
      "Effect": "Allow",
      "Action": ["ses:SendEmail"],
      "Resource": "*"
    }
  ]
}
```

## Fresh-account Bedrock quota

New AWS accounts get a tiny **daily token quota** on Bedrock (`ThrottlingException:
Too many tokens per day` on the first call). It lifts automatically within ~24h of
account activity. To raise it sooner: **Service Quotas → Amazon Bedrock →** search the
per-model "tokens per day" / "tokens per minute" quotas → request increase.
`smoke_aws.py` returning `ThrottlingException` means auth + model access are already
working — only the volume cap is in the way.

## 5. Billing alert (do this)
- Console → **Billing → Budgets** → create a **$10 monthly cost budget** with an
  email alert at 50% and 100%. Cheap insurance against a runaway loop.

## 6. Smoke test (after `.env` is filled)
```bash
cd listener && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python smoke_aws.py   # added in Fase 1 — pings Bedrock + Transcribe + SES
```
