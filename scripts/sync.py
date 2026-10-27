#!/usr/bin/env python3
"""Generate the Tachimanga repository from a locally signed legacy build.

Python 3.11+, standard library only. No network updates are performed. Only extension API 1.4 is accepted.
See schema/index.proto for the protobuf format.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "eu.kanade.tachiyomi.extension.pt.mangadash"
MAX_BYTES = 30 * 1024 * 1024


def read_varint(data: bytes, offset: int = 0) -> tuple[int, int]:
    value = 0
    for i in range(10):
        if offset >= len(data):
            raise ValueError("Truncated protobuf varint")
        byte = data[offset]
        offset += 1
        if i == 9 and byte > 1:
            raise ValueError("Protobuf varint overflows uint64")
        value |= (byte & 127) << (7 * i)
        if byte < 128:
            return value, offset
    raise ValueError("Invalid protobuf varint")


def varint(value: int) -> bytes:
    if not 0 <= value < 1 << 64:
        raise ValueError("Value outside uint64 range")
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def field(number: int, value: bytes | str) -> bytes:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return varint(number << 3 | 2) + varint(len(value)) + value


def fields(data: bytes) -> list[tuple[int, int, bytes | int, bytes]]:
    """Return (number, wire type, decoded value, original field bytes)."""
    result = []
    offset = 0
    while offset < len(data):
        start = offset
        tag, offset = read_varint(data, offset)
        number, wire = tag >> 3, tag & 7
        if not 0 < number < 1 << 29:
            raise ValueError("Invalid protobuf field number")
        if wire == 0:
            value, offset = read_varint(data, offset)
        elif wire in (1, 2, 5):
            if wire == 2:
                size, offset = read_varint(data, offset)
            else:
                size = 8 if wire == 1 else 4
            end = offset + size
            if end > len(data):
                raise ValueError("Truncated protobuf field")
            value, offset = data[offset:end], end
        else:
            raise ValueError(f"Unsupported protobuf wire type: {wire}")
        result.append((number, wire, value, data[start:offset]))
    return result


def one(data: bytes, number: int, wire: int = 2) -> bytes | int:
    matches = [v for n, w, v, _ in fields(data) if n == number and w == wire]
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one protobuf field {number}")
    return matches[0]


def pack_index(binary: bytes) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as stream:
        stream.write(binary)
    return output.getvalue()


def unpack_index(binary: bytes) -> bytes:
    with gzip.GzipFile(fileobj=io.BytesIO(binary)) as stream:
        result = stream.read(MAX_BYTES + 1)
    if len(result) > MAX_BYTES:
        raise ValueError("Index is too large")
    return result


def int_field(number: int, value: int) -> bytes:
    return varint(number << 3) + varint(value)


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def verify_archive(data: bytes, expected_sha: str, kind: str) -> None:
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError(f"{kind}: SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip() or "AndroidManifest.xml" not in archive.namelist():
            raise ValueError("Invalid extension archive")
        if kind == "jar":
            if not {"META-INF/CERT.RSA", "META-INF/CERT.SF"} <= set(archive.namelist()):
                raise ValueError("Missing JAR signature")
            classes = [archive.read(n) for n in archive.namelist() if n.endswith(".class")]
            methods = [b"popularMangaRequest", b"popularMangaParse", b"searchMangaRequest",
                       b"searchMangaParse", b"mangaDetailsParse", b"chapterListParse", b"pageListParse"]
            if any(b"keiyoushi/source/KeiSource" in b for b in classes):
                raise ValueError("Unsupported extension API 1.6")
            if any(native in cls for cls in classes for native in
                   (b"android/graphics/pdf/PdfRenderer", b"android/os/ParcelFileDescriptor")):
                raise ValueError("Unsupported Android PDF reader")
            if not any(b"eu/kanade/tachiyomi/source/online/HttpSource" in b
                       and all(m in b for m in methods) for b in classes):
                raise ValueError("Legacy HttpSource methods are missing")


def prepare(root: Path) -> dict[str, bytes]:
    config = json.loads((root / "repository.json").read_text())
    release = json.loads((root / "release.json").read_text())
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["repository"]):
        raise ValueError("Invalid repository")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", config["branch"]):
        raise ValueError("Invalid branch")
    if config["extensionLib"] != "1.4" or release["extensionLib"] != "1.4":
        raise ValueError("Only the legacy extension API 1.4 is supported")
    if release["packageName"] != PACKAGE or release["sources"][0]["id"] != "4579000402227688678":
        raise ValueError("Source identity changed")
    if not re.fullmatch(r"1\.4\.[0-9]+", release["versionName"]):
        raise ValueError("Invalid legacy version")
    if int(release["versionCode"]) != 104000 + int(release["versionName"].split(".")[-1]):
        raise ValueError("Version code does not match legacy version")
    cert = (root / "signing-certificate.der").read_bytes()
    signer = hashlib.sha256(cert).hexdigest()
    if signer != release["signingKey"]:
        raise ValueError("Certificate fingerprint mismatch")
    base = f"https://raw.githubusercontent.com/{config['repository']}/{config['branch']}/"
    resources, checksums = {}, []
    for kind in ("jar", "apk"):
        item = release["artifacts"][kind]
        filename = f"tachiyomi-pt.mangadash-v{release['versionName']}.{kind}"
        if item["name"] != filename:
            raise ValueError("Artifact filename does not match release")
        relative = f"{kind}/{filename}"
        verify_archive((root / relative).read_bytes(), item["sha256"], kind)
        resources[kind + "Url"] = base + relative
        checksums.append(f"{item['sha256']}  {relative}")
    resources["iconUrl"] = base + "icon.png"
    entry = {key: release[key] for key in ("name", "packageName", "extensionLib", "versionCode", "versionName", "sources")}
    entry.update(resources=resources, contentWarning="CONTENT_WARNING_MIXED")
    website = "https://github.com/" + config["repository"]
    index = {"name": config["name"], "badgeLabel": config["badgeLabel"], "signingKey": signer,
             "contact": {"website": website}, "extensionList": {"extensions": [entry]}}
    resource_pb = field(1, resources["apkUrl"]) + field(2, resources["iconUrl"]) + field(501, resources["jarUrl"])
    extension_pb = (field(1, entry["name"]) + field(2, PACKAGE) + field(3, resource_pb)
                    + field(4, "1.4") + int_field(5, int(entry["versionCode"]))
                    + field(6, entry["versionName"]) + int_field(7, 2))
    for source in entry["sources"]:
        if source["homeUrl"] != "https://mangadash.net" or source["language"] != "pt-BR":
            raise ValueError("Unexpected source configuration")
        source_pb = (int_field(1, int(source["id"])) + field(2, source["name"])
                     + field(3, source["language"]) + field(4, source["homeUrl"]))
        extension_pb += field(8, source_pb)
    index_pb = (field(1, config["name"]) + field(2, config["badgeLabel"]) + field(3, signer)
                + field(4, field(1, website)) + field(101, field(1, extension_pb)))
    repo = {"index_v2": base + "index.pb", "meta": {"name": config["name"], "website": website,
            "signingKeyFingerprint": signer}}
    return {"index.json": json_bytes(index), "index.pb": pack_index(index_pb),
            "repo.json": json_bytes(repo), "SHA256SUMS": ("\n".join(checksums) + "\n").encode()}


def sync(destination: Path = ROOT) -> bool:
    pending = prepare(destination)
    changed = False
    for name, data in pending.items():
        path = destination / name
        if not path.exists() or path.read_bytes() != data:
            temporary = path.with_name(path.name + ".tmp")
            temporary.write_bytes(data)
            temporary.replace(path)
            changed = True
    print("Índices da API 1.4 verificados." if not changed else "Índices da API 1.4 atualizados.")
    return changed


if __name__ == "__main__":
    sync()
