# `STRATA_METAL_IO_THREADS`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

Metal engine の SSD expert streaming 経路が使う I/O worker 数を設定する。worker は expert のファイル読み取りを処理し、decode 時には現在の layer の不足 expert と、次の layer などの read-ahead を読み込む。変数は Metal engine の `ExpertStream::open()` で一度読み、値を `nio_` に保存する。`ExpertStream::make_arena()` はその数だけ worker thread を生成する。

この設定は Strata の Metal engine にある streaming 専用であり、通常の CUDA/HIP/SYCL engine の worker 数には適用されない。streaming を使わないモデル経路では `ExpertStream` 自体を開かないため、値は読み取られず worker 数も変わらない。

## 値と判定

共通 helper は未設定または空文字列なら既定値を返し、それ以外は `std::atoi()` で変換する。その後 `std::max(1, ...)` を適用する。

| 環境変数の値 | `nio_` |
|---|---:|
| 未設定、空文字列 | 6（既定値） |
| `4` | 4 |
| `0`, `-3` | 1（下限 clamp） |
| `2threads`, `2.5` | 2（`atoi` が先頭の整数部分を変換し、後続文字を検査しない） |
| `threads`, 空白だけ | 1（`atoi` の変換結果 0 を下限 clamp） |
| `  +3tail` | 3（先頭空白と符号付き整数を受け付ける） |

大文字小文字や数値文字列全体の妥当性検査はありません。整数型 `int` で表現できない数値に対する `atoi` の結果は、この実装から保証できません。正の値に対するコード上の上限 clamp はありません。

## 有効になる条件

- `Window::init()` が Qwen3.8-Flash-Next の所定 geometry（48 layers など）を受け付けている。
- `ExpertStream::wanted()` が true で、`Window::init()` が streaming を選んでいる。`STRATA_METAL_STREAM=1` は明示的に有効化し、`=0` は無効化する。その他の値または未設定時はモデルの重みサイズと Metal working set 等による自動判定を使う。
- `ExpertStream::open()` が成功し、後続の arena 作成に進む。worker thread の生成は `make_arena()` 内で行われる。

したがって、`STRATA_METAL_IO_THREADS` を設定しただけでは streaming は有効にならない。streaming が無効ならこの変数は実行時の動作に影響しない。

## 実行時の詳細

`ExpertStream::open()` はファイルを開いた後、`env_int("STRATA_METAL_IO_THREADS", 6)` から値を取得し、最低 1 に丸めて `nio_` に格納する。値は model/window の初期化時に読み取られ、以降の `make_arena()` が `nio_` 個の `std::thread` を起動する。動作中に環境変数を書き換えても、既存 `ExpertStream` の worker 数は変わらない。別プロセスへの転送や上書きはこの読み取り箇所では行わない。

各 worker は共通の queue を待ち、urgent queue が空でなければそちらを優先し、なければ read-ahead queue から job を取り出す。job ごとに expert の一部を読み、expert の全 piece が完了すると `smap_` を更新し、待機側へ完了を通知する。`nio_` はこの読み取りの並列度に関係するが、ソースだけから速度や最適値は断定できない。起動時の streaming ログには実際の I/O thread 数が `%d I/O threads` として表示される。

## 根拠

- `metal/src/engine/stream.cpp:27-30`: unset/empty fallback と `atoi` を行う helper。
- `metal/src/engine/stream.cpp:149-150`: 既定値 6 で読み取り、最低 1 に clamp。
- `metal/src/engine/stream.cpp:304-329,332-343`: worker の queue 処理と各 job の完了処理。
- `metal/src/engine/stream.cpp:478-479,538-541`: `nio_` 個の thread 起動と thread 数を含む起動ログ。
- `metal/src/engine/window.cpp:414-435`: 対応 geometry の確認と streaming 経路を選ぶ `ExpertStream::wanted()` / `open()` の呼び出し。
- `metal/src/engine/stream.cpp:33-48`、`metal/src/engine/stream.h:34-40`: streaming の明示指定と自動選択の判定。
- `docs/MAC.md:183-200`: Metal の streaming を含む設定一覧。`STRATA_METAL_IO_THREADS` 自体の説明や推奨値、測定値は記載されていない。
