from __future__ import annotations

import os
import struct
import subprocess
import sys
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
import config
from modules import asr, translator
from modules.utils import AudioValidationError


class FakeResponse:
    def __init__(self, translated: str = "I have a stomach ache.") -> None:
        self.translated = translated

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return [[[self.translated, None, None]], None, "te"]


class GoogleWorkflowTests(unittest.TestCase):
    def test_default_server_binding_matches_render(self) -> None:
        project_dir = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment.pop("PORT", None)
        environment.pop("GRADIO_SERVER_NAME", None)
        environment.pop("GRADIO_SERVER_PORT", None)
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import config; print(config.GRADIO_SERVER_NAME, "
                "config.GRADIO_SERVER_PORT)",
            ],
            cwd=project_dir,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("0.0.0.0 10000", result.stdout)

    def test_render_environment_controls_host_and_port(self) -> None:
        project_dir = Path(__file__).resolve().parents[1]
        environment = os.environ.copy()
        environment.update({
            "PORT": "19321",
            "GRADIO_SERVER_PORT": "7860",
            "GRADIO_SERVER_NAME": "0.0.0.0",
            "GRADIO_IN_BROWSER": "false",
        })
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import config; print(config.GRADIO_SERVER_NAME, "
                "config.GRADIO_SERVER_PORT, config.GRADIO_IN_BROWSER)",
            ],
            cwd=project_dir,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertIn("0.0.0.0 19321 False", result.stdout)

    def test_render_blueprint_points_to_nested_application(self) -> None:
        repository_root = Path(__file__).resolve().parents[2]
        render_config = (repository_root / "render.yaml").read_text(
            encoding="utf-8"
        )
        python_version = (repository_root / ".python-version").read_text(
            encoding="utf-8"
        ).strip()
        requirements = (
            Path(__file__).resolve().parents[1] / "requirements.txt"
        ).read_text(encoding="utf-8")

        self.assertIn("rootDir: paasr", render_config)
        self.assertIn("pip install -r requirements.txt", render_config)
        self.assertIn("startCommand: python app.py", render_config)
        self.assertIn("value: 3.11.11", render_config)
        self.assertEqual(python_version, "3.11.11")
        for package in (
            "gradio==4.44.1",
            "fastapi==0.115.6",
            "starlette==0.41.3",
            "pydantic==2.10.6",
            "SpeechRecognition==3.14.3",
            "av==12.3.0",
            "numpy==1.26.4",
            "pyttsx3==2.91",
        ):
            self.assertIn(package, requirements)
        for package in (
            "pydantic-core==",
            "gradio-client==",
            "click==",
            "tqdm==",
            "filelock==",
            "packaging==",
        ):
            self.assertNotIn(package, requirements)

    def test_ui_is_a_single_translator_page_with_existing_voice_outputs(self) -> None:
        ui = app.build_app()
        components = ui.config["components"]
        component_types = [component.get("type") for component in components]
        element_ids = {
            component.get("props", {}).get("elem_id")
            for component in components
        }

        self.assertNotIn("tabs", component_types)
        self.assertNotIn("tabitem", component_types)
        self.assertTrue({
            "translator-card",
            "voice-recorder",
            "telugu-output",
            "english-output",
            "english-audio",
        }.issubset(element_ids))

    def _make_wav(self, directory: str) -> Path:
        path = Path(directory) / "telugu.wav"
        with wave.open(str(path), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(2)
            audio_file.setframerate(16_000)
            audio_file.writeframes(b"\x10\x00" * 16_000)
        return path

    def test_audio_decoder_resamples_to_google_pcm_format(self) -> None:
        class FakeAudioData:
            def __init__(self, frame_data, sample_rate, sample_width):
                self.frame_data = frame_data
                self.sample_rate = sample_rate
                self.sample_width = sample_width

        fake_sr = SimpleNamespace(AudioData=FakeAudioData)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stereo.wav"
            with wave.open(str(path), "wb") as audio_file:
                audio_file.setnchannels(2)
                audio_file.setsampwidth(2)
                audio_file.setframerate(44_100)
                audio_file.writeframes(
                    struct.pack("<hh", 400, -400) * 22_050
                )
            with patch.dict(sys.modules, {"speech_recognition": fake_sr}):
                audio, _sr = asr._decode_audio(path)

        self.assertEqual(audio.sample_rate, 16_000)
        self.assertEqual(audio.sample_width, 2)
        self.assertGreater(len(audio.frame_data), 0)

    def test_telugu_asr_uses_google_te_in_and_preserves_telugu_script(self) -> None:
        recognized = "నాకు కడుపు నొప్పిగా ఉంది"
        calls = []

        class FakeRecognizer:
            operation_timeout = None

            def recognize_google(self, audio, **kwargs):
                calls.append((audio, kwargs))
                return recognized

        fake_sr = SimpleNamespace(
            Recognizer=lambda: FakeRecognizer(),
            UnknownValueError=type("UnknownValueError", (Exception,), {}),
            RequestError=type("RequestError", (Exception,), {}),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self._make_wav(directory)
            with patch.object(asr, "_decode_audio", return_value=(object(), fake_sr)):
                transcript, info, language = asr.transcribe_audio(str(path))

        self.assertEqual(transcript, recognized)
        self.assertEqual(language, "te")
        self.assertIn("Google Speech Recognition", info)
        self.assertEqual(calls[0][1], {"language": "te-IN"})

    def test_google_speech_network_failure_is_actionable(self) -> None:
        request_error = type("RequestError", (Exception,), {})

        class FakeRecognizer:
            operation_timeout = None

            def recognize_google(self, _audio, **_kwargs):
                raise request_error("service unavailable")

        fake_sr = SimpleNamespace(
            Recognizer=lambda: FakeRecognizer(),
            UnknownValueError=type("UnknownValueError", (Exception,), {}),
            RequestError=request_error,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self._make_wav(directory)
            with patch.object(asr, "_decode_audio", return_value=(object(), fake_sr)):
                with self.assertRaisesRegex(RuntimeError, "internet connection"):
                    asr.transcribe_audio(str(path))

    def test_empty_audio_is_rejected_before_google_request(self) -> None:
        with self.assertRaisesRegex(AudioValidationError, "No audio received"):
            asr.transcribe_audio(None)

    def test_empty_audio_file_is_rejected_before_google_request(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.wav"
            path.write_bytes(b"")
            with self.assertRaisesRegex(AudioValidationError, "empty"):
                asr.transcribe_audio(str(path))

    def test_unrecognized_speech_has_a_clear_message(self) -> None:
        unknown_value = type("UnknownValueError", (Exception,), {})

        class FakeRecognizer:
            operation_timeout = None

            def recognize_google(self, _audio, **_kwargs):
                raise unknown_value()

        fake_sr = SimpleNamespace(
            Recognizer=lambda: FakeRecognizer(),
            UnknownValueError=unknown_value,
            RequestError=type("RequestError", (Exception,), {}),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = self._make_wav(directory)
            with patch.object(asr, "_decode_audio", return_value=(object(), fake_sr)):
                with self.assertRaisesRegex(RuntimeError, "could not understand"):
                    asr.transcribe_audio(str(path))

    def test_translate_uses_google_te_to_en_and_returns_service_result(self) -> None:
        with patch(
            "modules.translator.requests.get",
            return_value=FakeResponse(),
        ) as request:
            translated, info = translator.translate_text(
                "నాకు కడుపు నొప్పిగా ఉంది", "Telugu", "English"
            )

        self.assertEqual(translated, "I have a stomach ache.")
        self.assertIn("Google Translate", info)
        self.assertEqual(
            request.call_args.kwargs["params"],
            {
                "client": "gtx",
                "sl": "te",
                "tl": "en",
                "dt": "t",
                "q": "నాకు కడుపు నొప్పిగా ఉంది",
            },
        )
        self.assertEqual(
            request.call_args.kwargs["timeout"],
            config.GOOGLE_REQUEST_TIMEOUT_SECONDS,
        )

    def test_empty_and_unsupported_translation_inputs_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "empty"):
            translator.translate_text("   ", "Telugu", "English")
        with self.assertRaisesRegex(ValueError, "Unsupported source language"):
            translator.translate_text("hello", "Klingon", "English")
        with self.assertRaisesRegex(ValueError, "Unsupported target language"):
            translator.translate_text("hello", "English", "Klingon")
        with self.assertRaisesRegex(ValueError, "must be different"):
            translator.translate_text("hello", "English", "English")

    def test_long_text_is_sent_in_complete_bounded_segments(self) -> None:
        text = "one two three four five six seven eight nine ten"
        with patch.object(config, "GOOGLE_TRANSLATE_MAX_CHARS", 12), patch(
            "modules.translator.requests.get",
            side_effect=[FakeResponse("translated") for _ in range(10)],
        ) as request:
            translator.translate_text(text, "English", "Hindi")

        submitted = [
            call.kwargs["params"]["q"] for call in request.call_args_list
        ]
        self.assertTrue(all(len(chunk) <= 12 for chunk in submitted))
        self.assertEqual(" ".join(submitted).split(), text.split())
        self.assertTrue(all(
            call.kwargs["params"]["sl"] == "en"
            and call.kwargs["params"]["tl"] == "hi"
            for call in request.call_args_list
        ))

    def test_google_translate_network_failure_is_actionable(self) -> None:
        import requests

        with patch(
            "modules.translator.requests.get",
            side_effect=requests.exceptions.ConnectionError("offline"),
        ):
            with self.assertRaisesRegex(RuntimeError, "internet connection"):
                translator.translate_text("hello", "English", "Hindi")

    def test_voice_callbacks_transcribe_review_translate_and_return_output(self) -> None:
        transcript = "నాకు కడుపు నొప్పిగా ఉంది"
        corrected_transcript = "నాకు కడుపు నొప్పిగా ఉంది"
        noop_progress = lambda *_args, **_kwargs: None
        with patch(
            "modules.asr.transcribe_audio",
            return_value=(transcript, "Google Speech Recognition te-IN", "te"),
        ) as transcribe:
            displayed_transcript, translation, audio, status, language = (
                app.run_pipeline("speech.wav", progress=noop_progress)
            )

        transcribe.assert_called_once_with("speech.wav", progress=noop_progress)
        self.assertEqual(displayed_transcript, transcript)
        self.assertEqual(translation, "")
        self.assertIsNone(audio)
        self.assertEqual(language, "te")
        self.assertIn("Review the Telugu transcript", status)

        with patch(
            "modules.translator.translate_text",
            return_value=("I have a stomach ache.", "Google Translate"),
        ) as translate, patch(
            "modules.tts.synthesise_speech",
            return_value=("english.wav", "Local TTS"),
        ):
            english, audio_path, status = app.run_voice_translation(
                corrected_transcript, language, progress=noop_progress
            )

        translate.assert_called_once_with(
            corrected_transcript, "Telugu", "English", progress=noop_progress
        )
        self.assertEqual(english, "I have a stomach ache.")
        self.assertEqual(audio_path, "english.wav")
        self.assertIn("Google Translate", status)

    def test_text_translation_callback_displays_google_result(self) -> None:
        with patch(
            "modules.translator.translate_text",
            return_value=("నమస్కారం", "Google Translate"),
        ) as translate:
            result, status = app.run_text_translation(
                "Hello", "English", "Telugu",
                progress=lambda *_args, **_kwargs: None,
            )
        self.assertEqual(result, "నమస్కారం")
        self.assertIn("Google Translate", status)
        self.assertEqual(translate.call_args.args, ("Hello", "English", "Telugu"))

    def test_translation_callback_shows_network_error(self) -> None:
        with patch(
            "modules.translator.translate_text",
            side_effect=RuntimeError("Could not reach Google Translate."),
        ):
            output, status = app.run_text_translation(
                "Hello", "English", "Telugu",
                progress=lambda *_args, **_kwargs: None,
            )
        self.assertEqual(output, "")
        self.assertIn("Could not reach Google Translate", status)


if __name__ == "__main__":
    unittest.main()
