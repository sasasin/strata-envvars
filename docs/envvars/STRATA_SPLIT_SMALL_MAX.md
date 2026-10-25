# `STRATA_SPLIT_SMALL_MAX`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

レイヤー分割で複数 GPU を使う serve 経路において、`STRATA_SPLIT_SMALL_OWN` が確保する小さい prompt chunk `S` を使う対象リクエストの上限 `M`（tokens）を指定します。prompt segment が `M` 以下なら、その segment を通常の大きな prefill chunk で一度に貸し出す代わりに、最大 `S` tokens の chunk として各 stage の prefill path に配置します。`STRATA_SPLIT_SMALL_OWN` が無効なら、この変数だけでは何も変わりません。

## 値と判定

この値を読むのは `multi_gpu && !pf_parts.empty() && !host_res.empty()` の場合だけです。C++ の `std::atoll` で整数へ変換し、文字列全体の妥当性検査やエラー報告はしません。実効上限は `S > 0` のとき `max(S, atoll(M))` です。

| `STRATA_SPLIT_SMALL_MAX` | 実効上限 |
|---|---:|
| 未設定 | `S` |
| 空文字、数値に変換できない文字列、0、負数、`S` 未満の正数 | `S`（`atoll` の結果と `S` の大きい方） |
| `S` より大きい整数 | その整数 |

先頭に空白や符号を含む数値は `atoll` の変換規則に従います。数値の後ろに文字が続く場合、数値部分が変換されます（例: `2048tokens` は 2048）。`M` 自体に上限 clamp はありません。`S <= 0` の場合は実効上限を 0 とし、小 chunk 分岐そのものを無効にします。

`S` は同じ箇所で `STRATA_SPLIT_SMALL_OWN` を `atoll` で変換し、`request_chunk(value, o.prefill_chunk)` に通して決まります。入力が 0 以下なら 0、正数なら 256-token 単位で切り上げた値を `--prefill` の chunk 上限で制限します。したがって `M` が設定されていても `STRATA_SPLIT_SMALL_OWN` が未設定・空・非正数なら有効になりません。

## 有効になる条件

- serve の複数 GPU レイヤー分割で、stage ごとの `pf_parts` と host residency table が存在すること。
- `STRATA_SPLIT_SMALL_OWN` から求めた `S` が正であること。
- 対象 segment が `windows_ok()` による既存 window の再利用経路ではなく、通常の batched prompt 読み込みとして `lend()` を通ること。

単一 GPU、stage のない経路、host residency table のない経路では読み取り・適用されません。上限判定の対象は全会話の総 token 数そのものではなく、prompt の cut ごとに `lend(to - at)` へ渡される segment token 数です。既存 prompt window を読む場合は `refill()` 側へ進み、この変数による chunk 選択は行いません。

## 実行時の詳細

変数は serve engine の初期化中、stage 用 prompt path と expert cache の準備後に通常の `getenv` で読みます。値はこのリクエスト処理のローカル変数に保持されます。リクエストごとに環境を読み直す実装ではありません。

`lend()` はまず `equal_chunk(tokens, o.prefill_chunk)` で通常の希望 chunk を求めます。`tokens <= 実効上限` かつ `S > 0` なら、その値を `min(通常 chunk, S)` に縮めます。これにより最大 `M` tokens の segment は `S` 以下の stage chunk で複数回に分けて処理され、`M` を超える segment は通常 chunk のままです。`M` 未設定時の上限は `S` なので、S-token 以下の segment が対象です。

`S` が有効なとき、初期化時に各借用 stage の cache tail のうち S-token chunk 用 buffer と重なる expert slot を residency table 上で non-resident にします。そのため、短い segment で使う buffer 領域にその stage の expert を resident として残さず、対象 segment は S-token chunk の領域で処理されます。実際に各 request で slot を貸す範囲は `part_slots()` と `host_res` の状態から決まり、`STRATA_SPLIT_SMALL_MAX` はその範囲を直接指定しません。

この変数自身の専用ログはありません。S-token 領域確保時には `CUDA%d keeps ... slots for ...-token prompts (... experts no longer resident)` が stderr に出ます。`STRATA_TRACE` が有効で slot loan がある場合は、通常の trace として `lent ... slots for ... tokens` も出ます。失敗時は prompt lending / prefill の既存エラー経路を通ります。

## 根拠

- `src/program/generate.cpp:7389-7424`: `STRATA_SPLIT_SMALL_OWN` と `STRATA_SPLIT_SMALL_MAX` の読み取り、変換、実効上限、および S-token 領域確保。`sycl/src/program/generate.cpp:6962-6999` に対応実装があります。
- `src/program/generate.cpp:6326-6332`: `request_chunk()` の 256-token 切り上げ、上限、非正数処理。SYCL 版の同 helper は `sycl/src/program/generate.cpp:5980-5995`。
- `src/program/generate.cpp:10895-10906,10945-10955`: `lend()` が segment token 数から実際の chunk を選び、stage ごとに領域を relayout して slot を扱う処理。対応する SYCL 版は `sycl/src/program/generate.cpp:10141-10168,10173-10184`。
- `src/program/generate.cpp:11185-11205`: prompt cut ごとの segment 長を `lend(to - at)` に渡す経路。対応する SYCL 版は `sycl/src/program/generate.cpp:10358-10377`。
- `docs/MULTI_GPU.md:76-83`: split 時の短い prompt と `STRATA_SPLIT_OWN` の説明。`STRATA_SPLIT_SMALL_MAX` の値判定や上限についてはこの文書に説明がなく、上記の現行コードを根拠にしました。
