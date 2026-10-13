# `STRATA_LAYER_SPLIT_PROBE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

自動レイヤー分割 (`--layer-split auto`) の配置後に行う、512-token prompt chunk の起動可能性を確認する第2段階の診断を有効・無効にします。これは事前確認とログの切り替えであり、無効にしても自動配置そのものや serve の起動時チェックは無効になりません。

## 値と判定

| 環境変数の状態 | 判定 |
| --- | --- |
| 未設定 | 有効 |
| 空文字 | 有効 |
| 先頭文字が `0` | 無効（例: `0`, `0abc`） |
| それ以外 | 有効（例: `1`, `false`, `abc`） |

実装は文字列を数値や真偽値に parse せず、`v[0] != '0'` だけで判定します。したがって `false` は無効値ではなく有効です。値は関数内 `static const` の初期化時に一度読み取られ、そのプロセス中は環境を変更しても再評価されません。

## 有効になる条件

- 複数 GPU の `--layer-split auto` がまだ有効で、分割境界 `split_at` が確定している場合に限り実行します。明示的な `--layer-split K,...`、可視 GPU が1台で自動分割が取り消された場合、または `--split-skip-if-fits` により分割が取り消された場合はこの probe に入りません。
- probe は `src/program/generate.cpp` の実装にあります。同じ名前の読み取りは Strata の SYCL generate 実装、server/setup、同梱ツールでは見つかりませんでした。
- 起動可能性は「各参加 GPU が512-token分の prompt バッファを expert cache から借りられるか、借りられない場合はバッファ分と512 MiB headroomを空き VRAM に確保できるか」で判定します。
- cache から借りられるかの判定に使う `STRATA_PREFILL_LEND_PCT` は、この probe 内でも読み取られます。未設定なら `Prefill::pinned_share()` が0.9以上の場合90、それ以外は85です。設定時は `atoi` の結果を使い、空文字や数値で始まらない値は0、数値の後ろの文字は無視され、負値も clamp されません。

## 実行時の詳細

各 GPU について、その時点の空き量を `cudaMemGetInfo` で取得し、`Prefill::bytes_needed(..., 512)` で512-token chunkの必要量を見積もります。cache の枠数を `slots`、枠あたり平均バイト数を `avg` とし、必要枠数を256-byte単位に丸めた必要量から見積もります。枠が1つ以上あり、必要枠が正で、必要枠に128枠の余裕を足しても cache 内に収まり、かつ必要枠の割合が `STRATA_PREFILL_LEND_PCT` 以下なら、その GPU は借用可能として次へ進みます。そうでなければ、必要バッファ量に512 MiBを足した値が空き VRAM 以下かを調べます。どの GPU か1台でも両方の条件を満たさない場合は失敗扱いにします。

成功時は stderr に `strata generate: layer split auto: L2 probe: the split is startable on the live free figures` を出します。失敗時は対象 GPU、必要 MiB、空き MiB、cache枠数、見積もり必要枠数を `L2 probe: CUDA%d cannot start the prompt path...` の行で示し、続けて `to make room:` の案内を出します。この分岐自体は `return` せず、レイヤー分割の起動を止めません。後続の serve 処理には独立した実チェックがあり、借用できないときに指定 chunk が収まらなければ小さい chunk を探して切り替えます（`--prefill` の設定値に応じた処理）。

## 根拠

- `src/program/generate.cpp:2258-2310` — `split_auto` の設定、serve 限定、1 GPU時の取消し、`multi_gpu` 判定。
- `src/program/generate.cpp:3299-3335` — `--split-skip-if-fits` が自動分割を取り消す経路。
- `src/program/generate.cpp:5308-5357` — probe の目的、変数の読み取りと判定、512-token試算、cache借用条件、ログと継続動作。
- `src/prefill/prefill.cpp:1819-1821,1830-1884` — `bytes_needed` が prompt buffer の必要量を数え、8 MiB alignment slack を加える実装。
- `src/program/generate.cpp:7218-7258` — 後続の serve 側で実際の prompt chunk に対して own-buffer 空き容量を確認し、必要なら chunk を小さくする処理。
- `docs/MULTI_GPU.md:180-187` — `auto` の配置選択と起動ログの説明。`STRATA_LAYER_SPLIT_PROBE` 自体の説明は同文書および `docs/DETAILS.md` では確認できませんでした。
