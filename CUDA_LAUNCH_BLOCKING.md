# `CUDA_LAUNCH_BLOCKING`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリや GPU driver 自身がこの変数をどう扱うかは対象外。

## 役割

Strata の `generate` 実行ファイルはこの変数を読み、CUDA の同期 launch 設定が有効かを診断します。有効と判定すると起動時に警告し、サーバーの watchdog が要求停止を報告する際にも原因の補足を加えます。Strata のコードがこの変数を使って検証 window を無効にする処理はありません。

対象コードのコメントによると、検証 window の graph は GPU 上で host が立てる flag を待ちます。host は `cudaGraphLaunch` が戻ってから flag を立てますが、blocking launch では graph の完了まで launch が戻らず、相互待ちになります。コメントは最初の prompt はこの待ちを使わない batched path のため動作し、prompt 後の最初の verify window が止まると説明しています（`src/program/generate.cpp:1243-1245`）。

## 値と判定

HIP ビルドでは値を読みません。CUDA 側では `std::getenv("CUDA_LAUNCH_BLOCKING")` を `std::atoi` に渡し、その結果が 0 以外なら有効と判定します（`src/program/generate.cpp:1246-1252`）。

| 値 | Strata の判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数字で始まらない文字列（例: `true`） | 無効（`atoi` が 0 を返す） |
| `0`、`0anything`、空白の後の `0` | 無効 |
| `1`、`2`、`-1`、先頭の空白や符号の後に非ゼロ数字がある文字列 | 有効 |

文字列全体の妥当性は検査されず、`atoi` が読み取れる先頭の整数部分だけで判定されます。したがって `1tail` は有効、`0tail` は無効です。起動時の警告文は慣例的に `CUDA_LAUNCH_BLOCKING=1` と表示しますが、実装上は値が厳密に `1` かどうかではなく、変換結果が非ゼロかを見ます。

## 有効になる条件

- `STRATA_USE_HIP` または `STRATA_HIP_GFX906` が定義されたビルドでは、環境変数の値に関係なく `launch_blocking()` は `false` を返します。コメントにも HIP 固有のスイッチは確認しないとあります（`src/program/generate.cpp:1243-1252`）。
- それ以外のビルドでは、非ゼロ判定時に警告と watchdog の補足が有効です。ソースはこれらの分岐を CUDA 用コードとして置いています。
- 値が非ゼロでも、Strata 側の警告・診断が変わるだけです。実際に launch を blocking にする設定の解釈は外部 CUDA runtime 側の動作であり、この調査の対象外です。

## 実行時の詳細

`launch_blocking()` は環境値を毎回取得し、static cache はしません。`main` の初期処理中に一度呼ばれ、非ゼロなら stderr に次の警告を出します（`src/program/generate.cpp:1761-1764`）。

```text
warning: CUDA_LAUNCH_BLOCKING=1: the verify windows cannot run with blocking launches, so the first one after a prompt hangs until the watchdog ends the engine (#1341). Unset it; STRATA_PF_STEP_SYNC=1 narrows down a failing prompt step without it
```

同ファイルのコメントは、verify graph が GPU 上で host flag を待ち、blocking launch が完了まで戻らないため、この停止が起きると説明しています（`src/program/generate.cpp:1243-1245`）。watchdog は要求処理中に進捗が `STRATA_WATCHDOG_S` の時間（既定 60 秒）止まった場合、`no progress for ...` の診断を出します。その際も `launch_blocking()` が真なら `CUDA_LAUNCH_BLOCKING=1 is set, and no verify window can finish with it (#1341)` を追加し、stall report を出して engine を abort します（`src/program/generate.cpp:8997-9007,9017-9047`）。`STRATA_WATCHDOG_S=0` のとき watchdog thread は作られないため、ここで説明した watchdog による abort は行われません。

## 根拠

- `src/program/generate.cpp:1243-1252` — verify window の停止理由、HIP 除外、`getenv` と `atoi` による判定。
- `src/program/generate.cpp:1761-1764` — 起動時警告の条件と文言。
- `src/program/generate.cpp:8997-9009,9017-9047` — watchdog の既定値・無効条件、停止診断、補足と abort。
- `docs/DETAILS.md:1813` — watchdog が進捗の止まった要求を engine 再起動につなげる一般説明。`CUDA_LAUNCH_BLOCKING` の個別説明は見つからず、変数固有の挙動は上記の実装を根拠とした。
