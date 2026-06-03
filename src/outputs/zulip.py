import base64
import httpx
from src.models import AppConfig


async def post_to_zulip(content: str, config: AppConfig) -> None:
    if not config.zulip_email or not config.zulip_api_key or not config.zulip_server_url:
        raise ValueError("Zulip credentials not configured")

    credentials = base64.b64encode(
        f"{config.zulip_email}:{config.zulip_api_key}".encode()
    ).decode()

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{config.zulip_server_url}/api/v1/messages",
            headers={"Authorization": f"Basic {credentials}"},
            data={
                "type": "stream",
                "to": config.zulip_stream,
                "topic": config.zulip_topic,
                "content": content,
            },
        )
        response.raise_for_status()
