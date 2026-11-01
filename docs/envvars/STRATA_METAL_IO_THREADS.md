# `STRATA_METAL_IO_THREADS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

macOS Metal backend の SSD expert stream が使う I/O worker thread 数を設定します。値は `ExpertStream` の `nio_` に保存され、arena 初期化時にその数だけ worker を起動します。モデル全体を Metal buffer に載せる通常経路では `ExpertStream` を開かないため、この変数は使われません。

## 値と判定

内部 helper `env_int()` は変数が未設定または空文字なら既定値を返し、それ以外は `std::atoi()` で変換します。読み取り結果に `std::max(1, ...)` を適用するため、実効 thread 数は最低1です。上限 clamp はありません。

| 環境変数の状態・値 | 実効値 |
|---|---:|
| 未設定 | 6 |
| 空文字 | 6 |
| 整数文字列（例: `4`） | その整数。ただし1未満は1 |
| 数字で始まる文字列（例: `4workers`, `4.5`） | `atoi` が先頭の整数部分として読む値。ただし1未満は1 |
| 数字に変換できない文字列（例: `threads`） | `atoi` の0となり、1 |
| `0`、負数 | 1 |

`atoi` のため、文字列全体の妥当性検査やエラー通知はありません。表は `atoi` の変換範囲内の値についての説明です。範囲外の整数文字列の変換結果は C/C++ の `atoi` の仕様上保証されません。

## 有効になる条件

- `metal/CMakeLists.txt` は Apple 以外では Metal build を拒否します。
- `Window::init()` は `ExpertStream::wanted()` の結果が true の場合にだけ `ExpertStream` を作り、`open()` を呼びます。`wanted()` は `STRATA_METAL_STREAM=1` なら有効、`=0` なら無効にし、それ以外（未設定を含む）ではモデルの mapped weights と追加領域が GPU working set の footprint cap に収まるかで決めます。したがって、この変数だけでは streaming を有効化しません。
- 専用 CLI 引数や他の環境変数による `STRATA_METAL_IO_THREADS` の上書きは確認できません。`STRATA_METAL_READ_SPLIT` は別に読み取られ、worker 数の優先順位を変えず、各 expert read を分割する数を設定します。

## 実行時の詳細

値は streaming が選ばれた `Window::init()` 中、`ExpertStream::open()` で一度読み取られて `nio_` に保存されます。その後 arena を作る `make_arena()` で `nio_` 個の `std::thread` を生成します。worker は expert の read job を queue から取り出して読み込み、読み込み完了を待つ decode/prompt 側へ通知します。プロセス中に環境変数を変更しても、すでに設定済みの `nio_` や起動済み worker 数は変わりません。

この変数自体についての警告・エラー出力はありません。arena 作成時の stderr の統計行に実際の I/O thread 数が含まれます（`...; N I/O threads, read-ahead top ...`）。expert のファイル読み込みに失敗した場合は `strata metal stream: reading expert ... failed` を stderr に出して exit code 6 で終了します。この失敗経路は設定値を検証するものではありません。

## 根拠

- `metal/src/engine/stream.cpp:27-30` — `env_int()` の未設定・空文字 fallback と `atoi` 変換。
- `metal/src/engine/stream.cpp:149-150` — `STRATA_METAL_IO_THREADS` の既定値6、最低値1、および隣接する独立設定 `STRATA_METAL_READ_SPLIT`。
- `metal/src/engine/window.cpp:541-548` — `ExpertStream::wanted()` が true の場合だけ streaming 用 `ExpertStream::open()` を呼ぶ。
- `metal/src/engine/stream.cpp:33-48` — `STRATA_METAL_STREAM` と footprint 判定による streaming の選択。
- `metal/src/engine/window.cpp:1512-1514`, `metal/src/engine/stream.cpp:481` — arena 初期化から `nio_` 個の worker を起動する経路。
- `metal/src/engine/stream.cpp:272-274,307-332,541-544` — I/O worker の役割、読み込み完了通知、thread 数を含む stderr 統計行。
- `metal/src/engine/stream.cpp:275-303` — expert read が失敗した場合の stderr と exit code 6。
- `metal/CMakeLists.txt:14-17` — Metal build が Apple 専用であること。
