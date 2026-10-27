import pytest

from local_ai_assistant.interface.voice_intents import (
    FridayVoiceIntentRouter,
    FridayVoiceIntentType,
    ScreenQuestionMode,
    VoiceLearningAction,
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


@pytest.mark.parametrize(
    ("prompt", "pending", "action"),
    [
        ("Friday, continue my course", False, VoiceLearningAction.CONTINUE),
        ("Friday, explain the lesson again", False, VoiceLearningAction.REPEAT),
        ("Friday, repeat that", False, VoiceLearningAction.REPEAT),
        ("Can I repeat that?", False, VoiceLearningAction.REPEAT),
        ("Repeat that.", False, VoiceLearningAction.REPEAT),
        ("Explain logistic regression", False, VoiceLearningAction.EXPLAIN),
        ("My answer is a linear boundary", False, VoiceLearningAction.ANSWER),
        ("My answer is a linear boundary", True, VoiceLearningAction.CORRECT),
        ("yes, submit it", True, VoiceLearningAction.CONFIRM),
        ("cancel my answer", True, VoiceLearningAction.CANCEL),
        ("show my learning progress", False, VoiceLearningAction.PROGRESS),
        ("check my answer", False, VoiceLearningAction.CHECK),
    ],
)
def test_voice_learning_commands_are_typed_and_confirmation_requires_affirmation(prompt, pending, action):
    intent = FridayVoiceIntentRouter().classify(prompt, pending_voice_answer=pending)

    assert intent.kind is FridayVoiceIntentType.LEARNING_CAREER_PROJECT
    assert intent.learning_action is action


@pytest.mark.parametrize(
    "prompt",
    [
        "Can I have a beat that?",
        "Can I have a beat?",
        "Can I have a beat that is strong?",
    ],
)
def test_ambiguous_asr_homophone_does_not_route_to_lesson_repeat(prompt):
    router = FridayVoiceIntentRouter()

    assert router.classify(prompt).learning_action is None


@pytest.mark.parametrize("prompt", ["", " ", "maybe", "not sure", "no"])
def test_ambiguous_or_negative_confirmation_does_not_submit_learning_answer(prompt):
    intent = FridayVoiceIntentRouter().classify(prompt, pending_voice_answer=True)

    assert intent.learning_action is (VoiceLearningAction.CANCEL if prompt == "no" else None)
