# `STRATA_METAL_ARENA_STEP_GB`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の expert streaming 経路で、起動時に expert arena を埋める際の「一回に読み込んで空きメモリを再確認する単位」を指定します。arena の総容量や各 expert の優先順位を直接決める変数ではありません。空きメモリが厳しい場合、確認の単位が小さいほど arena の充填を細かく止められます。

対象コードは `metal/src/engine/stream.cpp` の `ExpertStream::make_arena()` です。Metal 以外の CUDA/HIP/SYCL 経路ではこの名前を読む箇所を確認できません。

## 値と判定

| 環境変数 | `step` の値 |
|---|---|
| 未設定 | `1536 MiB`（`1536 * 2^20` bytes） |
| 設定あり | `atof(value) * 1,000,000,000` bytes を `uint64_t` に変換し、最低 `64 MiB` にする |

`std::atof` を使い、文字列全体の検証やエラー判定はしません。したがって、先頭から数値として読める部分が使われ、数値以降の文字は無視されます。空文字や数値として読めない文字列は `atof` が `0` を返すため、`step` は `64 MiB` になります。たとえば `1.5` は 1,500,000,000 bytes（十進単位）、`0.01` は下限の 64 MiB です。大文字小文字や真偽値文字列の判定はありません。

負数や、`uint64_t` の範囲に収まらない値については、`atof` の結果を整数へ変換するコードに安全な範囲検査がありません。その場合の値をこの実装から確定できないため、文書化された利用値として扱えません。

## 有効になる条件

- Metal backend が使われ、GGUF の routed experts を SSD から読む `ExpertStream` の arena 初期化に進むこと。
- 通常利用では、モデルの expert 群が Metal の利用可能メモリに収まらず、expert streaming が選ばれる経路が該当します。`window.cpp` は arena 予算と空きメモリ確認 callback を用意して `make_arena()` を呼びます。
- 値が設定されても、メモリに余裕があれば充填完了まで進むので、値の差が最終 arena のサイズや実行結果に現れるとは限りません。

## 実行時の詳細

変数は `make_arena()` 内で arena の初期レイアウト作成後、expert の初期読み込みを始める前に読み取られます。静的キャッシュはありません。初期化時に空きメモリが減って arena を縮小して再試行する経路では、`make_arena()` が再度呼ばれ、その試行時の値を読みます。通常の生成中に毎回読む変数ではありません。

`fill` は profile 順（profile にない expert は layer 順）に積まれます。各バッチでは、次の expert を少なくとも1つ含め、合計バイト数 `sb` が `step` 以上になるまで expert を追加します。そのバッチの前に `grow(sb)` で空きメモリを再確認します。許可されなければ残りの slot を未使用のままにして充填を止め、stderr に `strata metal stream: the arena's fill stopped after ...` と未使用容量を記録します。個々の expert は分割されないため、1 expert 分だけ `step` を超える場合があります。

## 根拠

- `metal/src/engine/stream.cpp:368-370` — arena の初期化関数。
- `metal/src/engine/stream.cpp:417-427` — arena の総容量・Metal buffer の chunk 計算。`STRATA_METAL_ARENA_STEP_GB` とは別の `STRATA_METAL_ARENA_CHUNK_GB` が chunk 容量を指定する。
- `metal/src/engine/stream.cpp:478-512` — 既定値、環境値変換、step 単位での expert 充填、空きメモリ callback。
- `metal/src/engine/stream.cpp:513-541` — 充填停止時の stderr ログと実際に使う arena 容量。
- `metal/src/engine/window.cpp:1167-1207` — arena 予算の計算と空きメモリ再確認 callback を渡して `make_arena()` を呼ぶ箇所。
- `docs/MAC.md:30-33` — expert streaming、空きメモリの再確認、既定の 1.5 GB step に関する説明。コード上の未設定値は正確には 1536 MiB。
