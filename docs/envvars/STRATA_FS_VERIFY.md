# `STRATA_FS_VERIFY`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは調査開始時に clean。外部ライブラリと GPU driver の動作は対象外。

## 役割

CUDA の Foresight swap space がコピーした expert のデータを、GPU 上の slot から host へ読み戻し、元の host データと比較する検証用スイッチです。データの不一致または読み戻し失敗を検出した slot は提供対象から外し、そのリクエストでは通常の CPU 側 miss 経路へ戻します。検証は遅い test mode として実装されています。

この変数が使われるのは `strata serve` の Foresight swap space が作られた場合だけです。swap space 自体は `STRATA_FS_SLOTS` が正の slot 数を要求した場合に限り有効化を試みます。

## 値と判定

値は `foresight_swap_from_env()` 内の共通 `env_int` lambda で `std::getenv()` と `std::atoi()` を使って読み、`!= 0` を `verify` に設定します。既定値は `0`、下限引数も `0` なので、clamp による値の変更はありません。

| 環境値 | 判定 |
|---|---|
| 未設定 | `atoi` の代わりに既定値 `0` を使い、無効 |
| 空文字 | `atoi("")` 相当で `0`、無効 |
| 変換結果が `0` | 無効。例: `0`, `-0`, 数字で始まらない文字列 |
| 変換結果が非 `0` | 有効。例: `1`, `-1`, `2`, `1tail`, `  +1tail` |

`atoi` のため文字列全体の厳密な整数検証は行わず、先頭の空白と符号の後にある10進数字列を変換し、数字列以降は判定に使いません。したがって `0tail` は無効、`1tail` は有効です。負の非ゼロ値も有効で、範囲制限・無効文字列の警告・fallback のログはありません。`atoi` で `int` の範囲を超える入力の扱いは、この実装では検証も定義もしていません。

## 有効になる条件

次の条件を満たして Foresight swap space が初期化された場合にだけ、このフラグが実動作に使われます。

- `STRATA_FS_SLOTS` が設定され、`atoi` の結果が正である。未設定・空文字・非数値・0・負数では `foresight_swap_from_env()` が直ちに `nullptr` を返すため、`STRATA_FS_VERIFY` は読まれません。
- `STRATA_VERIFY_DEVICE_PLAN` が未設定、空文字、または `atoi` の結果が0である。非ゼロなら swap space を無効にして stderr に理由を出し、`STRATA_FS_VERIFY` の読み取り前に戻ります。
- swap space の初期化が成功する。確保・CUDA event 作成に失敗した場合は swap space が無効になり、`STRATA_FS_VERIFY` の値による検証は実行されません。

要求 slot 数は最大64に制限されます。これは `STRATA_FS_VERIFY` の値判定には影響しません。Foresight swap space の生成コードは `src/program/generate.cpp` の serve 経路にあり、通常の独立 CLI 引数でこの検証フラグを上書きする処理はありません。値は pool の生成時に一度読み、`ForesightSwap::verify` フィールドに保存されます。pool が存続する間にプロセス環境を変更しても再読込されません。別の pool を生成する場合はその生成時の環境値で判定されます。

## 実行時の詳細

Expert plan 作成時、cache にない expert について `ForesightSwap::take()` が成功すると、その slot の device address を GPU group に渡します。まだコピー中、または CUDA event が未完了なら `take()` は false を返して通常の miss 処理へ進みます。コピーが完了した slot を初めて提供しようとする際、`take()` は device から `sl.bytes` 全体を同期 `cudaMemcpy` で host vector に読み戻し、元データ `sl.src` と `memcmp` します。

- 一致時は `verify_ok` を増やし、slot を通常どおり GPU に提供します。
- 読み戻しに失敗するかデータが一致しない場合は `verify_bad` を増やし、slot を `ready=false` にして expert と slot の対応を解除して `take()` は false を返します。呼び出し元はその expert を Foresight hit として GPU に渡さず、CPU miss 経路へ進みます。明示的な mismatch 警告やプロセス終了はこの分岐にはありません。CUDA error state は `cudaGetLastError()` でクリアされます。
- その後の pool report には `verified <ok> ok / <bad> BAD` が加わります。report は decode 処理の serve 側ログに `strata serve:` 接頭辞付きで出力されます。

## ログと失敗経路

初期化に成功した場合、stderr に slot 数・card 数・コピー budget 等の通常の Foresight 設定ログが出ます。`STRATA_FS_VERIFY` が有効かどうかを個別に告げる起動ログはありません。検証結果は後の report にカウンタとして現れます。デバイス計画との併用時には `strata serve: foresight swap: off beside STRATA_VERIFY_DEVICE_PLAN (the device would plan resident layers without the host)`、初期化失敗時には `strata serve: foresight swap: <reason> - swap space off` が出ます。これらは pool の適用条件に関するログです。

## 根拠

- `src/core/expert_source.cpp:6537-6557` — `STRATA_FS_SLOTS` による早期 return、`STRATA_VERIFY_DEVICE_PLAN` の排他判定、`env_int` の `getenv` / `atoi` / 下限 clamp、対象変数の既定値と `verify` への代入、初期化失敗時のログ。
- `include/strata/core/foresight_swap.hpp:2-21,63-66,76-84` — Foresight swap space が `STRATA_FS_SLOTS` により opt-in であること、検証用フラグと slot / prediction 機能の宣言。
- `src/program/generate.cpp:11108-11129` — serve 経路で pool を生成し、drive・look-ahead・expert source に接続する処理。
- `src/core/expert_source.cpp:6404-6438` — landed slot の確認、readback と byte 比較、カウンタ更新、不一致時の slot 無効化、正常時に GPU address を返す処理。
- `src/core/expert_source.cpp:4983-5005` — `take()` が失敗した expert を miss として処理し、必要なら CPU 側 staging に回す呼び出し元。
- `src/core/expert_source.cpp:6524-6534` と `src/program/generate.cpp:17177` — 検証結果カウンタを含む report 文字列と serve stderr への出力。
- `src/core/expert_source.cpp:6325-6356,6392-6400` — CUDA device 上の slot 確保、CUDA stream 上の expert copy と event 記録、初期化条件。
- `docs/DETAILS.md:1030,1437` — Foresight swap の slot 設定と記載済み測定。`STRATA_FS_VERIFY` 固有の意味・測定値の記載はなく、本書の挙動説明は上記実装に基づく。
