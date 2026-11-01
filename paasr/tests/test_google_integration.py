"""Opt-in integration tests for Google services; no credentials are used."""

from __future__ import annotations

import os
import unittest

from modules.asr import transcribe_audio
from modules.translator import translate_text


GOOGLE_TESTS_ENABLED = os.environ.get("PAASR_RUN_GOOGLE_INTEGRATION") == "1"
TEST_AUDIO = os.environ.get("PAASR_TEST_AUDIO")


@unittest.skipUnless(
    GOOGLE_TESTS_ENABLED,
    "Set PAASR_RUN_GOOGLE_INTEGRATION=1 to contact Google services.",
)
class GoogleServiceIntegrationTests(unittest.TestCase):
    def test_telugu_phrase_translation(self) -> None:
        source = "నాకు కడుపు నొప్పిగా ఉంది"
        translated, info = translate_text(source, "Telugu", "English")
        self.assertTrue(translated.strip())
        print(
            "\nGoogle Translate Telugu -> English\n"
            f"Input: {ascii(source)}\n"
            f"Actual output: {ascii(translated)}\n"
            f"Details: {info}"
        )

    @unittest.skipUnless(
        TEST_AUDIO,
        "Set PAASR_TEST_AUDIO to an audio file to send it to Google Speech Recognition.",
    )
    def test_real_telugu_audio_recognition(self) -> None:
        transcript, info, language = transcribe_audio(TEST_AUDIO)
        self.assertTrue(transcript.strip())
        self.assertEqual(language, "te")
        print(
            "\nGoogle Speech Recognition te-IN\n"
            f"Audio: {TEST_AUDIO}\n"
            f"Actual transcript: {ascii(transcript)}\n"
            f"Details: {info}"
        )


if __name__ == "__main__":
    unittest.main()
