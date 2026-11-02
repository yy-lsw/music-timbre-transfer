import io
import os
import time
import unittest

import numpy as np
import soundfile as sf
from unittest import mock

from backend.app import app
from backend.config import OUTPUT_FOLDER, UPLOAD_FOLDER
from backend.effects import AudioEffects
from backend.inference import TimbreInference
from backend.neural import NeuralVoiceConverter
from backend.preprocessor import AudioPreprocessor
from backend.realtime import REALTIME_PRESETS, fast_pitch_shift
from backend.reconstructor import AudioReconstructor


def _sine_bytes(duration=1.0, frequency=440.0, sample_rate=44100):
    samples = np.sin(
        2 * np.pi * frequency * np.arange(int(duration * sample_rate)) / sample_rate
    ).astype(np.float32)
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate, format="WAV", subtype="PCM_16")
    buffer.seek(0)
    return buffer


class BackendTests(unittest.TestCase):
    def test_health_and_styles(self):
        client = app.test_client()
        health = client.get("/api/health")
        self.assertEqual(health.status_code, 200)
        styles = client.get("/api/styles").get_json()["styles"]
        self.assertGreaterEqual(len(styles), 5)
        self.assertIn("m2f", [style["key"] for style in styles])

    def test_effects_keep_shape_and_are_finite(self):
        audio = np.random.default_rng(0).normal(0, 0.1, (1, 4410)).astype(np.float32)
        output = AudioEffects().process(audio, "hifi")
        self.assertEqual(output.shape, audio.shape)
        self.assertTrue(np.isfinite(output).all())

    def test_reverb_styles_are_finite(self):
        audio = np.random.default_rng(1).normal(0, 0.1, (1, 4410)).astype(np.float32)
        for style in ("classical", "jazz", "surround"):
            output = AudioEffects().process(audio, style)
            self.assertTrue(np.isfinite(output).all())
            self.assertGreaterEqual(output.shape[1], audio.shape[1])

    def test_voice_preset_raises_pitch(self):
        sample_rate = 44100
        audio = np.sin(
            2 * np.pi * 220 * np.arange(sample_rate) / sample_rate
        ).astype(np.float32)[np.newaxis, :]
        output = AudioEffects().process(audio, "m2f")
        peak_bin = int(np.argmax(np.abs(np.fft.rfft(output[0]))))
        peak_frequency = peak_bin * sample_rate / len(output[0])
        self.assertGreater(peak_frequency, 270)

    def test_full_conversion_flow(self):
        client = app.test_client()
        upload = client.post(
            "/api/upload",
            data={"file": (_sine_bytes(), "voice.wav")},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload.status_code, 200)
        file_id = upload.get_json()["file_id"]

        convert = client.post(
            "/api/convert",
            json={"file_id": file_id, "style": "hifi", "params": {}},
        )
        self.assertEqual(convert.status_code, 200)
        task_id = convert.get_json()["task_id"]

        status = {}
        for _ in range(60):
            status = client.get(f"/api/status/{task_id}").get_json()
            if status["status"] in ("completed", "error", "cancelled"):
                break
            time.sleep(0.2)

        self.assertEqual(status["status"], "completed")
        output_file = status["output_file"]
        download = client.get(f"/api/download/{output_file}")
        self.assertEqual(download.status_code, 200)
        download.close()

        history = client.get("/api/history").get_json()["history"]
        self.assertTrue(any(row["original_filename"] == "voice.wav" for row in history))

        for path in (
            os.path.join(UPLOAD_FOLDER, file_id),
            os.path.join(OUTPUT_FOLDER, output_file),
        ):
            if os.path.exists(path):
                os.remove(path)

    def test_neural_converter_degrades_gracefully(self):
        converter = NeuralVoiceConverter(
            seedvc_home=r"C:\__missing__\Seed-VC",
            seedvc_python=r"C:\__missing__\python.exe",
        )
        self.assertFalse(converter.available)
        with self.assertRaises(RuntimeError):
            converter.convert("missing-source.wav", "missing-ref.wav", "out")

    def test_neural_status_reports_unavailable(self):
        unavailable = NeuralVoiceConverter(
            seedvc_home=r"C:\__missing__\Seed-VC",
            seedvc_python=r"C:\__missing__\python.exe",
        )
        client = app.test_client()
        with mock.patch("backend.app.neural_engine", unavailable):
            response = client.get("/api/neural/status")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertFalse(payload["available"])
        self.assertIn("hint", payload)

    def test_neural_convert_rejects_when_unavailable(self):
        unavailable = NeuralVoiceConverter(
            seedvc_home=r"C:\__missing__\Seed-VC",
            seedvc_python=r"C:\__missing__\python.exe",
        )
        client = app.test_client()
        upload = client.post(
            "/api/upload",
            data={"file": (_sine_bytes(), "voice.wav")},
            content_type="multipart/form-data",
        )
        self.assertEqual(upload.status_code, 200)
        file_id = upload.get_json()["file_id"]
        with mock.patch("backend.app.neural_engine", unavailable):
            response = client.post(
                "/api/neural/convert",
                json={"file_id": file_id, "reference_key": "female"},
            )
        self.assertEqual(response.status_code, 503)
        path = os.path.join(UPLOAD_FOLDER, file_id)
        if os.path.exists(path):
            os.remove(path)

    def test_fast_pitch_shift_shifts_pitch_and_keeps_length(self):
        sample_rate = 44100
        n = sample_rate // 2
        x = (0.3 * np.sin(2 * np.pi * 220 * np.arange(n) / sample_rate)).astype(
            np.float32
        )
        shifted = fast_pitch_shift(x, sample_rate, 5.0)
        self.assertEqual(len(shifted), len(x))
        self.assertTrue(np.all(np.isfinite(shifted)))

        def peak_freq(signal):
            windowed = signal * np.hanning(len(signal))
            spectrum = np.abs(np.fft.rfft(windowed))
            return np.fft.rfftfreq(len(signal), 1 / sample_rate)[
                int(np.argmax(spectrum))
            ]

        self.assertAlmostEqual(peak_freq(shifted), 220 * 2 ** (5 / 12), delta=2.0)

    def test_realtime_presets_and_status_endpoint(self):
        self.assertIn("female", REALTIME_PRESETS)
        self.assertIn("male", REALTIME_PRESETS)
        self.assertIn("robot", REALTIME_PRESETS)
        client = app.test_client()
        status = client.get("/api/realtime/status").get_json()
        self.assertIn("available", status)
        self.assertIn("presets", status)


if __name__ == "__main__":
    unittest.main()
