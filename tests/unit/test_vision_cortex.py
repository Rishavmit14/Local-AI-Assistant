import base64
import json

import httpx
import pytest
from PIL import Image

from local_ai_assistant.common.config import VisionCortexConfig
from local_ai_assistant.perception.vision_cortex import LocalVisionCortex, VisionCortexUnavailable


def png(path, size=(640, 480)):
    Image.new("RGB", size, "#336699").save(path)
    return path


def test_local_vision_cortex_sends_bounded_pixels_only_to_verified_loopback(tmp_path):
    requests = []

    def handle(request):
        requests.append(request)
        assert request.headers.get("authorization") == "Bearer unit-test-vision-key-with-at-least-32-chars"
        if request.url.path == "/props":
            return httpx.Response(200, json={
                "modalities": {"vision": True},
                "model_alias": "friday-vision-qwen2.5-vl-3b",
            })
        assert request.url.path == "/v1/chat/completions"
        body = json.loads(request.content)
        assert body["model"] == "friday-vision-qwen2.5-vl-3b"
        image_item = body["messages"][1]["content"][1]
        data_uri = image_item["image_url"]["url"]
        assert data_uri.startswith("data:image/jpeg;base64,")
        image_bytes = base64.b64decode(data_uri.split(",", 1)[1])
        with Image.open(__import__("io").BytesIO(image_bytes)) as image:
            assert image.size == (320, 240)
        return httpx.Response(200, json={
            "id": "local-test",
            "object": "chat.completion",
            "created": 1,
            "model": "friday-vision-qwen2.5-vl-3b",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "A blue rectangle fills the frame."}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 8, "total_tokens": 18},
        })

    http = httpx.Client(transport=httpx.MockTransport(handle), trust_env=False)
    adapter = LocalVisionCortex(
        VisionCortexConfig(
            base_url="http://127.0.0.1:8781/v1",
            api_key="unit-test-vision-key-with-at-least-32-chars",
            max_image_edge=320,
        ),
        http_client=http,
    )

    evidence = adapter.describe(png(tmp_path / "screen.png"), "What is visible?")

    assert evidence.summary == "A blue rectangle fills the frame."
    assert evidence.input_bytes > 0
    assert [request.url.host for request in requests] == ["127.0.0.1", "127.0.0.1"]
    assert "screen.png" not in requests[1].content.decode()


def test_local_vision_cortex_rejects_text_only_server_before_image_request(tmp_path):
    paths = []

    def handle(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"modalities": {"vision": False}})

    http = httpx.Client(transport=httpx.MockTransport(handle), trust_env=False)
    adapter = LocalVisionCortex(
        VisionCortexConfig(
            base_url="http://localhost:8781/v1",
            api_key="unit-test-vision-key-with-at-least-32-chars",
        ),
        http_client=http,
    )

    with pytest.raises(VisionCortexUnavailable, match="does not accept images"):
        adapter.describe(png(tmp_path / "input.png"), "Describe this")

    assert paths == ["/props"]


def test_local_vision_cortex_requires_exact_advertised_model_identity(tmp_path):
    paths = []

    def handle(request):
        paths.append(request.url.path)
        return httpx.Response(200, json={"modalities": {"vision": True}})

    http = httpx.Client(transport=httpx.MockTransport(handle), trust_env=False)
    adapter = LocalVisionCortex(
        VisionCortexConfig(
            base_url="http://localhost:8781/v1",
            api_key="unit-test-vision-key-with-at-least-32-chars",
        ),
        http_client=http,
    )

    with pytest.raises(VisionCortexUnavailable, match="identity does not match"):
        adapter.describe(png(tmp_path / "input.png"), "Describe this")

    assert paths == ["/props"]
