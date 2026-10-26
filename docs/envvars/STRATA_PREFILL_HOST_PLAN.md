# `STRATA_PREFILL_HOST_PLAN`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。

## 役割

自動 prompt chunk (`--prefill auto`) の候補を、GPU cache の収まりだけでなく、expert の RAM copy、OS page cache、モデルファイルを読む drive、host-to-device 転送も含めた予測時間で再評価します。予測上、十分な改善があるときは prompt chunk と ring slot 数を選び直します。重みや expert の配置自体はこの変数では変更しません。

値は `host_plan_chunk()` が呼ばれるたびに `std::getenv()` で読みます。静的キャッシュはありません。

## 値と判定

実装は文字列全体や数値を parse せず、先頭文字だけを判定します。

| 値 | この planner の扱い |
|---|---|
| 未設定 | 有効（既定） |
| 空文字 | 有効（先頭文字は `\0` で `'0'` ではない） |
| 先頭文字が `0`（例: `0`, `0abc`） | 無効 |
| その他すべて（例: `1`, `false`, `off`, 空白始まり） | 有効 |

これは要求値の判定であり、実際に計画が行われるには下記の実行条件も必要です。根拠: `src/program/generate.cpp:7770-7779`。

## 有効になる条件

値判定が有効でも、planner は以下の場合に元の chunk をそのまま返します。

- `--prefill auto` ではない、または候補 chunk が 0 以下。
- GGUF の in-place source 経路ではない（`srcp != &src`）。
- `Prefill::ring_bytes_enabled()` が false。
- GPU cache が全 expert を保持し、file tier がない。
- host memory の測定値を取得できない。

通常の prompt 経路では、`--prefill auto` かつバッチ対象 prompt が 1024 token を超える場合に、この planner を呼びます。複数 GPU の prompt 経路にも呼び出しがあり、自動 chunk と ring の候補を再評価します（`src/program/generate.cpp:8612-8637,15775-15795`）。

文書 `docs/DETAILS.md` はこの機能を Linux の file-tier planner として説明し、Windows では何もしないとしています。ソース上の変数判定自体に OS 分岐はありませんが、Windows の実利用範囲については同文書の説明に従います（`docs/DETAILS.md:281-286`）。

## 実行時の詳細

planner は expert 総量、GPU cache、RAM copy と貸出 slot に残る copy、PLE の追加 file set を計算します。host memory 測定が取れた場合、buffered source の page-cache 容量は `MemAvailable` 等の測定値から約 1.17 GiB の slack を引き、unbuffered source では 0 とします。PCIe 速度は直近の H2D 測定値（なければ 12 GB/s）、drive 速度は `drive_read_gbps()` の見積もりを使います。候補の prompt 長は呼び出し側の hint があればそれを使い、なければ chunk と `--max-context` をもとに 4096〜32768 token の範囲で見積もります (`src/program/generate.cpp:7780-7805`)。

候補は現行選択と、同じか小さい chunk に対する複数 ring サイズです。`prefill_plan::choose()` は予測時間が最小の候補を選びますが、現行選択より予測時間を少なくとも 5% かつ 2 秒改善しなければ現行 chunk/ring を維持します。計算では RAM に残らない貸出 expert、page cache に対する file set、chunk 数、H2D と drive の速度、ring 縮小の penalty を使います（`include/strata/program/prefill_plan.hpp:81-127`）。

結果は stderr に `strata: prefill plan: ...` として出ます。変更時は chunk と ring の変更、予測 read 量・時間を、変更なしの場合は選択を維持した旨を表示します（`src/program/generate.cpp:7842-7856`, `include/strata/program/prefill_plan.hpp:151-173`）。通常経路では、選ばれた小さい chunk は prompt が元の VRAM 選択 chunk より長い場合に適用されます。元の buffer chunk を維持し、別の `pf_plan_chunk` として保存します（`src/program/generate.cpp:8639-8642,13375`）。

関連設定では、固定値の `--prefill N` は planner 対象外です。`STRATA_PREFILL_RING` が指定されている場合も ring の予算設定・適合判定に影響します。`STRATA_SSD_GBPS` は `std::atof(e) > 0` のとき drive 速度推定を上書きします。`STRATA_PREFILL_PLAN_TOKS` も同じ判定で prompt compute 速度の見積もりを上書きします。いずれも文字列全体の数値検証ではなく、`atof` が変換した値が正かを見ます（`src/program/generate.cpp:7791-7793,1387-1403`）。

## 根拠

- `src/program/generate.cpp:7755-7789` — planner の目的、環境変数判定、適用条件、host 値の取得。
- `src/program/generate.cpp:7790-7856` — tier/candidate の設定、選択、ログと ring の反映。
- `src/program/generate.cpp:8612-8642,13375,15775-15903` — 呼び出し箇所と選択 chunk の利用。
- `include/strata/program/prefill_plan.hpp:81-127,151-173` — 見積もり、改善閾値、ログ内容。
- `src/core/conversation_memory.cpp:280-291` — OS 別の host memory sampling（Windows/Linux/その他）。
- `docs/DETAILS.md:281-286`; `docs/release-notes-0.2.0.md:61` — Linux file-tier planner の説明、Windows の適用外、無効化方法と測定例。release note の性能値は記載された RTX 3060 / SATA SSD 模擬 / cgroup RAM・450 MB/s 制限の条件での報告であり、この調査で再測定した値ではありません。
