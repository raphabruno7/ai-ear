"""FieldsWS routing check: a subscriber gets only its session's broadcasts."""

import asyncio
import json

import websockets

from ws_server import FieldsWS

PORT = 8799


async def main() -> None:
    ws = FieldsWS(port=PORT)
    await ws.start()

    async with websockets.connect(f"ws://localhost:{PORT}") as a, \
               websockets.connect(f"ws://localhost:{PORT}") as b:
        await a.send(json.dumps({"type": "subscribe", "session_id": "s1"}))
        await b.send(json.dumps({"type": "subscribe", "session_id": "s2"}))
        await asyncio.sleep(0.1)

        await ws.broadcast("s1", {"owner_name": "Kathleen"})

        msg = json.loads(await asyncio.wait_for(a.recv(), timeout=2))
        assert msg["type"] == "fields" and msg["session_id"] == "s1", msg
        assert msg["fields"] == {"owner_name": "Kathleen"}, msg
        assert isinstance(msg["sent_at"], (int, float)), msg

        # b (session s2) must NOT receive s1's broadcast
        try:
            await asyncio.wait_for(b.recv(), timeout=0.5)
            raise AssertionError("s2 subscriber received s1 broadcast — isolation broken")
        except asyncio.TimeoutError:
            pass

    await ws.stop()
    print("ws server routing demo ok")


if __name__ == "__main__":
    asyncio.run(main())
