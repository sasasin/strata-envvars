# `STRATA_PIPED_CONCURRENT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`--batch-groups` で複数の slot group を layer split の pipeline に流している間、通常は全 slot が待つ prompt read を専用スレッドへ移し、slot group の decode と同時に実行します。対象は Strata の batch prompt read であり、単独の通常 prompt read 全般を並行化する設定ではありません。ソースのコメントはこの機能を experimental / opt-in としています。

## 値と判定

値は `std::atoi()` で整数変換され、その結果が 0 なら無効、0 以外なら有効です。文字列全体の検証はありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、`0`、`false`、数値に変換できない文字列 | 無効（`atoi` が 0 を返す） |
| `1`、`-1`、`2` | 有効 |
| `1abc`、` 1tail` | 有効（`atoi` が先頭の整数部分を変換） |
| `0tail`、`00` | 無効 |

`pr_conc` は `generate.cpp` 内の関数ローカル `static const bool` なので、初回評価後は同じプロセス内で環境を変更しても再評価されません。Verifier の stream 優先度にも同名変数が使われますが、こちらは別の static 判定です。

## 有効になる条件

値が有効でも、次の条件が必要です。

- `--batch` が正数、`--batch-groups` が 1 より大きく、layer split の stage があること（`piped` 経路）。
- prompt に画像が含まれないこと。
- 読み取りスレッド内の確保・解放や CUDA 呼び出し、または単一スレッドで buffer を再利用する expert source との競合がないこと。コードは次の状態を検査し、最初に該当した理由を stderr に出して機能を無効にします。
  - `STRATA_PREFILL_HELP` が `atoi` で非 0
  - `STRATA_SPLIT_MTP_BATCH` が `atoi` で非 0
  - `STRATA_FS_SLOTS` が `atoi` で非 0
  - `--pcie-mode dma`
  - helper cache の利用（`--expert-cache-device1..3` など）
  - source が blob を stage する場合、または GGUF source / arena 以外の expert source

無効条件のログは `strata batch: STRATA_PIPED_CONCURRENT is off beside %s` です。環境変数が無効、pipeline 経路でない、または画像付きの場合に、この機能専用の警告が必ず出るわけではありません。

## 実行時の詳細

有効時、prompt は reader thread で読み、メインスレッドは slot group の pipeline を進めます。各 verifier の doorbell は別スレッドで処理され、read の終了時には thread を join して doorbell の外部処理を解除します。読み取り途中に短い要求が待っている場合、次の chunk で read を止めて slot に譲る経路があります。プロンプトの K/V は main sessions に、slot の K/V は各 slot に保持され、ソース資料は PLE table をロックすると説明しています。VRAM expert slot は read 前に貸し出し、read 後に補充するため、その間 slot windows は該当 expert を CPU で計算します。

CUDA build では `Verifier::make_stream()` もこの変数を `atoi` で判定します。非 0 かつ `STRATA_PIPED_CONCURRENT_PRIO` が未設定または `atoi` で非 0 の場合、window stream を device の最高優先度で作成しようとします。優先度範囲取得または優先度付き stream 作成に失敗した場合はエラーをクリアして通常の non-blocking stream 作成へ進みます。`STRATA_PIPED_CONCURRENT_PRIO=0` はこの優先度変更を止めますが、prompt read の並行化自体は止めません。

HIP では stream の最高優先度化をこの分岐で行いません。Strata の `docs/BATCHING.md` はこの機能を CUDA と HIP 向けとし、SYCL では利用できないと記載しています。

並行読込が実行された場合、stderr に `strata batch: read ... (concurrent, to ...); the slots decoded ...` の形式で読込量、経過時間、読込中の decode 行数・速度、stage ごとの情報を出します。資料の測定例は 2x RTX 5090、Swift 1.5 IQ3_S、split 25、`--batch 6 --batch-groups 2` などの条件で、固定 stream prompt の読込中の stream 速度は無効時 2–3 tok/s、有効時 85–92 tok/s、同じ仕事全体の stream 完了時間は 5–8% 短縮（平均 6.4%）と報告されています。これは `docs/BATCHING.md` に記載された測定であり、他の環境の性能を示すものではありません。

## 根拠

- `src/program/generate.cpp:11092-11100`: pipeline 経路の定義。
- `src/program/generate.cpp:12855-12893`: 主変数の `atoi` 判定、初回 static 評価、抑止条件とログ。
- `src/program/generate.cpp:12967-12977,13015-13054,13058-13115`: doorbell の別スレッド処理、reader thread、終了時の join、完了ログ。
- `src/core/verify.cpp:848-865`: CUDA の window stream 優先度と通常 stream への fallback。
- `include/strata/program/batch_read.hpp:30-53`: concurrent read を無効化する条件と判定順。
- `docs/BATCHING.md:191-225,227-245`: 機能説明、backend、ログ、測定条件と結果。
