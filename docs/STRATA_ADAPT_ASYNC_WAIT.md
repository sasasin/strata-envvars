# `STRATA_ADAPT_ASYNC_WAIT`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

`--adapt-async 1` の expert arena 経路で、GPU cache への copy-in 完了を待ってから新しい expert を resident として公開するかを決めます。既定値は待機する設定です。`0` にすると各 tick では完了をポーリングし、未完了ならその tick の処理を戻して後の tick に続けます。

## 値と判定

この変数は、`generate.cpp` 内のローカル helper が `getenv()` の値を `atoi()` に渡して判定します。変数が未設定、または空文字なら helper の既定値 `1` を返します。空白や数値の後ろの文字は `atoi()` の規則で扱われます（例: `" 1x"` は 1、`"x1"` は 0）。完全な文字列一致や範囲検証はありません。

| 値 | 判定 | copy-in 完了の扱い |
|---|---|---|
| 未設定・空文字 | 既定値 1 | job thread と CUDA event を同期して待つ |
| `atoi()` の結果が 0（例: `0`, `false`, `x1`） | 無効 | job thread が idle でなければ戻り、idle 後も CUDA event が未完了ならポーリングを続ける |
| `atoi()` の結果が 0 以外（例: `1`, `-1`, `2`） | 有効 | job thread と CUDA event を同期して待つ |

数値変換は `a_env()` によるもので、読み取り結果が bool に変換されます。したがって `false` という文字列は数値 0 として無効、`true` は数値 0 として無効です。数値として表現できない入力に対する追加のエラー処理や範囲検証はありません。根拠: `src/program/generate.cpp:10390-10398`。

## 有効になる条件

- `--adapt-async 1` が指定され、適応層の `--adapt-every` と `--adapt-swaps` が有効であること。
- Strata が expert arena をデータ源にしていること（`srcp == &arena_src`）。この変数による `a_wait` は arena の場合だけ true になり得ます。resident RAM copy 経路では false です。
- 非同期 tier の初期化条件で routing usage が空でないこと。初期化されなければ `ajob` がなく、この設定は処理に影響しません。
- その実行経路で非同期 tier が無効化されていないこと。実装は `--serve` を必要とし、arena では layer split と `--pipeline-windows 2` を許しません。条件を満たさない場合は stderr に `strata generate: --adapt-async 1 is off (...)` を出して blocking tier に戻します。

根拠: `src/program/generate.cpp:7959-7974, 8192, 10387-10406`。

## 実行時の詳細

変数は非同期 tier のセットアップ時に一度読み取られ、`a_wait` に保存されます。実行中の環境変更を再読するコードはこの経路にありません。

arena では各 expert が既に arena にあるため、round は GPU cache への copy-in のみです。copy-in の enqueue 後、`AState::SwapIn` で `a_ready(drain || a_wait)` を呼びます。`a_wait` が true、または round を drain する場面では job thread を join し、使用中の CUDA event を `cudaEventSynchronize()` します。false の場合は job thread の idle 状態と event をそれぞれ poll し、未完了ならその tick を終了します。すべて完了した後で初めて `host_res` に新しい resident slot を記録し、residency table を upload します。このため false は待ち合わせをなくすのではなく、round を複数 tick にまたがって進めます。

arena の設定値は request 終了時の累積診断行にも表示されます。tier が初期化された場合、ログ形式は ` (arena, copy-in only, batch %zu, wait %d, pick %s %.2f ms/round)` です。根拠: `src/program/generate.cpp:10546-10556, 10661-10677, 15376-15384`。

`docs/DETAILS.md` は `STRATA_ADAPT_ASYNC_WAIT=1` を arena 経路での既定値とし、次 tick に round の copy 完了を待ってから GPU-resident 化する説明をしています。実装と一致します。同資料の RTX 3090 + Ryzen 5 5600X の性能値は同資料とリンク先レポートに記載された測定であり、この調査では再測定していません。根拠: `docs/DETAILS.md:202-209`。

## 根拠

- 値の読み取り、既定値、arena 限定: `src/program/generate.cpp:10387-10398`
- 非同期 tier の利用条件と fallback: `src/program/generate.cpp:7959-7974, 8192, 10399-10406`
- 待機と poll の差、および resident table 更新: `src/program/generate.cpp:10546-10556, 10661-10677`
- request 終了時の診断出力: `src/program/generate.cpp:15376-15384`
- 設計説明と掲載測定: `docs/DETAILS.md:202-209`
