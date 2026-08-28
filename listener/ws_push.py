"""Dev tool: run the fields WS standalone and dribble a fake extraction into it,
so the Chrome extension + demo-scheduler can be demoed without AWS.

    python ws_push.py --session demo-1

Then in the extension popup: WS URL ws://localhost:8765, Session ID demo-1, Connect.
Open http://localhost:3000/demo-scheduler and watch it fill.
"""

import argparse
import asyncio

from ws_server import FieldsWS

STEPS = [
    {"owner_name": "Kathleen O'Brien"},
    {"owner_phone": "617-555-0142"},
    {"owner_email": "kathleen.obrien@gmail.com"},
    {"pet_name": "Luna"},
    {"visit_type": "Sick visit — not eating"},
    {"preferred_time": "Tomorrow 3:00 PM"},
    {"clinical_notes": "Not eating for ~2 days, lethargic. Golden retriever, 4 yrs."},
]


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--session", default="demo-1")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--interval", type=float, default=2.5)
    args = ap.parse_args()

    ws = FieldsWS(port=args.port)
    await ws.start()
    print(f"WS on :{args.port}, session {args.session!r}. Ctrl+C to stop.")

    fields: dict[str, str] = {}
    while True:
        for step in STEPS:
            fields.update(step)
            await ws.broadcast(args.session, dict(fields))
            print("  ->", step)
            await asyncio.sleep(args.interval)
        await asyncio.sleep(args.interval * 2)
        fields.clear()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
