"""Real local PCM bytes; no model execution or claims about the sound of speech."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
import wave

SCRIPTS = Path(__file__).resolve().parents[1] / "skills/colab-video-studio/scripts"
sys.path.insert(0, str(SCRIPTS))
import audio_artifacts as audio
import dialogue_timing


class AudioArtifacts(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name)
        (self.project / "assets").mkdir()
        self.wav = self.project / "assets/scene.wav"
        self.write_wav()
        self.plan = dict(assets={"scene_audio": dict(path="assets/scene.wav", role="audio", status="ready",
                                                   audio_artifact="assets/scene.audio.json")},
                         characters=[dict(id="alice", voice_id="alto"), dict(id="bob", voice_id="bass")],
                         voices=[dict(id="alto", description="A clear alto."), dict(id="bass", description="A low bass.")])
        self.spec = dict(asset_id="scene_audio", utterances=[
            dict(id="u1", character_id="alice", voice_id="alto", text="Hello there.", start_seconds=1, end_seconds=2),
            dict(id="u2", character_id="bob", voice_id="bass", text="Hi!", start_seconds=1.5, end_seconds=2.5)])
        self.timing = dict(utterances=[
            dict(id="u1", speaker="alice", voice_id="alto", text="Hello there."),
            dict(id="u2", speaker="bob", voice_id="bass", text="Hi!")])

    def write_wav(self, *, width=2, channels=1, rate=8000, frames=40000):
        with wave.open(str(self.wav), "wb") as stream:
            stream.setparams((channels, width, rate, frames, "NONE", "not compressed"))
            stream.writeframes(bytes([17]) * frames * channels * width)

    def aligned(self):
        spec = copy.deepcopy(self.spec)
        spec["alignment"] = dict(method="manual", provenance="Reviewer supplied sentence/word boundaries; synthetic test only.",
            sentences=[dict(utterance_id=row["id"], **{key: row[key] for key in ("text", "start_seconds", "end_seconds")})
                       for row in spec["utterances"]],
            words=[dict(utterance_id="u1", text="Hello", start_seconds=1, end_seconds=1.4),
                   dict(utterance_id="u1", text="there.", start_seconds=1.5, end_seconds=2),
                   dict(utterance_id="u2", text="Hi!", start_seconds=1.5, end_seconds=2.5)])
        return spec

    def save(self, spec=None):
        manifest = audio.create_artifact(self.project, self.plan, spec or self.spec)
        self.manifest_path = self.project / "assets/scene.audio.json"
        self.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return manifest

    def test_import_measures_every_frame_keeps_overlap_and_does_not_write(self):
        original = copy.deepcopy((self.plan, self.spec))
        manifest = audio.create_artifact(self.project, self.plan, self.spec)
        self.assertEqual(manifest["audio"]["frame_count"], 40000)
        self.assertEqual(manifest["audio"]["duration_seconds"], 5)
        self.assertEqual(manifest["audio"]["sample_rate_hz"], 8000)
        self.assertEqual(manifest["audio"]["sample_width_bytes"], 2)
        self.assertEqual(manifest["alignment"]["status"], "unavailable")
        self.assertLess(manifest["utterances"][1]["start_seconds"], manifest["utterances"][0]["end_seconds"])
        self.assertIn("Manual supplied", manifest["utterance_timing_provenance"])
        self.assertIn("not verified", manifest["limitations"])
        self.assertEqual((self.plan, self.spec), original)
        self.assertFalse((self.project / "assets/scene.audio.json").exists())
        self.assertEqual(manifest, audio.create_artifact(self.project, self.plan, self.spec))

    def test_complete_pcm_formats_and_partial_frames(self):
        for width, channels in ((1, 1), (2, 2), (3, 2), (4, 1)):
            with self.subTest(width=width, channels=channels):
                self.write_wav(width=width, channels=channels)
                manifest = audio.create_artifact(self.project, self.plan, self.spec)
                self.assertEqual(manifest["audio"]["duration_seconds"], 5)
                self.assertEqual(manifest["audio"]["channels"], channels)
        # A valid-looking RIFF extent but a data chunk one byte short of a frame.
        self.write_wav()
        raw = bytearray(self.wav.read_bytes()[:-1])
        struct.pack_into("<I", raw, 4, len(raw)-8)
        struct.pack_into("<I", raw, 40, len(raw)-44)
        self.wav.write_bytes(raw)
        with self.assertRaisesRegex(ValueError, "partial PCM frame"):
            audio.create_artifact(self.project, self.plan, self.spec)

    def test_corrupt_truncated_empty_and_non_pcm_wav_fail(self):
        original = self.wav.read_bytes()
        cases = [b"not a WAV", original[:30], original[:-2], original + b"extra"]
        non_pcm = bytearray(original)
        struct.pack_into("<H", non_pcm, 20, 3)  # IEEE float, not integer PCM.
        cases.append(bytes(non_pcm))
        wrong_rate = bytearray(original)
        struct.pack_into("<I", wrong_rate, 28, 42)  # Byte rate disagrees with frames.
        cases.append(bytes(wrong_rate))
        for raw in cases:
            with self.subTest(length=len(raw)), self.assertRaises(ValueError):
                self.wav.write_bytes(raw)
                audio.create_artifact(self.project, self.plan, self.spec)
        self.write_wav(frames=0)
        with self.assertRaisesRegex(ValueError, "nonempty"):
            audio.create_artifact(self.project, self.plan, self.spec)

    def test_ids_bindings_ranges_and_explicit_same_speaker_overlap(self):
        mutations = [dict(id="../bad"), dict(id="u2"), dict(character_id="unknown"),
                     dict(voice_id="bass"), dict(voice_id="missing"), dict(text=""),
                     dict(start_seconds=-1), dict(start_seconds=True), dict(start_seconds=float("nan")),
                     dict(end_seconds=float("inf")), dict(end_seconds=6), dict(end_seconds=1)]
        for change in mutations:
            spec = copy.deepcopy(self.spec)
            spec["utterances"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                audio.create_artifact(self.project, self.plan, spec)
        same_speaker = copy.deepcopy(self.spec)
        same_speaker["utterances"][1].update(character_id="alice", voice_id="alto")
        self.assertEqual(audio.create_artifact(self.project, self.plan, same_speaker)["utterances"], same_speaker["utterances"])
        same_speaker["utterances"].reverse()
        self.assertEqual(audio.create_artifact(self.project, self.plan, same_speaker)["utterances"], same_speaker["utterances"])

    def test_project_paths_cannot_escape_for_audio_or_manifest(self):
        for field in ("path", "audio_artifact"):
            for value in ("../outside.wav", str(self.wav.resolve())):
                plan = copy.deepcopy(self.plan)
                plan["assets"]["scene_audio"][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    audio.load_artifact(self.project, plan, "scene_audio")
        (self.project / "assets/escape.wav").symlink_to(self.project.parent / "outside.wav")
        self.plan["assets"]["scene_audio"]["path"] = "assets/escape.wav"
        with self.assertRaisesRegex(ValueError, "leaves project"):
            audio.create_artifact(self.project, self.plan, self.spec)

    def test_loading_checks_real_bytes_manifest_and_voice_dependencies(self):
        expected = self.save(self.aligned())
        self.assertEqual(audio.load_artifact(self.project, self.plan, "scene_audio"), expected)
        original = self.wav.read_bytes()
        changed = bytearray(original)
        changed[-1] ^= 1
        self.wav.write_bytes(changed)
        with self.assertRaisesRegex(ValueError, "dependencies"):
            audio.load_artifact(self.project, self.plan, "scene_audio")
        self.wav.write_bytes(original)
        for change in ("voice_binding", "missing_character", "missing_voice"):
            plan = copy.deepcopy(self.plan)
            if change == "voice_binding":
                plan["characters"][0]["voice_id"] = "bass"
            elif change == "missing_character":
                plan["characters"].pop(0)
            else:
                plan["voices"].pop(0)
            with self.subTest(change=change), self.assertRaises(ValueError):
                audio.load_artifact(self.project, plan, "scene_audio")
        prose_change = copy.deepcopy(self.plan)
        prose_change["voices"][0]["description"] = "Different native prompt prose, not different WAV bytes."
        self.assertEqual(audio.load_artifact(self.project, prose_change, "scene_audio"), expected)
        changed = copy.deepcopy(expected)
        changed["utterances"][0]["text"] = "Different text."
        self.manifest_path.write_text(json.dumps(changed))
        with self.assertRaises(ValueError):
            audio.load_artifact(self.project, self.plan, "scene_audio")

    def test_binding_matches_ids_text_speakers_and_voices_before_hydration(self):
        self.save()
        for change in (dict(id="missing"), dict(text="Hello!"), dict(speaker="bob"), dict(voice_id="bass"),
                       dict(start_seconds=0),
                       dict(measured_utterance_seconds=4), dict(planned_utterance_seconds=1), dict(not_before_seconds=0),
                       dict(voice_mode="inner"), dict(delivery="Fearful whisper"), dict(rate_multiplier=1.2)):
            spec = copy.deepcopy(self.timing)
            spec["utterances"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                audio.bind_timing(self.project, self.plan, "scene_audio", spec)
        for rows in (self.timing["utterances"][:1], self.timing["utterances"] * 2):
            with self.assertRaises(ValueError):
                audio.bind_timing(self.project, self.plan, "scene_audio", dict(utterances=rows))

    def test_hydration_uses_full_file_clock_without_extra_default_silence(self):
        self.save()
        timing = copy.deepcopy(self.timing)
        timing["utterances"][0]["voice_description"] = "Native intent only, not a recording dependency."
        original = copy.deepcopy(timing)
        hydrated, timeline = audio.bind_timing(self.project, self.plan, "scene_audio", timing)
        self.assertEqual(timing, original)
        self.assertEqual(hydrated["timing_mode"], "explicit")
        self.assertEqual(hydrated["utterances"][0]["start_seconds"], 1)
        self.assertEqual(hydrated["utterances"][0]["measured_utterance_seconds"], 1)
        self.assertFalse({"id", "voice_id", "voice_description"} & hydrated["utterances"][0].keys())
        planned = dialogue_timing.plan_timing(hydrated)
        self.assertEqual(planned["requested_duration_seconds"], 5)
        self.assertEqual(planned["required_content_seconds"], 5)
        self.assertEqual(timeline["utterances"][0]["id"], "u1")
        self.assertEqual(timeline["duration_seconds"], 5)
        timing.update(policy=dict(tail_seconds=.25), action_end_seconds=6, clip_seconds=8)
        hydrated, timeline = audio.bind_timing(self.project, self.plan, "scene_audio", timing)
        self.assertEqual(hydrated["policy"]["tail_seconds"], .25)
        self.assertEqual(hydrated["action_end_seconds"], 6)
        self.assertEqual(timeline["duration_seconds"], 8)
        timing["clip_seconds"] = 4
        with self.assertRaisesRegex(ValueError, "truncate"):
            audio.bind_timing(self.project, self.plan, "scene_audio", timing)
        decimal_spec = copy.deepcopy(self.spec)
        decimal_spec["utterances"][0].update(start_seconds=1.2, end_seconds=2.3)
        self.save(decimal_spec)
        timing = copy.deepcopy(self.timing)
        timing["utterances"][0]["measured_utterance_seconds"] = 1.1
        hydrated, _ = audio.bind_timing(self.project, self.plan, "scene_audio", timing)
        self.assertAlmostEqual(hydrated["utterances"][0]["measured_utterance_seconds"], 1.1)

    def test_alignment_is_separate_and_validates_text_order_and_containment(self):
        unaligned = audio.create_artifact(self.project, self.plan, self.spec)
        aligned = audio.create_artifact(self.project, self.plan, self.aligned())
        self.assertEqual(unaligned["artifact_digest"], aligned["artifact_digest"])
        self.assertNotEqual(unaligned["alignment_digest"], aligned["alignment_digest"])
        for change in (dict(start_seconds=.9), dict(end_seconds=2.1), dict(start_seconds=float("nan")),
                       dict(utterance_id="missing"), dict(utterance_id=[]), dict(text="Wrong transcript.")):
            spec = self.aligned()
            spec["alignment"]["sentences"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                audio.create_artifact(self.project, self.plan, spec)
        spec = self.aligned()
        spec["alignment"]["words"][:2] = list(reversed(spec["alignment"]["words"][:2]))
        with self.assertRaisesRegex(ValueError, "ordered"):
            audio.create_artifact(self.project, self.plan, spec)
        spec = self.aligned()
        spec["alignment"]["provenance"] = ""
        with self.assertRaisesRegex(ValueError, "provenance"):
            audio.create_artifact(self.project, self.plan, spec)

    def test_srt_never_invents_sentence_or_word_alignment(self):
        manifest = audio.create_artifact(self.project, self.plan, self.spec)
        with self.assertRaisesRegex(ValueError, "supplied sentence"):
            audio.srt_from_timeline(manifest)
        spec = self.aligned()
        spec["alignment"]["sentences"] = []
        with self.assertRaisesRegex(ValueError, "supplied sentence"):
            audio.srt_from_timeline(audio.create_artifact(self.project, self.plan, spec))
        spec = self.aligned()
        spec["alignment"]["sentences"].pop()
        with self.assertRaisesRegex(ValueError, "every included"):
            audio.srt_from_timeline(audio.create_artifact(self.project, self.plan, spec))
        aligned = audio.create_artifact(self.project, self.plan, self.aligned())
        self.assertEqual(audio.srt_from_timeline(aligned),
                         "1\n00:00:01,000 --> 00:00:02,000\nHello there.\n\n2\n00:00:01,500 --> 00:00:02,500\nHi!\n")

    def test_trim_speed_maps_all_supplied_timing_and_preserves_source_identity(self):
        manifest = self.save(self.aligned())
        _, timeline = audio.bind_timing(self.project, self.plan, "scene_audio", self.timing)
        original = copy.deepcopy(timeline)
        mapped = audio.map_timeline(timeline, 1, 3, 4)
        self.assertEqual(timeline, original)
        for key in ("asset_id", "audio", "artifact_digest", "alignment_digest", "voice_bindings"):
            self.assertEqual(mapped[key], manifest[key])
        self.assertEqual(mapped["duration_seconds"], 4)
        self.assertEqual(mapped["utterances"][0]["start_seconds"], 0)
        self.assertEqual(mapped["utterances"][1]["end_seconds"], 3)
        self.assertAlmostEqual(mapped["alignment"]["words"][0]["end_seconds"], .8)
        self.assertIn("00:00:01,000 --> 00:00:03,000\nHi!", audio.srt_from_timeline(mapped))
        again = audio.map_timeline(mapped, 0, 4, 2)
        self.assertEqual(len(again["transforms"]), 2)
        self.assertEqual(again["utterances"][0]["end_seconds"], 1)

    def test_trims_fail_cut_speech_but_can_drop_whole_utterances(self):
        manifest = audio.create_artifact(self.project, self.plan, self.aligned())
        for start, end in ((1.1, 3), (0, 2.4)):
            with self.subTest(start=start, end=end), self.assertRaisesRegex(ValueError, "cuts through"):
                audio.map_timeline(manifest, start, end, 2)
        for start, end, target in ((0, 6, 1), (-1, 3, 1), (2, 1, 1), (0, 3, 0), (float("nan"), 3, 1)):
            with self.subTest(start=start, end=end, target=target), self.assertRaises(ValueError):
                audio.map_timeline(manifest, start, end, target)
        silence = audio.map_timeline(manifest, 3, 5, 1)
        self.assertEqual(silence["utterances"], [])
        self.assertEqual(silence["alignment"]["sentences"], [])
        with self.assertRaisesRegex(ValueError, "supplied sentence"):
            audio.srt_from_timeline(silence)
        self.assertEqual(audio.map_timeline(silence, 0, 1, 2)["duration_seconds"], 2)
        spec = self.aligned()
        spec["utterances"][1].update(start_seconds=3, end_seconds=4)
        for level in ("sentences", "words"):
            for row in spec["alignment"][level]:
                if row["utterance_id"] == "u2":
                    row.update(start_seconds=3, end_seconds=4)
        only_first = audio.map_timeline(audio.create_artifact(self.project, self.plan, spec), 0, 2, 1)
        self.assertEqual([row["id"] for row in only_first["utterances"]], ["u1"])
        self.assertNotIn("Hi!", audio.srt_from_timeline(only_first))


if __name__ == "__main__":
    unittest.main()
