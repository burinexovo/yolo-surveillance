# modules/line_notify.py
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Union

from linebot.v3.messaging.models.broadcast_request import BroadcastRequest
from linebot.v3.messaging.models.push_message_request import PushMessageRequest
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    TextMessage,
    ImageMessage,
)


@dataclass(frozen=True)
class LineConfig:
    access_token: str
    user_file: Union[str, Path]


def load_users(user_file: Union[str, Path]) -> Dict[str, Any]:
    user_file = Path(user_file)
    with user_file.open("r", encoding="utf-8") as f:
        return json.load(f)


def broadcast_message(cfg: LineConfig, msg: str) -> None:
    configuration = Configuration(access_token=cfg.access_token)

    with ApiClient(configuration) as api_client:
        msg_api = MessagingApi(api_client)
        msg_api.broadcast(
            BroadcastRequest(messages=[TextMessage(text=msg)]),
            x_line_retry_key=str(uuid.uuid4())
        )


def push_message(cfg: LineConfig, msg: str, img_url: Optional[str] = None) -> None:
    users = load_users(cfg.user_file)
    configuration = Configuration(access_token=cfg.access_token)

    with ApiClient(configuration) as api_client:
        msg_api = MessagingApi(api_client)

        for uid, info in users.items():
            if not info.get("notifications_enabled", True):
                continue

            if img_url:
                msg_api.push_message(
                    PushMessageRequest(
                        to=uid,
                        messages=[
                            TextMessage(text=msg),
                            ImageMessage(
                                originalContentUrl=img_url,
                                previewImageUrl=img_url,
                            ),
                        ],
                    )
                )
            else:
                msg_api.push_message(
                    PushMessageRequest(
                        to=uid,
                        messages=[TextMessage(text=msg)],
                    )
                )
