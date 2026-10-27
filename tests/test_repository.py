import gzip
import hashlib
import importlib.util
import json
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync', ROOT / 'scripts/sync.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class RepositoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release = json.loads((ROOT / 'release.json').read_text())
        cls.config = json.loads((ROOT / 'repository.json').read_text())
        cls.index = json.loads((ROOT / 'index.json').read_text())
        cls.binary = (ROOT / 'index.pb').read_bytes()
        cls.extension = sync.one(sync.one(gzip.decompress(cls.binary), 101), 1)

    def test_only_mangadash_is_published(self):
        self.assertEqual([e['packageName'] for e in self.index['extensionList']['extensions']], [sync.PACKAGE])
        self.assertEqual(sync.one(self.extension, 2).decode(), sync.PACKAGE)

    def test_legacy_version_is_declared_in_both_indexes(self):
        self.assertEqual(self.release['extensionLib'], '1.4')
        self.assertEqual(sync.one(self.extension, 4).decode(), '1.4')
        self.assertEqual(sync.one(self.extension, 5, 0), int(self.release['versionCode']))
        self.assertEqual(sync.one(self.extension, 6).decode(), self.release['versionName'])

    def test_source_id_retains_64_bit_precision(self):
        source = sync.one(self.extension, 8)
        expected = 4579000402227688678
        self.assertGreater(expected, 2**53)
        self.assertEqual(sync.one(source, 1, 0), expected)
        self.assertEqual(self.release['sources'][0]['id'], str(expected))
        self.assertEqual(sync.one(source, 3).decode(), 'pt-BR')
        self.assertEqual(sync.one(source, 4).decode(), 'https://mangadash.net')

    def test_indexes_agree_on_resource_urls(self):
        resources = sync.one(self.extension, 3)
        entry = self.index['extensionList']['extensions'][0]
        for number, key in [(1, 'apkUrl'), (2, 'iconUrl'), (501, 'jarUrl')]:
            self.assertEqual(sync.one(resources, number).decode(), entry['resources'][key])
            self.assertTrue(entry['resources'][key].startswith(
                'https://raw.githubusercontent.com/2ksllvwr/-mangadash-tachimanga/main/'))

    def test_signer_matches_public_certificate(self):
        expected = hashlib.sha256((ROOT / 'signing-certificate.der').read_bytes()).hexdigest()
        self.assertEqual(expected, self.release['signingKey'])
        self.assertEqual(expected, self.index['signingKey'])
        self.assertEqual(expected, sync.one(gzip.decompress(self.binary), 3).decode())
        self.assertEqual(expected, json.loads((ROOT / 'repo.json').read_text())['meta']['signingKeyFingerprint'])

    def test_artifact_checksums_and_signatures_exist(self):
        for kind, item in self.release['artifacts'].items():
            data = (ROOT / kind / item['name']).read_bytes()
            sync.verify_archive(data, item['sha256'], kind)
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                sync.verify_archive(data + b'modified', item['sha256'], kind)

    def test_jar_manifest_matches_build_metadata(self):
        item = self.release['artifacts']['jar']
        with zipfile.ZipFile(ROOT / 'jar' / item['name']) as archive:
            manifest = ET.fromstring(archive.read('AndroidManifest.xml'))
        ns = '{http://schemas.android.com/apk/res/android}'
        self.assertEqual(manifest.attrib[ns + 'versionName'], self.release['versionName'])
        self.assertEqual(manifest.attrib[ns + 'versionCode'], self.release['versionCode'])
        self.assertEqual(manifest.attrib['package'], sync.PACKAGE)

    def test_generated_metadata_keeps_source_identity(self):
        build = json.loads((ROOT / 'source/build-info.json').read_text())
        self.assertEqual(str(build['sources'][0]['id']), self.release['sources'][0]['id'])
        self.assertEqual(build['versionName'], self.release['versionName'])
        self.assertEqual(str(build['versionCode']), self.release['versionCode'])

    def test_pdf_reader_does_not_reference_android_renderer(self):
        item = self.release['artifacts']['jar']
        with zipfile.ZipFile(ROOT / 'jar' / item['name']) as archive:
            classes = b''.join(archive.read(name) for name in archive.namelist()
                               if name.endswith('.class'))
        self.assertIn(b'__mangadash_pdf', classes)
        for unsupported in [b'android/graphics/pdf/PdfRenderer',
                            b'android/os/ParcelFileDescriptor']:
            self.assertNotIn(unsupported, classes)

    def test_pdf_dependency_licenses_are_in_release(self):
        for kind, item in self.release['artifacts'].items():
            with zipfile.ZipFile(ROOT / kind / item['name']) as archive:
                for dependency, suffix in [('pdfbox.jar', ''), ('fontbox.jar', ''),
                                           ('commons-logging.jar', '.txt')]:
                    for document in ['LICENSE', 'NOTICE']:
                        self.assertTrue(archive.read(
                            f'assets/licenses/{dependency}_{document}{suffix}'))

    def test_new_api_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            shutil.copytree(ROOT, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
            config = dict(self.config, extensionLib='1.6')
            (target / 'repository.json').write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError, 'legacy'):
                sync.prepare(target)

    def test_bad_checksum_cannot_overwrite_index(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            shutil.copytree(ROOT, target, dirs_exist_ok=True, ignore=shutil.ignore_patterns('__pycache__'))
            release = json.loads((target / 'release.json').read_text())
            release['artifacts']['jar']['sha256'] = '0' * 64
            (target / 'release.json').write_text(json.dumps(release))
            before = (target / 'index.pb').read_bytes()
            with self.assertRaisesRegex(ValueError, 'SHA-256'):
                sync.sync(target)
            self.assertEqual((target / 'index.pb').read_bytes(), before)

    def test_generation_is_deterministic(self):
        pending = sync.prepare(ROOT)
        for name, data in pending.items():
            self.assertEqual((ROOT / name).read_bytes(), data)
        self.assertEqual(sync.pack_index(gzip.decompress(self.binary)), self.binary)

    def test_wire_parser_rejects_corruption(self):
        for data in [b'\x0a\x05ab', b'\x80', b'\x00', b'\x0f', b'\xff' * 11]:
            with self.assertRaises(ValueError):
                sync.fields(data)
        self.assertEqual(sync.fields(b'\x08\x96\x01')[0][:3], (1, 0, 150))
        self.assertEqual(sync.varint(150), b'\x96\x01')

    def test_no_private_signing_keys_are_in_repository(self):
        forbidden = [p for p in ROOT.rglob('*') if p.is_file() and
                     (p.suffix in {'.p12', '.jks', '.key'} or p.name == 'password.txt')]
        self.assertEqual(forbidden, [])


if __name__ == '__main__':
    unittest.main()
