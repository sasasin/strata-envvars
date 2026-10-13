# `STRATA_FS_VERIFY`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Foresight swap が VRAM にコピーした expert の内容を、利用前にホスト側の元データと照合する診断用スイッチです。通常の expert cache の検証ではなく、`STRATA_FS_SLOTS` で有効化する Foresight swap のスロットだけが対象です。値が有効なとき、コピー完了後にスロットを初めて利用しようとする時点でデバイスからホストへ内容を読み戻し、元データと全 byte を比較します。

## 値と判定

Foresight swap の初期化関数内にある共通整数 helper が、`std::getenv()` の結果を `std::atoi()` で変換し、下限 0 を適用します。全体一致の文字列比較ではありません。

| 値 | 判定結果 |
|---|---|
| 未設定 | 既定値 0。検証しない |
| 空文字 | `atoi` の結果 0。検証しない |
| 数字で始まらない文字列 | `atoi` の結果 0。検証しない |
| 先頭の空白・符号の後に正の十進整数がある | 変換値が正なら検証する。例: `  +2tail` は 2 として扱う |
| `1tail` や `2` | 変換値が正なので検証する。後続文字列は判定に使わない |
| `0`, `0tail`, `-1`, `-0` | 変換値が 0 以下なので下限 0 となり、検証しない |
| 小数表記 `0.5` | `atoi` が整数部の 0 を読むため検証しない |

正の値の大きさによる段階的な動作差はありません。実装は変換結果が 0 以外かを `bool` にします。範囲外の数値文字列に対する明示的な検査やエラー処理はありません。

根拠: `src/core/expert_source.cpp:4961-4966`。

## 有効になる条件

- `STRATA_FS_SLOTS` が `atoi` で正の値になり、Foresight swap の作成が試みられること。未設定、空文字、数値でない値、0 以下なら初期化関数は swap 自体を作らず、`STRATA_FS_VERIFY` も読みません。
- `STRATA_VERIFY_DEVICE_PLAN` が設定されていないか、`atoi` の結果が 0 であること。非ゼロなら swap の作成は拒否され、stderr に `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)` と出ます。
- swap の初期化が成功すること。初期化失敗時は stderr に `strata serve: foresight swap: <理由> - swap space off` と出して swap を破棄します。

この実装は CUDA runtime API を使う `src/core/expert_source.cpp` にあります。確認した Foresight swap の初期化・検証経路について、HIP/SYCL 等の別実装は見つかりませんでした。

## 実行時の詳細

`foresight_swap_from_env()` が呼ばれたとき、`STRATA_FS_SLOTS` と他の swap 設定を読み、swap 作成時に一度 `verify` に保存します（`src/program/generate.cpp:8182-8193`）。`STRATA_FS_VERIFY` は static cache ではありませんが、作成済み swap に対してリクエストごとやスロットごとに環境を読み直す処理もありません。

コピー担当 thread は slot の VRAM への非同期コピーを発行します。利用側の `take()` はコピー完了を確認した後、その slot がまだ ready でない場合に限って検証します。検証では同じサイズの一時 host buffer を確保し、`cudaMemcpy` で VRAM から読み戻した byte 列を `sl.src` と `memcmp` で比較します。

一致すれば `verify_ok` を増やして slot を ready にし、その後の利用では同じ resident slot を再比較しません。相違または読み戻し失敗なら `verify_bad` を増やし、slot を ready に戻さず、expert と slot の対応を解除して `take()` は false を返します。その slot の不一致データを GPU に渡さない動作です。呼び出し側は false の場合に miss を記録し、通常の処理へ進みます（`src/core/expert_source.cpp:3740-3744`）。

swap のレポート出力が有効なときは、`STRATA_FS_VERIFY` が有効なら `verified <成功数> ok / <不一致数> BAD` が追加されます。これは swap の利用統計とともに stderr に出力されます（`src/program/generate.cpp:12055`）。

## 文書との照合

`docs/DETAILS.md:1680-1685` は `STRATA_FS_VERIFY=1` で landed slot を読み戻して比較すると説明し、RTX 5070 で 2,300 回超の読み取りに 0 bad と記載しています。現行ソースでは `=1` に限定されず、`atoi` 結果が正の任意の整数で有効です。また比較はコピー直後ではなく、コピー完了後の初回利用時に行われます。測定値は同資料の記載として引用し、この調査で再測定したものではありません。

## 根拠

- `src/core/expert_source.cpp:4951-4976` — swap 初期化、`STRATA_FS_VERIFY` の整数読み取り、既定値・下限、診断ログ。
- `src/core/expert_source.cpp:4813-4836` — copy thread が VRAM コピーと完了 event を発行。
- `src/core/expert_source.cpp:4839-4874` — 初回利用時の readback 比較、一致・不一致時の処理。
- `src/core/expert_source.cpp:3740-3744` — Foresight slot miss 後の呼び出し側処理。
- `src/core/expert_source.cpp:4939-4948` — 成功・不一致数を含む report。
- `src/program/generate.cpp:8182-8193,12055` — swap 作成とレポート出力。
- `include/strata/core/foresight_swap.hpp:2-21,63-66` — 機能概要と verify 状態。
- `docs/DETAILS.md:1680-1685` — 文書上の動作説明と RTX 5070 の測定記載。
