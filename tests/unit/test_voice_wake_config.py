import pytest

from local_ai_assistant.common.config import (
    AppConfig,
)
from local_ai_assistant.common.errors import (
    ConfigurationError,
)


def test_wake_is_disabled_by_default() -> None:
    config = AppConfig.from_env({})

    assert not config.wake.enabled
    assert config.wake.phrase == "hey friday"


def test_wake_can_be_enabled_explicitly() -> None:
    config = AppConfig.from_env(
        {
            "LOCAL_AI_WAKE_ENABLED":
                "true",
            "LOCAL_AI_WAKE_PHRASE":
                "Hey Friday",
        }
    )

    assert config.wake.enabled
    assert config.wake.phrase == "hey friday"


def test_wake_phrase_is_normalized() -> None:
    config = AppConfig.from_env(
        {
            "LOCAL_AI_WAKE_PHRASE":
                "  HEY FRIDAY  ",
        }
    )

    assert config.wake.phrase == "hey friday"


def test_empty_wake_phrase_is_rejected() -> None:
    with pytest.raises(
        ConfigurationError,
        match=(
            "LOCAL_AI_WAKE_PHRASE "
            "must not be empty"
        ),
    ):
        AppConfig.from_env(
            {
                "LOCAL_AI_WAKE_PHRASE":
                    "   ",
            }
        )


def test_invalid_wake_boolean_is_rejected() -> None:
    with pytest.raises(
        ConfigurationError,
    ):
        AppConfig.from_env(
            {
                "LOCAL_AI_WAKE_ENABLED":
                    "sometimes",
            }
        )
