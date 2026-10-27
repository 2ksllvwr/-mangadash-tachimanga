#!/usr/bin/env python3
"""Publish only MangaDash from one immutable, verified Keiyoushi snapshot.

Python 3.11+, standard library only. Binary artifacts remain unmodified.
The protobuf extension message is preserved byte for byte, including unknown
fields. See schema/index.proto for the upstream format.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "eu.kanade.tachiyomi.extension.pt.mangadash"
UPSTREAM = "https://raw.githubusercontent.com/keiyoushi/extensions"
API = "https://api.github.com/repos/keiyoushi/extensions"
EXPECTED_KEY = "9add655a78e96c4ec7a53ef89dccb557cb5d767489fac5e785d671a5a75d4da2"
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


def release_url(url: str, suffix: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    filename = parsed.path.rsplit("/", 1)[-1]
    path_pattern = (r"/keiyoushi/extensions/releases/download/[0-9a-f]{7,40}/"
                    r"tachiyomi-pt\.mangadash-v[0-9.]+" + re.escape(suffix))
    if (parsed.scheme != "https" or parsed.netloc != "github.com"
            or not re.fullmatch(path_pattern, parsed.path) or parsed.query or parsed.fragment):
        raise ValueError(f"Unexpected upstream {suffix} URL")
    return filename


def validate_config(config: dict) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", config["repository"]):
        raise ValueError("Invalid owner/repository")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", config["branch"]):
        raise ValueError("Use a simple branch name without slashes")
    if not config["name"] or not config["badgeLabel"]:
        raise ValueError("Repository name and badge are required")


def unpack_index(binary: bytes) -> bytes:
    if not binary.startswith(b"\x1f\x8b"):
        return binary
    with gzip.GzipFile(fileobj=io.BytesIO(binary)) as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("Decompressed index exceeded size limit")
    return data


def pack_index(binary: bytes) -> bytes:
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode="wb", mtime=0) as stream:
        stream.write(binary)
    return output.getvalue()


def make_indexes(original: dict, binary: bytes, config: dict) -> tuple[dict, bytes, dict]:
    validate_config(config)
    binary = unpack_index(binary)
    candidates = [e for e in original["extensionList"]["extensions"] if e["packageName"] == PACKAGE]
    if len(candidates) != 1:
        raise ValueError("MangaDash is missing or duplicated in upstream JSON")
    extension = candidates[0]
    if original["signingKey"] != EXPECTED_KEY or one(binary, 3).decode() != EXPECTED_KEY:
        raise ValueError("Upstream signing key changed; manual review required")
    if not extension.get("sources") or any(s["homeUrl"] != "https://mangadash.net" for s in extension["sources"]):
        raise ValueError("Unexpected MangaDash source URL")
    for kind in ("jar", "apk"):
        release_url(extension["resources"][kind + "Url"], "." + kind)

    extension_list = one(binary, 101)
    matches = [v for n, w, v, _ in fields(extension_list)
               if n == 1 and w == 2 and one(v, 2).decode() == PACKAGE]
    if len(matches) != 1:
        raise ValueError("MangaDash is missing or duplicated in upstream protobuf")
    selected = matches[0]
    if one(selected, 6).decode() != extension["versionName"] or one(selected, 5, 0) != int(extension["versionCode"]):
        raise ValueError("JSON and protobuf versions do not match")
    resources = one(selected, 3)
    for number, key in ((1, "apkUrl"), (2, "iconUrl"), (501, "jarUrl")):
        if one(resources, number).decode() != extension["resources"][key]:
            raise ValueError("JSON and protobuf resource URLs do not match")
    proto_sources = [v for n, w, v, _ in fields(selected) if n == 8 and w == 2]
    expected_sources = [(int(s["id"]), s["language"], s["homeUrl"]) for s in extension["sources"]]
    actual_sources = [(one(s, 1, 0), one(s, 3).decode(), one(s, 4).decode()) for s in proto_sources]
    if actual_sources != expected_sources:
        raise ValueError("JSON and protobuf source IDs do not match")

    website = "https://github.com/" + config["repository"]
    output = copy.deepcopy(original)
    output["name"] = config["name"]
    output["badgeLabel"] = config["badgeLabel"]
    output["contact"] = {"website": website}
    output["extensionList"] = {"extensions": [copy.deepcopy(extension)]}
    output.pop("extensionListUrl", None)
    # Preserve any unknown top-level fields, and the complete selected extension.
    preserved = b"".join(raw for n, _, _, raw in fields(binary) if n not in (1, 2, 4, 101, 102))
    published = (field(1, config["name"]) + field(2, config["badgeLabel"])
                 + preserved + field(4, field(1, website)) + field(101, field(1, selected)))
    return output, pack_index(published), extension


def download(url: str) -> bytes:
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "MangaDash-Tachimanga-Repository/1.0"})
            with urllib.request.urlopen(request, timeout=30) as response:
                data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("Upstream response exceeded size limit")
                return data
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("Download failed")


def verify_archive(data: bytes, expected_sha: str, kind: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise ValueError("Missing upstream SHA-256")
    if hashlib.sha256(data).hexdigest() != expected_sha:
        raise ValueError(f"{kind}: upstream SHA-256 mismatch")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if archive.testzip() is not None or "AndroidManifest.xml" not in archive.namelist():
            raise ValueError(f"{kind}: corrupt extension archive")
        if kind == "jar" and not {"META-INF/CERT.RSA", "META-INF/CERT.SF"} <= set(archive.namelist()):
            raise ValueError("JAR signature files are missing")


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode()


def sync(destination: Path = ROOT, cache: Path | None = None) -> bool:
    config = json.loads((destination / "repository.json").read_text())
    if cache:
        commit = json.loads((cache / "upstream-tree.json").read_text())["sha"]
        raw_json = (cache / "upstream-full-index.json").read_bytes()
        raw_pb = (cache / "index.pb").read_bytes()
    else:
        commit = json.loads(download(API + "/git/ref/heads/repo"))["object"]["sha"]
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Invalid upstream commit")
        raw_json = download(f"{UPSTREAM}/{commit}/index.json")
        raw_pb = download(f"{UPSTREAM}/{commit}/index.pb")
    output, binary, extension = make_indexes(json.loads(raw_json), raw_pb, config)
    index_url = f"https://raw.githubusercontent.com/{config['repository']}/{config['branch']}/index.pb"
    repo = {"index_v2": index_url, "meta": {"name": config["name"],
            "website": "https://github.com/" + config["repository"],
            "signingKeyFingerprint": EXPECTED_KEY}}
    pending = {"index.json": json_bytes(output), "index.pb": binary, "repo.json": json_bytes(repo)}
    assets = json.loads((cache / "release-assets.json").read_bytes() if cache
                        else download(f"{UPSTREAM}/{commit}/release-assets.json"))[PACKAGE]
    checksums, origins = [], {}
    for kind in ("jar", "apk"):
        url = extension["resources"][kind + "Url"]
        name = release_url(url, "." + kind)
        info = assets[kind]
        if info["name"] != name:
            raise ValueError("Artifact filename and checksum metadata differ")
        current = destination / kind / name
        if current.exists() and hashlib.sha256(current.read_bytes()).hexdigest() == info["sha256"]:
            data = current.read_bytes()
        else:
            data = (cache / name).read_bytes() if cache else download(url)
        verify_archive(data, info["sha256"], kind)
        path = f"{kind}/{name}"
        pending[path] = data
        checksums.append(f"{info['sha256']}  {path}")
        origins[kind] = {"url": url, "sha256": info["sha256"]}
    pending["SHA256SUMS"] = ("\n".join(checksums) + "\n").encode()
    if all((destination / name).exists() and (destination / name).read_bytes() == data
           for name, data in pending.items()):
        print("MangaDash já está atualizado; nenhum arquivo alterado.")
        return False

    tag = urllib.parse.urlsplit(extension["resources"]["jarUrl"]).path.split("/")[-2]
    pending["provenance.json"] = json_bytes({
        "upstreamRepository": "https://github.com/keiyoushi/extensions",
        "indexCommit": commit, "indexJsonSha256": hashlib.sha256(raw_json).hexdigest(),
        "indexProtobufSha256": hashlib.sha256(raw_pb).hexdigest(),
        "packageName": PACKAGE, "versionName": extension["versionName"],
        "sourceCode": f"https://github.com/keiyoushi/extensions-source/tree/{tag}/src/pt/mangadash",
        "artifacts": origins, "binaryModified": False,
    })
    # Validate everything before changing any deliverable; all writes are local.
    for name, data in pending.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(data)
        temporary.replace(path)
    for kind in ("jar", "apk"):
        for old in (destination / kind).glob("*.*"):
            if old.name != origins[kind]["url"].rsplit("/", 1)[1]:
                old.unlink()
    print(f"MangaDash {extension['versionName']}: índices e arquivos verificados.")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, help="Use a previously downloaded snapshot for offline preparation")
    args = parser.parse_args()
    sync(cache=args.cache)
