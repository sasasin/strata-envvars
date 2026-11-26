# `STRATA_METAL_STREAM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal engine の decode window が routed experts を GGUF 全体の常駐読み込みで使うか、SSD から読む expert arena で扱うかを選ぶ。`1` は常駐可能なサイズでも streaming を強制し、`0` は streaming を止める。自動判定ではモデルの tensor bytes とメモリ上限を比較する。判定後は `Window::init` が streaming 用 `ExpertStream` を開き、dense tensor をメモリへ読み、routed experts を必要に応じて SSD から arena に読む（`engine/metal/src/engine/stream.cpp:34-49`, `engine/metal/src/engine/window.cpp:714-744,975-980`）。

## 値と判定

engine は `std::getenv` で取得し、文字列全体が厳密に `"1"` または `"0"` と一致するか比較する。数値変換や trim、大文字小文字変換はしない。したがって未設定、空文字、`true`、`01`、`1x`、`0 ` などはすべて自動判定に進む（`engine/metal/src/engine/stream.cpp:34-49`）。

| build / 設定値 | 判定 |
|---|---|
| Metal engine、未設定または `"1"` 以外かつ `"0"` 以外 | 自動判定。全 tensor bytes（`per_layer_token_embd.weight` を除く）に 12 GiB の余裕を加え、resident cap に収まらなければ streaming。 |
| Metal engine、厳密に `"1"` | streaming を有効化。容量による抑制はしない。 |
| Metal engine、厳密に `"0"` | streaming を無効化。 |

自動判定の比較は `resident_fits`: `model_bytes + overhead <= resident_cap`。ここで `overhead` は 12 GiB、`phys` は `hw.memsize`、GPU working set は `recommended_working_set()` から取得する。`sysctlbyname` の戻り値はこの箇所で検査されない（`engine/metal/src/engine/stream.cpp:42-48`, `engine/metal/src/engine/arena_budget.h:135-142`）。

## 有効になる条件

- Metal backend の engine で decode window が初期化される経路で評価される。CUDA / HIP / SYCL の engine ではこの実装を通らない（`engine/metal/src/engine/window.cpp:714-744`）。
- Metal の `window_probe` は window を作る前に `setenv("STRATA_METAL_STREAM", "0", 1)` で streaming を無効にするため、その診断実行では外から渡した値は使われない（`engine/metal/probe/window_probe.cpp:40-44`）。
- Metal window が受け付けるモデル形状であること。形状・expert 数・expert/token 数の検査に失敗すると、stream 判定より前に `metal window: the geometry differs from Qwen3.8-Flash-Next's` で初期化が失敗する（`engine/metal/src/engine/window.cpp:720-728`）。
- `1` の強制指定はメモリ不足を回避しない。streaming の arena 作成、buffer 割り当て、dense 読み込みなどが失敗すれば初期化または実行が失敗する（`engine/metal/src/engine/window.cpp:740-744,975-980`; `engine/metal/src/engine/stream.cpp:61-75,450-464`）。
- この変数に対応する engine CLI 引数はない。直接起動ならプロセス環境の値が使われる。setup が生成する Mac 設定は RAM とモデル表の値から `streams(model, ram_gb)` を計算し、`STRATA_METAL_STREAM` に `"1"` / `"0"` を設定する（`terminal/strata_control/mac_fit.py:214-216`, `terminal/setup.py:11204,11337-11340`, `engine/metal/setup_mac.py:569,593-598`）。
- server は現在の環境を複製した後、config の `env` を同名キーにも代入するため、設定値が継承環境より優先される。従って setup が書いた `"0"` は、親プロセスに `STRATA_METAL_STREAM=1` があっても engine では `"0"` になる（`terminal/serve/server.py:4007-4029,9386-9394`）。Metal のモデル設定を採用する経路も `"1"` を config に書く（`terminal/strata_cli/launch/adopt.py:302-306`）。

## 実行時の詳細

`ExpertStream::wanted` 自体は値を static cache しない。ただし `Window::init` から呼ばれ、window は `window_init` で `ready()` が false のときだけ初期化されるため、実用上はモデル window の初期化時に一度評価される。初期化後に環境を変更しても、その window の `stream_` 選択は変わらない（`engine/metal/src/engine/window.cpp:714-744,3627-3638`）。

streaming が選ばれると `ExpertStream::open` は GGUF を読み取り専用で開き、各層の routed expert tensors を確認する。層に routed experts がなければ `metal stream: layer N has no routed experts` を返す。dense tensor は別途読み込まれ、window の通常の初期化・実行が続く（`engine/metal/src/engine/stream.cpp:61-75,181-220`; `engine/metal/src/engine/window.cpp:975-980`）。

streaming では arena の予算を計算し、読み込みに使える空きメモリが計画時より減った場合は縮小して再試行する。4 回の再試行後も作成できない場合は失敗する。arena が 4 buffer を超える場合や `mmap` できない場合もエラーになる（`engine/metal/src/engine/window.cpp:1726-1808`, `engine/metal/src/engine/stream.cpp:450-464`）。

## ログと測定値

decode window 初期化時、stderr に `strata metal: decode window on ...: ... streamed from the SSD (experts) ...` または `... wrapped ...` が出る（`engine/metal/src/engine/window.cpp:1013-1015`）。streaming の arena についてはメモリ予算や確保量を `strata metal stream: ...` の行で出力する。stream が選ばれない場合、streaming 固有のログは出ない（`engine/metal/src/engine/window.cpp:1769-1818`）。

失敗時の例として、model file を開けない場合は `metal stream: cannot open <path>`、routed experts がない層は `metal stream: layer N has no routed experts`、arena が 4 buffer を超える場合は `metal stream: the arena needs more than 4 buffers (lower STRATA_METAL_ARENA_GB)` を返す（`engine/metal/src/engine/stream.cpp:61-75,450`）。この関数からは自動判定で選んだ理由を示すログは出ない。

## 根拠

- 値の比較と自動判定: `engine/metal/src/engine/stream.cpp:34-49`
- 常駐 cap の式: `engine/metal/src/engine/arena_budget.h:135-142`
- 呼び出し、streaming / wrapped の分岐と起動ログ: `engine/metal/src/engine/window.cpp:714-744,1013-1015`
- probe による強制設定: `engine/metal/probe/window_probe.cpp:40-44`
- setup の値決定と config への書き込み: `terminal/strata_control/mac_fit.py:214-216`, `terminal/setup.py:11337-11340`, `engine/metal/setup_mac.py:593-598`
- config 環境変数の優先順位と engine 起動: `terminal/serve/server.py:4007-4029,9386-9394`
- stream 初期化と arena のエラー経路: `engine/metal/src/engine/stream.cpp:61-75,450-464`, `engine/metal/src/engine/window.cpp:1726-1808`
