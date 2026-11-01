# PAASR — Telugu Voice Translator

PAASR is a Gradio app that transcribes Telugu audio, translates the
reviewed Telugu transcript into English, and generates English speech.

## Important privacy and network note

Voice recognition uses Google Speech Recognition with language `te-IN`.
Translation uses Google Translate with source `te` and target `en`. The
recording is sent to Google for speech recognition, and the transcript is sent
to Google for translation. Internet access is required. This app does not ask
for or store Google API keys. English text-to-speech runs locally through
Windows SAPI5 or Linux eSpeak.

The app uses Google's public web-service endpoints through client libraries;
these are not a production SLA and may be throttled or changed by Google. Do
not send sensitive audio or text unless you are comfortable with Google's
service terms and privacy practices.

## Windows setup and run

Requirements: Windows 10/11 or a Linux web host, Python 3.11 or newer, and
internet access.

1. Open the project folder.
2. Double-click `setup.bat` once to create `.venv` and install the dependencies.
3. Double-click `run.bat`, or run in PowerShell:

   ```powershell
   .\.venv\Scripts\python.exe app.py
   ```

4. Open <http://127.0.0.1:10000>.
5. On the single translator page, record or upload Telugu audio, click **Transcribe Telugu**,
   review or edit the Telugu transcript, then click
   **Translate to English**. Gradio shows the microphone waveform while recording.

No Whisper or NLLB model download is needed. The voice input accepts WAV, MP3,
OGG, WebM, and M4A audio up to two minutes. PyAV decodes uploads to mono,
16 kHz audio before recognition. The separate text translation flow supports
English, Hindi, and Telugu in either direction when source and target differ.

## Error behavior

- Empty, unreadable, unsupported, or too-short audio is rejected before upload.
- If Google cannot understand the speech, the app asks for a clearer recording.
- Network or Google service errors appear in the status panel with an
  actionable message; details are logged in `logs/app.log`.
- The transcript remains editable so recognition mistakes can be corrected
  before translation.
- English TTS errors are non-fatal: the translated text remains available.

## Deploy to Render

The Git repository contains the app and `requirements.txt` inside the `paasr/`
subdirectory. The repository-root `render.yaml` configures this path for
Render Blueprint deployments. For a manually created Web Service, use:

| Setting | Value |
|---|---|
| Root Directory | `paasr` |
| Runtime | Python 3 |
| Branch | `main` |
| Build Command | `apt-get update && apt-get install -y espeak libespeak1 && pip install -r requirements.txt` |
| Start Command | `python app.py` |
| Instance | Free is suitable for a demo; choose more RAM if it runs out of memory |

Render should provide `PORT` automatically. Set these environment variables:

```text
GRADIO_SERVER_NAME=0.0.0.0
GRADIO_IN_BROWSER=false
PYTHON_VERSION=3.12.10
```

The application binds to `0.0.0.0` and Render's `PORT` when available; the
local default port is `10000`. The `espeak`
packages enable pyttsx3 audio synthesis on a Linux host. The free instance
may spin down while idle, has limited memory, and uses ephemeral storage:
SQLite survey data and generated temporary audio should not be treated as
persistent. Push the latest code to the selected Git branch before creating
the Render service.

## Tests

Run the unit tests (Google requests are mocked):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run basic local checks:

```powershell
.\.venv\Scripts\python.exe check_setup.py
.\.venv\Scripts\python.exe smoke_test.py
```

Optional tests that contact Google Translate:

```powershell
$env:PAASR_RUN_GOOGLE_INTEGRATION = "1"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_google_integration.py -v
```

To include an actual audio recording, set its path before running:

```powershell
$env:PAASR_TEST_AUDIO = "C:\path\to\telugu-recording.wav"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_google_integration.py -v
```

The optional audio test sends that file to Google. Integration results depend
on internet availability and Google's service response. Mocked unit tests do
not establish recognition or translation accuracy.

## Project layout

```text
app.py                 Gradio UI and callbacks
config.py              Language codes, server, and audio limits
requirements.txt       Windows application dependencies
setup.bat / run.bat    Setup and launch scripts
modules/asr.py         Google te-IN speech recognition and PyAV decoding
modules/translator.py  Google Translate requests and bounded text splitting
modules/tts.py         Local Windows SAPI5 speech synthesis
modules/survey_db.py   Local SQLite survey storage
tests/                 Unit and opt-in Google integration tests
```
