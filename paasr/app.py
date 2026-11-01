"""PAASR single-page Gradio Telugu-to-English voice translator."""

from __future__ import annotations

import os
import socket
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env", override=False)

import config
from modules.utils import logger

import gradio as gr

_CSS_PATH = config.ASSETS_DIR / "style.css"
_CUSTOM_CSS = _CSS_PATH.read_text(encoding="utf-8") if _CSS_PATH.exists() else ""


def _error_box(message: str) -> str:
    safe = (
        message.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )
    return (
        '<div class="status-box status-error">'
        f"<strong>Error</strong><br>{safe}</div>"
    )


def _status_box(lines: list[str]) -> str:
    items = "".join(
        "<li>"
        f"{line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')}"
        "</li>"
        for line in lines
    )
    return (
        '<div class="status-box status-ok">'
        f"<strong>Translation status</strong><ul>{items}</ul></div>"
    )


def run_pipeline(audio_path: str | None, progress=gr.Progress()):
    """Transcribe recorded/uploaded Telugu audio using Google Speech Recognition."""
    from modules.asr import transcribe_audio
    from modules.utils import AudioValidationError

    try:
        transcript, asr_info, detected_language = transcribe_audio(
            audio_path, progress=progress
        )
        return (
            transcript,
            "",
            None,
            _status_box([
                f"[OK] {asr_info}",
                "[NEXT] Review the Telugu transcript, then translate it to English.",
            ]),
            detected_language,
        )
    except AudioValidationError as exc:
        return "", "", None, _error_box(str(exc)), None
    except (RuntimeError, ValueError) as exc:
        return "", "", None, _error_box(str(exc)), None
    except Exception:
        logger.exception("Unexpected Google speech recognition error.")
        return (
            "",
            "",
            None,
            _error_box(
                "Google speech recognition failed unexpectedly. "
                "Check logs/app.log for details."
            ),
            None,
        )


def run_voice_translation(
    transcript: str,
    detected_language: str | None,
    progress=gr.Progress(),
) -> tuple[str, str | None, str]:
    """Translate the reviewed Telugu transcript and synthesize English audio."""
    from modules.translator import translate_text
    from modules.tts import synthesise_speech

    if not transcript or not transcript.strip():
        return (
            "",
            None,
            _error_box("Transcribe or enter a Telugu transcript before translating."),
        )

    source_language = config.SPEECH_TO_TRANSLATION_LANGUAGE.get(detected_language)
    if source_language is None:
        supported = ", ".join(config.SPEECH_TO_TRANSLATION_LANGUAGE.values())
        return (
            "",
            None,
            _error_box(
                f"Detected speech language {detected_language!r} is not supported. "
                f"Supported speech languages: {supported}."
            ),
        )

    try:
        progress(0.1, desc="Translating the reviewed Telugu transcript ...")
        english_text, trans_info = translate_text(
            transcript, source_language, "English", progress=progress
        )
    except (ValueError, RuntimeError) as exc:
        return "", None, _error_box(str(exc))
    except Exception:
        logger.exception("Unexpected Google Translate error.")
        return (
            "",
            None,
            _error_box(
                "Translation failed unexpectedly. Check logs/app.log for details."
            ),
        )

    status_parts = [f"[OK] {trans_info}"]
    audio_out = None
    try:
        progress(0.9, desc="Generating English speech ...")
        audio_out, tts_info = synthesise_speech(english_text)
        status_parts.append(f"[OK] {tts_info}")
    except (ValueError, RuntimeError) as exc:
        logger.exception("English speech synthesis failed after translation.")
        status_parts.append(f"[WARN] English audio could not be generated: {exc}")

    progress(1.0, desc="Translation complete.")
    return english_text, audio_out, _status_box(status_parts)


def run_text_translation(
    text: str,
    source_language: str,
    target_language: str,
    progress=gr.Progress(),
) -> tuple[str, str]:
    """Translate text using the same Google Translate service."""
    from modules.translator import translate_text

    try:
        translated_text, info = translate_text(
            text, source_language, target_language, progress=progress
        )
        return translated_text, _status_box([f"[OK] {info}"])
    except (ValueError, RuntimeError) as exc:
        return "", _error_box(str(exc))
    except Exception:
        logger.exception("Unexpected text translation error.")
        return (
            "",
            _error_box(
                "Text translation failed unexpectedly. Check logs/app.log for details."
            ),
        )


def clear_text_outputs():
    return "", ""


def clear_outputs():
    return None, "", "", None, "", None


def _find_free_port(preferred: int) -> int:
    """Return the preferred local port or another available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        try:
            server.bind(("127.0.0.1", preferred))
            return preferred
        except OSError:
            server.bind(("127.0.0.1", 0))
            return server.getsockname()[1]


def build_app() -> gr.Blocks:
    """Build the single-page, responsive voice translator."""
    with gr.Blocks(
        title=config.APP_TITLE,
        css=_CUSTOM_CSS,
        theme=gr.themes.Soft(
            primary_hue="violet",
            secondary_hue="purple",
            neutral_hue="slate",
        ),
        elem_id="paasr-app",
    ) as demo:
        gr.HTML(
            """
            <header class="paasr-header">
              <div class="brand-mark" aria-hidden="true">P</div>
              <h1>PAASR</h1>
              <p>Telugu to English Voice Translator</p>
            </header>
            """
        )

        with gr.Column(elem_id="translator-card"):
            gr.HTML(
                """
                <div class="language-direction" aria-label="Telugu to English">
                  <span class="language-pill"><span class="language-dot"></span>తెలుగు</span>
                  <span class="direction-arrow" aria-hidden="true">→</span>
                  <span class="language-pill"><span class="language-dot english-dot"></span>English</span>
                </div>
                <p class="card-instruction">Speak naturally. We’ll transcribe your Telugu and translate it into English.</p>
                """
            )

            audio_input = gr.Audio(
                sources=["microphone", "upload"],
                type="filepath",
                show_label=False,
                elem_id="voice-recorder",
            )
            gr.HTML(
                '<p class="record-hint">Tap to speak '
                '<span>or upload an audio file</span></p>'
            )

            with gr.Row(elem_id="voice-actions"):
                btn_transcribe = gr.Button(
                    "Transcribe Telugu",
                    variant="primary",
                    elem_id="transcribe-button",
                )
                btn_voice_translate = gr.Button(
                    "Translate to English",
                    variant="primary",
                    elem_id="translate-button",
                )
                btn_clear = gr.Button(
                    "Clear",
                    variant="secondary",
                    elem_id="clear-button",
                )

            status_box = gr.HTML(
                value=(
                    '<div class="status-box status-idle">'
                    "Your translation will appear here.</div>"
                ),
                elem_id="status-box",
            )

            with gr.Row(elem_id="translation-results"):
                with gr.Column(elem_id="transcript-card"):
                    gr.HTML(
                        '<div class="result-heading">'
                        '<span class="result-icon telugu-icon">అ</span>'
                        "<span><strong>Telugu transcript</strong>"
                        "<small>Review or edit before translating</small></span></div>"
                    )
                    telugu_output = gr.Textbox(
                        label="",
                        lines=4,
                        max_lines=8,
                        placeholder="Your Telugu transcript will appear here…",
                        show_label=False,
                        interactive=True,
                        elem_id="telugu-output",
                    )

                with gr.Column(elem_id="english-card"):
                    gr.HTML(
                        '<div class="result-heading">'
                        '<span class="result-icon english-icon">A</span>'
                        "<span><strong>English translation</strong>"
                        "<small>Your translated text</small></span></div>"
                    )
                    english_output = gr.Textbox(
                        label="",
                        lines=4,
                        max_lines=8,
                        placeholder="Your English translation will appear here…",
                        show_label=False,
                        interactive=False,
                        show_copy_button=True,
                        elem_id="english-output",
                    )
                    audio_output = gr.Audio(
                        label="English Audio Output",
                        type="filepath",
                        interactive=False,
                        show_download_button=True,
                        elem_id="english-audio",
                    )

            gr.HTML(
                '<p class="privacy-note">Audio and transcript are sent to Google '
                "for speech recognition and translation.</p>"
            )

        with gr.Accordion(
            "Translate text instead", open=False, elem_id="text-translation"
        ):
            with gr.Row():
                text_source_language = gr.Dropdown(
                    choices=list(config.TRANSLATION_LANGUAGES),
                    value="Telugu",
                    label="From",
                )
                text_target_language = gr.Dropdown(
                    choices=list(config.TRANSLATION_LANGUAGES),
                    value="English",
                    label="To",
                )
            text_input = gr.Textbox(
                label="Text to translate",
                lines=3,
                placeholder="Type or paste text here…",
            )
            with gr.Row():
                btn_text_translate = gr.Button("Translate text", variant="primary")
                btn_text_clear = gr.Button("Clear text", variant="secondary")
            text_output = gr.Textbox(
                label="Translated text",
                lines=3,
                interactive=False,
                show_copy_button=True,
            )
            text_status_box = gr.HTML()

        voice_translation_source = gr.State(value=None)

        btn_transcribe.click(
            fn=run_pipeline,
            inputs=[audio_input],
            outputs=[
                telugu_output,
                english_output,
                audio_output,
                status_box,
                voice_translation_source,
            ],
            show_progress="full",
        )
        btn_voice_translate.click(
            fn=run_voice_translation,
            inputs=[telugu_output, voice_translation_source],
            outputs=[english_output, audio_output, status_box],
            show_progress="full",
        )
        btn_clear.click(
            fn=clear_outputs,
            inputs=[],
            outputs=[
                audio_input,
                telugu_output,
                english_output,
                audio_output,
                status_box,
                voice_translation_source,
            ],
            queue=False,
        )
        btn_text_translate.click(
            fn=run_text_translation,
            inputs=[text_input, text_source_language, text_target_language],
            outputs=[text_output, text_status_box],
            show_progress="full",
        )
        btn_text_clear.click(
            fn=clear_text_outputs,
            inputs=[],
            outputs=[text_input, text_output],
            queue=False,
        )

    return demo


if __name__ == "__main__":
    # Render routes traffic to PORT; never silently switch to another port there.
    port = (
        config.GRADIO_SERVER_PORT
        if os.getenv("PORT") is not None
        else _find_free_port(config.GRADIO_SERVER_PORT)
    )
    if port != config.GRADIO_SERVER_PORT:
        logger.warning(
            "Port %d is in use; using %d instead.",
            config.GRADIO_SERVER_PORT,
            port,
        )

    logger.info(
        "Starting PAASR v%s on http://%s:%d",
        config.APP_VERSION,
        config.GRADIO_SERVER_NAME,
        port,
    )
    print(f"[PAASR] Starting on http://{config.GRADIO_SERVER_NAME}:{port}")
    print("[PAASR] Google speech recognition and translation require internet access.")

    app = build_app()
    app.launch(
        server_name=config.GRADIO_SERVER_NAME,
        server_port=port,
        share=config.GRADIO_SHARE,
        show_error=True,
        inbrowser=config.GRADIO_IN_BROWSER,
    )
