# `TQENC_CPU_THREADS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata 同梱の trellis encoder Python wrapper `tools/tqenc.py` で、GPU エンコード用ロックを取得できず CPU encoder に切り替わった場合のスレッド数を指定します。Strata の推論 engine の環境変数ではなく、`tools/tqenc.py` を使う変換・調査ツール向けです。`tools/trellis/README.md` はこの encoder を research 用の standalone encoder と説明しています。

## 値と判定

環境変数は GPU fallback が選ばれた時点で `os.environ.get()` から取得し、Python の `int()` で変換します。文字列全体を整数として変換し、前後の空白や符号付き整数は Python `int()` の規則で受け付けます。空文字や整数でない文字列は `ValueError` になります。値域チェックや Python 側の clamp はありません。

| 状態 | Python wrapper が渡す値 | encoder 側の扱い |
|---|---:|---|
| 未設定 | `threads or 24` | 正の値は block 数以下に制限。0 以下なら hardware concurrency（最低 1）を使う |
| 設定値 `N > 0` | `N` | `min(N, max(1, nblocks))` スレッド |
| 設定値 `0` または負数 | その整数 | hardware concurrency（最低 1）に置換 |
| 空文字・整数でない文字列 | 変換失敗 | `ValueError` が呼び出し元へ伝播し、CPU encode 呼び出しに進まない |

未設定時の `threads or 24` は、呼び出し元から渡された `threads` が truthy ならそれを使い、0 なら 24 にします。したがってこの GPU fallback 経路では、環境変数が未設定でも `threads=0` は C++ encoder の hardware concurrency 指定にならず、24 になります。環境変数が設定されていれば、呼び出し元の `threads` 引数を上書きします。正の値は C API の `int` 引数に渡され、その後 C++ 側で block 数以下に制限されます。

## 有効になる条件

- `encode(..., gpu=True)` で呼ばれること。`gpu=False` の CPU encode ではこの環境変数を読みません。
- GPU encoder は `exact` が偽で、type が `TQ2_T` でない場合に限り進みます。これらの条件を外れると、lock 処理より前に `ValueError` になります。
- `_gpu_lock` が `ok=False` を返すこと。`TQENC_GPU_LOCK` が未設定なら lock は即時に `ok=True` となり、GPU encode に進むため、この環境変数は使われません。ロック取得に成功した場合も同様です。
- lock fallback は、`~/locks/EXCL_WAIT` がある状態または lock file の flock 競合が `TQENC_GPU_WAIT` の待ち時間を超えたときに起きます。`TQENC_GPU_WAIT` が未設定なら待ち時間の既定は `1e9` 秒です。

## 実行時の詳細

GPU lock に失敗すると、`encode()` は `TQENC_CPU_THREADS` をその場で読み、`lib().tqe_encode(...)` に値を渡して CPU encode します。`TQENC_CPU_THREADS` の値を static 変数などに保存する処理はなく、fallback のたびに環境を読み直します。GPU lock 成功時は `tqh_encode(...)` の結果を返して関数を抜けるため、変数は評価されません。

C++ encoder は `nthreads <= 0` を `max(1, hardware_concurrency())` に置き換え、続いて `max(1, nblocks)` を上限にします。スレッドは block を最大4個ずつ atomic index で取得して処理します。返り値はエンコード結果と統計値で、wrapper 自体はこの変数に関するログを出しません。変換例の `tools/dsv41/tq_convert.py` は `tqenc.encode(..., gpu=not a.cpu)` を呼んでいますが、CPU fallback の失敗や `ValueError` は捕捉せず、その呼び出し元へ伝播します。

## 根拠

- 候補一覧に名前があること: `docs/envvars/000_envvers.md:1674-1678`。
- 唯一の環境読み取り、GPU/CPU 分岐、`threads` 上書き、C API 呼び出し: `tools/tqenc.py:137-165`。リポジトリ全体の完全一致検索では、環境から読む箇所は `tools/tqenc.py:162` のみでした。
- GPU lock の既定、lock timeout による `ok=False`、file lock の解放: `tools/tqenc.py:67-110`。
- C++ encoder が非正値を hardware concurrency にし、block 数で thread 数を制限する処理: `tools/trellis/tqenc.cpp:538-564`。
- encoder が standalone の research tooling である説明: `tools/trellis/README.md:1-18`、`tools/trellis/tqenc.hpp:1-6`。
- 実際の利用例: `tools/dsv41/tq_convert.py:137-149`、`tools/trellis/pilot.py:194-200`。
