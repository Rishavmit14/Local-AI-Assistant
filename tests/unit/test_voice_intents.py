import pytest

from local_ai_assistant.interface.voice_intents import (
    FridayVoiceIntentRouter,
    FridayVoiceIntentType,
    ScreenQuestionMode,
)


@pytest.mark.parametrize(
    "prompt",
    [
        "What do you see on my screen?",
        "What's on my screen?",
        "What is this?",
        "Why is this failing?",
        "What does that mean?",
        "Read this",
        "What do you think of this?",
        "What error do you see?",
        "Read what's on screen",
        "Can you describe this chart?",
    ],
)
def test_visual_screen_context_intents_include_natural_deictic_language(prompt):
    intent = FridayVoiceIntentRouter().classify(prompt)

    assert intent.kind is FridayVoiceIntentType.SCREEN_CONTEXT_QUESTION
    assert intent.screen_mode is ScreenQuestionMode.VISUAL


@pytest.mark.parametrize(
    "prompt",
    [
        "What application is open?",
        "Which app is active?",
        "What window am I in?",
        "What button is focused?",
        "What's currently focused?",
    ],
)
def test_high_confidence_window_and_focus_questions_use_semantic_fast_path(prompt):
    intent = FridayVoiceIntentRouter().classify(prompt)

    assert intent.kind is FridayVoiceIntentType.SCREEN_CONTEXT_QUESTION
    assert intent.screen_mode is ScreenQuestionMode.SEMANTIC


def test_non_screen_conversation_remains_generic():
    intent = FridayVoiceIntentRouter().classify("Can you explain how gradient descent works?")

    assert intent.kind is FridayVoiceIntentType.CONVERSATIONAL_KNOWLEDGE


def test_multi_step_open_and_search_routes_to_general_computer_planning():
    intent = FridayVoiceIntentRouter().classify(
        "Hey Friday, open YouTube, search for machine learning."
    )

    assert intent.kind is FridayVoiceIntentType.COMPUTER_ACTION
    assert intent.open_command is None
    assert intent.computer_goal == "Hey Friday, open YouTube, search for machine learning."


def test_historical_probe_transcript_routes_raw_text_without_asr_replacement():
    transcript = "Open the second folder in this files video."

    intent = FridayVoiceIntentRouter().classify(transcript)

    assert intent.kind is FridayVoiceIntentType.COMPUTER_ACTION
    assert intent.computer_goal == transcript
