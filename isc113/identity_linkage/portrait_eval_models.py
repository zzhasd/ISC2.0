"""Pinned local E5-small model for multilingual evidence retrieval."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
from pathlib import Path
import sys

from .core import HERE

HOME = HERE / "runs" / "portrait_eval_model_cache"
DEPENDENCIES = ("onnxruntime==1.22.1", "tokenizers==0.21.4", "huggingface-hub==0.34.4")
REPOSITORY = "Xenova/multilingual-e5-small"
REVISION = "761b726dd34fb83930e26aab4e9ac3899aa1fa78"
WEIGHTS = "onnx/model_int8.onnx"
WEIGHTS_SHA256 = "4d24e2bc01a447951524466ef533e52944bf48509e6552810bcee1a2711cb02c"
FILES = ("tokenizer.json", "config.json", WEIGHTS)


def sha256(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def model_manifest(home):
    folder = home / "retrieval"
    files = {filename: sha256(folder / Path(filename).name) for filename in FILES}
    if files[WEIGHTS] != WEIGHTS_SHA256:
        raise ValueError("The E5-small ONNX weights do not match the pinned SHA-256")
    return {"retrieval": dict(repository=REPOSITORY, revision=REVISION, sha256=files)}


def download(home, host):
    """Download pinned E5-small artifacts."""
    import requests

    def fetch(filename):
        path = home / "retrieval" / Path(filename).name
        if path.exists() and (filename != WEIGHTS or sha256(path) == WEIGHTS_SHA256):
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".part")
        with requests.Session() as session:
            session.trust_env = False
            with session.get(f"{host.rstrip('/')}/{REPOSITORY}/resolve/{REVISION}/{filename}",
                             timeout=(12, 90), stream=True) as response:
                response.raise_for_status()
                with temp.open("wb") as handle:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        handle.write(chunk)
        if filename == WEIGHTS and sha256(temp) != WEIGHTS_SHA256:
            raise ValueError(f"Checksum mismatch in {REPOSITORY}")
        temp.replace(path)
        print(f"Prepared retrieval/{path.name}", flush=True)

    with ThreadPoolExecutor(max_workers=len(FILES)) as pool:
        list(pool.map(fetch, FILES))

class LocalRetrievalModel:
    def __init__(self, home, threads=6):
        import numpy as np

        vendor = home / "packages"
        if vendor.is_dir() and str(vendor) not in sys.path:
            sys.path.insert(0, str(vendor))
        import onnxruntime as ort
        import tokenizers

        self.np = np
        self.runtime = {"onnxruntime": ort.__version__, "tokenizers": tokenizers.__version__,
                        "numpy": np.__version__}
        path = home / "retrieval"
        self.tokenizer = tokenizers.Tokenizer.from_file(str(path / "tokenizer.json"))
        self.tokenizer.enable_truncation(max_length=192)
        self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("<pad>"), pad_token="<pad>")
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = threads
        opts.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(path / Path(WEIGHTS).name), sess_options=opts,
                                            providers=["CPUExecutionProvider"])
        self.input_names = {node.name for node in self.session.get_inputs()}

    def run(self, texts, batch_size=32):
        np = self.np
        pieces = []
        for start in range(0, len(texts), batch_size):
            batch = self.tokenizer.encode_batch(texts[start:start + batch_size])
            arrays = {
                "input_ids": np.asarray([x.ids for x in batch], dtype=np.int64),
                "attention_mask": np.asarray([x.attention_mask for x in batch], dtype=np.int64),
                "token_type_ids": np.asarray([x.type_ids for x in batch], dtype=np.int64),
            }
            feed = {name: arrays[name] for name in self.input_names}
            output = self.session.run(None, feed)[0]
            mask = arrays["attention_mask"][..., None].astype(np.float32)
            vectors = (output * mask).sum(axis=1) / mask.sum(axis=1)
            pieces.append(vectors / np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-10))
        if not pieces:
            return np.empty((0, 384), dtype=np.float32)
        return np.concatenate(pieces)

