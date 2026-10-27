#!/usr/bin/env python3
"""Prepare a pinned PDFBox parser without desktop image codec initialization."""
import argparse
import hashlib
import os
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ARTIFACTS = {
    'pdfbox.jar': ('org/apache/pdfbox/pdfbox/2.0.37/pdfbox-2.0.37.jar', 'fcb04e6dac53f8681108bb66d5ac2ca72987b6c6795b14a8071636fc49a5d703'),
    'fontbox.jar': ('org/apache/pdfbox/fontbox/2.0.37/fontbox-2.0.37.jar', '992e14d5e903f69517903a1a817040ed7bf1288e768870e0a27bf9090bb34ec3'),
    'commons-logging.jar': ('commons-logging/commons-logging/1.2/commons-logging-1.2.jar', 'daddea1ea0be0f56978ab3006b8ac92834afeefbd9b7e4e6316fca57df0fa636'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    for name, (path, expected) in ARTIFACTS.items():
        local = output / name
        if not local.exists() or hashlib.sha256(local.read_bytes()).hexdigest() != expected:
            with urllib.request.urlopen('https://repo.maven.apache.org/maven2/' + path, timeout=30) as response:
                data = response.read()
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError(name + ': upstream checksum mismatch')
            local.write_bytes(data)
        print(name + ': SHA-256 verified', flush=True)
    javac = [shutil.which('javac')] if shutil.which('javac') else ['java', '--module', 'jdk.compiler/com.sun.tools.javac.Main']
    classes = output / '.patch-classes'
    classes.mkdir(exist_ok=True)
    classpath = os.pathsep.join(str(output / name) for name in ARTIFACTS)
    subprocess.run(javac + ['--release', '8', '-cp', classpath, '-d', str(classes),
                           str(root / 'source/headless-pdfbox/FilterFactory.java')], check=True)
    entry = 'org/apache/pdfbox/filter/FilterFactory.class'
    with zipfile.ZipFile(output / 'pdfbox.jar') as original, zipfile.ZipFile(output / 'pdfbox-headless.jar', 'w', zipfile.ZIP_DEFLATED) as patched:
        for name in sorted(original.namelist()):
            if not name.endswith('/') and name != entry:
                patched.writestr(name, original.read(name))
        patched.writestr(entry, (classes / entry).read_bytes())
    assets = output.parent / 'assets/licenses'
    assets.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACTS:
        with zipfile.ZipFile(output / name) as archive:
            for item in archive.namelist():
                if item.startswith('META-INF/') and ('LICENSE' in item.upper() or 'NOTICE' in item.upper()) and not item.endswith('/'):
                    (assets / (name + '_' + Path(item).name)).write_bytes(archive.read(item))
    tests = output / '.test-classes'
    tests.mkdir(exist_ok=True)
    runtime_cp = os.pathsep.join(str(output / name) for name in ['pdfbox-headless.jar', 'fontbox.jar', 'commons-logging.jar'])
    extractor = output.parent / 'src/eu/kanade/tachiyomi/extension/pt/mangadash/PdfImageExtractor.java'
    subprocess.run(javac + ['--release', '8', '-cp', runtime_cp, '-d', str(tests),
                           str(extractor), str(root / 'tests/PdfExtractorTest.java')], check=True)
    subprocess.run(['java', '--limit-modules', 'java.base,java.logging,java.xml', '-cp',
                    str(tests) + os.pathsep + runtime_cp, 'PdfExtractorTest', str(root / 'tests/fixtures')], check=True)


if __name__ == '__main__':
    main()
