# `--selfcheck`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP CLI） |
| オプション | `--selfcheck` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

バックエンドの自己検査を実行します。モデルを指定しない場合は選択された backend の device / 演算検査を行い、モデルを指定した場合はそのファイルを開いて backend を初期化してから検査します。CUDA ビルドでは device 情報の取得と softcap kernel の照合、HIP ビルドでは SF4 GPU 演算と CPU 参照値の照合、CPU 選択時は SF4・MX8 演算と KV 形式の round-trip 等が検査対象です。モデルの推論品質や生成結果を評価するモードではありません（`engine/src/inkling2/ink_main.cpp:101-127`; `engine/src/inkling2/cuda/ink_cuda_backend.cu:825-848`; `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2475-2526`; `engine/src/inkling2/ink_cpu_backend.cpp:1236-1305`）。

## 使い方

```sh
# 選択された backend の基本検査。モデルなしで実行する
strata-inkling --selfcheck

# モデルを開いて backend を初期化した上で検査する
strata-inkling --selfcheck --native ./model.strata

# CPU backend を選んで検査する
strata-inkling --selfcheck --cpu

# .strata モデルを開く際、対象 section の SHA-256 検証も行う
strata-inkling --selfcheck --native ./model.strata --verify-hash
```

`--native` は `--model` と同じ parser 分岐です。省略時にモデル読み込みを必須とする一般生成経路とは異なり、selfcheck 経路ではモデルなしも許されます（`engine/src/inkling2/ink_main.cpp:101-121,396-405,544-553`）。

## 値と既定値

値を取りません。parser は指定されると `mode_selfcheck` を true にします。同じ指定を複数回しても true のままです。省略時は selfcheck を実行しません（`engine/src/inkling2/ink_main.cpp:373-374,396-398`）。

モデルパスが空でなければ、selfcheck 処理はモデルを開き、`--verify-hash` が指定されている場合はその後にハッシュ検証を行い、backend を初期化します。モデルパスが空の場合はこの一連の処理を飛ばして backend 検査へ進みます。そのため `--verify-hash` 単独ではモデルのハッシュ検証は起きません（`engine/src/inkling2/ink_main.cpp:101-121,398-405,546`）。

## 実行時の動作

`--selfcheck` はフラグの受理後、引数処理を終えたところで `--info`、`--export-tokenizer` の後、KLD 評価・参照 dump・bench・serve・通常生成より前に選ばれます。したがって `--info` または `--export-tokenizer` も同時指定した場合はそちらが先に return し、selfcheck は実行されません。ほかの後順位モードフラグとの同時指定では selfcheck が先に return します（`engine/src/inkling2/ink_main.cpp:544-549`）。

backend は通常、ビルドで利用可能な CUDA、EP-CUDA、HIP 等から選ばれ、`--cpu` があれば CPU backend を選びます。CUDA/HIP のどちらが選択可能かはビルド条件に依存します（`engine/src/inkling2/ink_backend.h:150-168`; parser とツールの対応は `docs/cli/README.md:1511-1513`）。

- CUDA backend: GPU device 情報取得後、64 要素の値を GPU に転送して softcap kernel を実行し、結果を CPU 参照値と比較します。不一致または CUDA device query 失敗で検査失敗になります（`engine/src/inkling2/cuda/ink_cuda_backend.cu:825-848`）。
- HIP backend: SF4 の GPU GEMV / WMMA 結果を CPU で dequantize した参照値と比較し、相対 L2 誤差が `1e-2` を超えると失敗します。.strata モデルがロードされている場合は Section 5 の読み取りと空でないことも検査します（`engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2475-2526`）。
- CPU backend: SF4、MX8 の dot product、FP8 E4M3・K8V8・K8V4 KV round-trip を検査します。.strata モデルがロードされている場合は Section 5 が空でないことも検査します（`engine/src/inkling2/ink_cpu_backend.cpp:1236-1305`）。

`--verify-hash` はモデルを開いた場合のみ有効です。`.strata` では Section 0〜5（Section 4 を含む）の SHA-256 を読み取り照合し、safetensors / GGUF では `verify_sections()` が成功として戻るため、この追加照合は行いません（`engine/src/inkling2/ink_main.cpp:110-115`; `engine/src/inkling2/ink_manifest.h:532-555`）。モデルを開く際は `InkModelFile::open()` が拡張子等に応じて Strata、safetensors、GGUF の処理へ振り分けます（`engine/src/inkling2/ink_manifest.h:454-477`）。

## 適用条件と副作用

この文書の対象は `strata-inkling` root の CUDA/HIP CLI parser です。Metal と SYCL には別 parser があり、索引でも `metal/` と `sycl/` の別スコープに載っています（`docs/cli/README.md:1511,1549,1572`）。選択 backend とビルド条件に応じて、CPU メモリ確保、モデルファイルの読み取り、GPU device 検査・メモリ確保・kernel 実行が発生します。selfcheck 本体にファイル出力処理は確認できません（`engine/src/inkling2/ink_main.cpp:101-127`; backend 実装は上記）。

## 出力とエラー

成功時は stdout に `[selfcheck] PASS backend=... (...)` を出して終了コード 0 です。モデルを開けない、Section hash が一致しない、backend 初期化に失敗する、または backend 検査に失敗する場合は、それぞれ `[selfcheck] FAIL open: ...`、`FAIL hash: ...`、`FAIL init: ...`、`FAIL: ...` を stderr に出して終了コード 1 です（`engine/src/inkling2/ink_main.cpp:105-127`）。CUDA / HIP / CPU の追加検査に失敗した場合の詳細文字列は各 backend が設定します（上記各 backend の selfcheck 実装）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:373-405,488-503` — `--selfcheck` と `--verify-hash` の parser、モデル指定、help 表示、未知 option の失敗経路。
- `engine/src/inkling2/ink_main.cpp:101-127,544-553` — selfcheck の優先順位、モデル open・任意の hash 検証・backend 初期化・終了コードと出力。
- `engine/src/inkling2/ink_backend.h:150-168` — ビルド条件と `--cpu` による backend 選択。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:825-848` — CUDA の device / kernel 検査。
- `engine/src/inkling2/hip/ink_hip_backend.hip.cpp:2475-2526` — HIP の SF4 検査と .strata Section 5 確認。
- `engine/src/inkling2/ink_cpu_backend.cpp:1236-1305` — CPU の演算・KV 検査と .strata Section 5 確認。
- `engine/src/inkling2/ink_manifest.h:454-477,532-555` — モデル形式の振り分けと Section SHA-256 の検証範囲。
