"""Atomic file writes and the canonical JSON dump format."""

import json
import os
import tempfile


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    binary = isinstance(data, bytes)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def dump_json(obj):
    return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"
