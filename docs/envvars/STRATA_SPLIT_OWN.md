# `STRATA_SPLIT_OWN`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。対象は Strata 所有の CUDA/HIP 系および SYCL 実装。外部ライブラリ・GPU ドライバー自身の環境変数動作は対象外。

## 役割

複数 GPU の layer split で、各 stage の prompt path が expert cache の末尾を借りて一時バッファとして使う既定動作を、各 GPU に専用の prompt buffer を確保する動作へ切り替えます。専用バッファはセッション中 VRAM を予約しますが、prompt 中に cache から expert を借りて prompt 後に戻す運用を避けます。どの expert が各 GPU の cache に残るかも変わり得るため、既定動作と出力が異なる場合があります。

## 値と判定

実装は文字列全体を一般的な boolean として parse しません。最初に未設定かどうかと先頭文字を見て、その後、文字列全体が小文字の `auto` と一致するかを確認します。

| 値 | 判定と動作 |
|---|---|
| 未設定 | 環境変数による変更なし。通常は各 stage が cache の領域を借りる。 |
| 空文字 | 設定済みだが先頭文字が `1` ではないため専用 buffer を選ばない。 |
| `0` で始まる値（例: `0`, `0abc`） | 外側の条件で無視され、借用動作を保つ。 |
| `1` で始まる値（例: `1`, `10`, `1abc`） | 各 GPU の専用 buffer を選ぶ。文字列全体の検証はしない。 |
| 正確に `auto` | 各 GPU で見積もった buffer 予約量が VRAM の 12% 以下の場合だけ専用 buffer を選ぶ。 |
| その他（例: `true`, `2`, `auto `, `AUTO`, `-1`） | 有効な選択肢ではなく、専用 buffer を選ばない。 |

`auto` の見積もり対象 chunk は、`--prefill auto` または chunk 指定なし・0以下なら 2048 token、それ以外は `--prefill` の指定値です。判定用予約量は `160 + (chunk × 680) / 1024 + 96 × 4` MiB。CUDA 実装は CUDA0 と split の各 GPU、SYCL 実装は device 0 と各 split device を調べ、いずれかの予約量が総 VRAM の 12% を超えると借用動作にします。device 情報の取得に失敗した場合も専用 buffer を選びません。

## 有効になる条件

- `--layer-split` により実際に複数 GPU を使うこと。単一 GPU 経路ではこの環境変数を読むブロックに入りません。
- layer split では `--expert-profile` が必要です。profile がない場合は先にエラー終了します。
- `--no-prefill-borrow` が既に指定されていないこと。指定済みなら環境変数の分岐はスキップされます。
- `--split-skip-if-fits` が指定されていないこと。同オプションが split を省略する経路と競合しないよう、環境変数の分岐はスキップされます。

`STRATA_SPLIT_OWN=1` は `auto` の 12% 制限を適用せず、上記条件を満たせば専用 buffer を選びます。`auto` で容量条件を満たさない場合は借用動作のままです。`STRATA_SPLIT_OWN=auto` が有効になった場合、または `=1` が有効になった場合、`--layer-split auto` の配置検索では専用 buffer の予約を一旦見込まずに stage の境界を検索します。関連変数 `STRATA_SPLIT_OWN_PLACE=reserve` を設定すると、その検索で予約を見込みます（これは別環境変数の独立した判定です）。

## 実行時の詳細

環境変数は split の stage 構築前に読みます。専用 buffer を選ぶと `o.no_prefill_borrow` を有効にし、後段の prompt 経路は各 cache から buffer を借りる処理を行いません。`--prefill auto` はこの状態では 2048-token chunk に固定されます。layer split の VRAM 配置見積もりには、chunk buffer と streamed expert ring の予約が反映されます。

選択時の stderr ログは次の形式です。末尾の `(STRATA_SPLIT_OWN=1)` は `auto` 以外の選択時に付くため、`auto` 成功時には付きません。

```text
strata generate: layer split: every stage keeps its own prompt buffers (~<MiB> MiB each, <token数>-token chunks)[ (STRATA_SPLIT_OWN=1)]
```

`auto` で容量条件に合わないときは `strata generate: layer split: the prompt paths borrow from the caches (<CUDAデバイス情報>)` を出します。device 情報の取得失敗では `why` が空のため、この借用理由ログは出ません。`1` 以外の不正値や `0` はこのブロックで選択されないため、専用 buffer 選択ログも出ません。

## 文書・測定値との照合

`docs/MULTI_GPU.md` は `=1` を opt-in と説明し、R9700 + RX 9070 XT での測定として、既定構成が 2K prompt 1,265 tok/s・16K 1,950 tok/s、`=1` がそれぞれ 1,450 tok/s・2,227 tok/s と記載しています。同資料は、専用 buffer では cache に残る expert が変わるため既定と出力が異なる場合があること、`auto` は buffer が各 GPU の VRAM の最大 12% のときに限ることも説明しています。これらは資料中の特定環境の測定値であり、他の GPU 構成での性能を示すものではありません。

## 根拠

- `src/program/generate.cpp:2407-2408,2419-2423,2452-2485` — CUDA/HIP 系の split 条件、値判定、容量判定、状態変更、ログ。
- `src/program/generate.cpp:2523-2526,3728-3741,3761-3765,3797-3812` — `--prefill auto` の変更、buffer/ring の予約計算、配置検索と `STRATA_SPLIT_OWN_PLACE` の相互作用。
- `src/program/generate.cpp:7293-7302,13166-13184` — split stage ごとの cache 借用と非借用時の prompt 経路。
- `sycl/src/program/generate.cpp:2100-2101,2121-2185,2245-2268,3504-3565` — SYCL 実装の同等の値判定・効果・配置検索。
- `docs/MULTI_GPU.md:76-83` — 利用者向け説明と上記測定値。
