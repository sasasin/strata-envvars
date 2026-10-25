# `STRATA_MTP_PREFILL_SYNC`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP drafter がプロンプト中の draft layer 用 K/V を作るフォールバック処理で、旧来の「最大 `max_t_` 行ごとに入力を準備して graph を実行し、その都度 stream を同期する」経路と、入力レコードをまとめて転送し、複数 group の graph を投入してから同期する E-4 経路を選びます。`1` 相当は旧経路、`0` 相当は E-4 経路です。

この変数を読むのは `MtpDrafter::prefill()` です。通常の単一 GPU では先に `Prefill::draft_kv()` が試され、対応できない場合に drafter 自身の `prefill()` へ進みます。MTP が無効ならこの経路は呼ばれません。CUDA サーバーの layer split では、別設定 `STRATA_SPLIT_MTP_BATCH=1` によって prompt-path のバッチ処理が有効になる場合があります。その場合も、バッチ処理が辞退すれば drafter 側の経路へ進みます。

## 値と判定

`std::getenv()` で未設定かどうかを調べ、設定値は `std::atoi()` で整数化して 0 かどうかを判定します。文字列全体の妥当性検査はありません。

| 入力 | 判定 |
|---|---|
| 未設定 | HIP は旧経路。それ以外は E-4 経路 |
| 空文字 | `atoi("") == 0` のため E-4 経路 |
| 数値として 0 になる文字列（例 `0`, `abc`） | E-4 経路 |
| `atoi()` が非 0 を返す文字列（例 `1`, `-1`, `2tail`） | 旧経路 |

先頭空白や符号は `atoi()` の規則で解釈されます。数値の後ろにある文字は変換を止める位置以降、判定に影響しません。値の大きさに応じた範囲制限はありません。

## 有効になる条件

- MTP drafter が有効で、プロンプト処理から `MtpDrafter::prefill()` が呼ばれる必要があります。
- 1 GPU の通常経路では `Prefill::draft_kv()` が先に試されます。たとえば drafter の K/V が hybrid である、ring に対して `STRATA_MTP_BATCH_RING=0` が指定されている、または必要な tensor や embedding の条件を満たさないなどでバッチ処理が辞退すると、drafter 側へ進みます。`STRATA_MTP_BATCH=0` もバッチ処理を辞退させます。これらの辞退条件は `STRATA_MTP_PREFILL_SYNC` 自体の値判定ではありません。
- CUDA の単一 GPU generate 経路でも、バッチ処理が成功すれば `mtp.prefill()` は呼ばれません。layer split は CUDA と SYCL で呼び出し条件が異なり、CUDA では `STRATA_SPLIT_MTP_BATCH` によるバッチ試行、SYCL の該当箇所では `!multi_gpu` 条件があります。
- Metal は `MtpDrafter::prefill()` 冒頭で Metal engine に委譲して戻るため、この環境変数の判定箇所には到達しません。

## 実行時の詳細

環境変数は `prefill()` 内の関数局所 `static const bool` 初期化子で一度だけ読みます。同一プロセスで最初にこの変数へ到達した後の環境変更は再評価されません。HIP ビルドでは未設定時に `true`、それ以外の同関数のビルドでは `false` です。設定があれば、この既定値を `atoi(value) != 0` で置き換えます。

旧経路では `max_t_` 以下の group ごとに入力を host 側 staging buffer に書き、`capture_prefill()` と graph launch を行い、各 group の後で stream を同期します（CUDA: `src/core/mtp.cpp:1458-1477`、SYCL: `sycl/src/core/mtp.cpp:1483` 以降）。E-4 経路では `n` 行分の token / step / position record を一括して device buffer に転送し、各 group に対して record と hidden-state の device copy、graph launch を順に投入します。`sync` 引数が true なら投入後に一度だけ stream / queue を同期します。false なら同期を待たずに戻り、呼び出し側が同じ stream 上で順序を保つ前提です（CUDA: `src/core/mtp.cpp:1400-1456`、SYCL: `sycl/src/core/mtp.cpp:1364-1481`）。

この同期引数は `STRATA_MTP_PREFILL_SYNC` とは独立しています。環境変数が選ぶのは per-group の旧経路か一括転送経路かであり、E-4 経路の末尾で待つかは `sync` 引数によります。

両経路とも、`cell0 + c + T <= first_needed` の group は K/V を今後参照しないとして処理を飛ばします。メモリ確保、転送、graph launch、同期の失敗時は `false` を返し、`err` に `mtp prefill: ...` のエラーを設定します。通常の選択結果を知らせる専用ログはこの判定箇所にはありません。

## 根拠

- 環境変数の parse、ビルド別既定値、一括経路: `src/core/mtp.cpp:1371-1456`、`sycl/src/core/mtp.cpp:1339-1481`。
- 旧経路の group ごとの同期: `src/core/mtp.cpp:1458-1480`、`sycl/src/core/mtp.cpp:1483-1510`。
- CUDA generate の fallback 呼び出し: `src/program/generate.cpp:13214-13225`。CUDA server の prompt path と layer split のバッチ条件: `src/program/generate.cpp:8504-8529`。
- SYCL generate のバッチ試行と fallback: `sycl/src/program/generate.cpp:7818-7826`、`sycl/src/program/generate.cpp:11891-11902`。
- バッチ経路の辞退条件: `src/prefill/prefill.cpp:1381-1424`。
- `docs/DETAILS.md` には `STRATA_MTP_PREFILL_SYNC` または E-4 の説明は見つかりませんでした。`src/core/mtp.cpp:1382-1391` と SYCL 側同範囲には、旧経路に関する測定・障害のメモがありますが、ここではソース内コメントの記録として扱い、独立に再測定した結果とはしていません。
