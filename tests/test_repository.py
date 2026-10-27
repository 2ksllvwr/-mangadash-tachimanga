import copy
import gzip
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("sync", ROOT / "scripts/sync.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


def selected_message(binary):
    extension_list = sync.one(gzip.decompress(binary), 101)
    return sync.one(extension_list, 1)


class RepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = json.loads((ROOT / "index.json").read_text())
        cls.binary = (ROOT / "index.pb").read_bytes()
        cls.config = json.loads((ROOT / "repository.json").read_text())

    def test_index_is_gzipped_and_contains_only_mangadash(self):
        self.assertEqual(self.binary[:2], b"\x1f\x8b")
        entries = self.index["extensionList"]["extensions"]
        self.assertEqual([e["packageName"] for e in entries], [sync.PACKAGE])
        selected = selected_message(self.binary)
        self.assertEqual(sync.one(selected, 2).decode(), sync.PACKAGE)
        self.assertEqual(sync.one(selected, 6).decode(), entries[0]["versionName"])

    def test_source_id_keeps_64_bit_precision(self):
        entry = self.index["extensionList"]["extensions"][0]
        source = sync.one(selected_message(self.binary), 8)
        expected = int(entry["sources"][0]["id"])
        self.assertGreater(expected, 2**53)
        self.assertEqual(sync.one(source, 1, 0), expected)
        self.assertEqual(sync.one(source, 4).decode(), "https://mangadash.net")

    def test_repository_urls_match_configuration(self):
        repo = json.loads((ROOT / "repo.json").read_text())
        self.assertEqual(repo["index_v2"],
                         f"https://raw.githubusercontent.com/{self.config['repository']}/{self.config['branch']}/index.pb")
        self.assertEqual(repo["meta"]["signingKeyFingerprint"], sync.EXPECTED_KEY)
        self.assertEqual(sync.one(gzip.decompress(self.binary), 3).decode(), sync.EXPECTED_KEY)

    def test_filter_removes_other_extensions_and_preserves_unknown_fields(self):
        index = copy.deepcopy(self.index)
        other = copy.deepcopy(index["extensionList"]["extensions"][0])
        other["packageName"] = "eu.kanade.tachiyomi.extension.en.example"
        index["extensionList"]["extensions"].append(other)
        # Field 99 below is deliberately unknown to today's Extension schema.
        target = selected_message(self.binary) + b"\x9a\x06\x03xyz"
        other_pb = sync.field(2, other["packageName"])
        raw = gzip.decompress(self.binary)
        header = b"".join(x[3] for x in sync.fields(raw) if x[0] != 101)
        upstream = sync.pack_index(header + sync.field(101, sync.field(1, other_pb) + sync.field(1, target)))
        filtered, binary, _ = sync.make_indexes(index, upstream, self.config)
        self.assertEqual(len(filtered["extensionList"]["extensions"]), 1)
        self.assertEqual(selected_message(binary), target)

    def test_missing_or_duplicate_source_is_rejected(self):
        for entries in ([], self.index["extensionList"]["extensions"] * 2):
            index = copy.deepcopy(self.index)
            index["extensionList"]["extensions"] = entries
            with self.assertRaises(ValueError):
                sync.make_indexes(index, self.binary, self.config)

    def test_mismatched_version_is_rejected(self):
        index = copy.deepcopy(self.index)
        index["extensionList"]["extensions"][0]["versionName"] = "1.6.999"
        with self.assertRaisesRegex(ValueError, "versions"):
            sync.make_indexes(index, self.binary, self.config)

    def test_changed_signer_is_rejected(self):
        index = copy.deepcopy(self.index)
        index["signingKey"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "signing key"):
            sync.make_indexes(index, self.binary, self.config)

    def test_artifacts_have_expected_sha_and_archive_structure(self):
        provenance = json.loads((ROOT / "provenance.json").read_text())
        for kind in ("jar", "apk"):
            info = provenance["artifacts"][kind]
            path = ROOT / kind / sync.release_url(info["url"], "." + kind)
            data = path.read_bytes()
            sync.verify_archive(data, info["sha256"], kind)
            self.assertEqual(hashlib.sha256(data).hexdigest(), info["sha256"])
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                sync.verify_archive(data + b"modified", info["sha256"], kind)

    def test_unexpected_download_hosts_and_paths_are_rejected(self):
        valid = self.index["extensionList"]["extensions"][0]["resources"]["jarUrl"]
        for invalid in (valid.replace("https:", "http:"),
                        valid.replace("github.com/", "github.com.evil.example/"),
                        valid.replace("/keiyoushi/", "/someone/"),
                        valid.replace("/download/", "/download/../"), valid + "?other=1"):
            with self.assertRaises(ValueError):
                sync.release_url(invalid, ".jar")

    def test_wire_parser_rejects_corrupt_messages(self):
        for binary in (b"\x0a\x05ab", b"\x80", b"\x00", b"\x0f", b"\xff" * 11):
            with self.assertRaises(ValueError):
                sync.fields(binary)
        # Independently known protobuf: field 1, varint value 150.
        self.assertEqual(sync.fields(b"\x08\x96\x01")[0][:3], (1, 0, 150))
        self.assertEqual(sync.varint(150), b"\x96\x01")

    def test_repeated_generation_is_identical(self):
        index, binary, _ = sync.make_indexes(self.index, self.binary, self.config)
        self.assertEqual(index, self.index)
        self.assertEqual(binary, self.binary)

    def test_failed_asset_validation_does_not_overwrite_existing_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "repository.json").write_text(json.dumps(self.config))
            (root / "index.pb").write_bytes(b"keep-existing-index")
            upstream_index = json.dumps(self.index).encode()
            bad_metadata = {sync.PACKAGE: {"jar": {"name": "wrong.jar", "sha256": "0" * 64}}}
            responses = [b'{"object":{"sha":"' + b"a" * 40 + b'"}}',
                         upstream_index, self.binary, json.dumps(bad_metadata).encode()]
            with patch.object(sync, "download", side_effect=responses):
                with self.assertRaisesRegex(ValueError, "filename"):
                    sync.sync(root)
            self.assertEqual((root / "index.pb").read_bytes(), b"keep-existing-index")


if __name__ == "__main__":
    unittest.main()
