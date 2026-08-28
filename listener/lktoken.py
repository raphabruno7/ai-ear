"""LiveKit access-token helpers, shared by the listener and sim_call."""

import os

from livekit import api


def _key_secret() -> tuple[str, str]:
    return os.environ["LIVEKIT_API_KEY"], os.environ["LIVEKIT_API_SECRET"]


def listener_token(room: str, identity: str = "copilot-listener") -> str:
    key, secret = _key_secret()
    grants = api.VideoGrants(
        room_join=True, room=room,
        can_subscribe=True, can_publish=False, can_publish_data=False,
    )
    return api.AccessToken(key, secret).with_identity(identity).with_grants(grants).to_jwt()


def publisher_token(room: str, identity: str) -> str:
    key, secret = _key_secret()
    grants = api.VideoGrants(
        room_join=True, room=room,
        can_subscribe=False, can_publish=True,
    )
    return api.AccessToken(key, secret).with_identity(identity).with_grants(grants).to_jwt()
