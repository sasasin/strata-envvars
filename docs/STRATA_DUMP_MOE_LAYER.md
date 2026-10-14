# `STRATA_DUMP_MOE_LAYER`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

prompt prefill の MoE 入力を診断用バイナリへ書き出すとき、対象の layer index を選びます。この変数だけでは出力されません。別変数 `STRATA_DUMP_MOE_INPUT` に出力先パスが設定されている必要があります。実装箇所は CUDA Runtime API を使う `src/prefill/prefill.cpp` の MoE prefill 経路一つです。

## 値と判定

`STRATA_DUMP_MOE_LAYER` は `std::atoi` で整数に変換し、現在の layer index `l` と完全一致する場合に対象になります。文字列全体の数値検証はありません。

| 設定 | 比較に使う値 |
|---|---:|
| 未設定 | `0` |
| 空文字、数字で始まらない文字列 | `0` (`atoi` の変換結果) |
| 整数または符号付き整数 | 変換された整数 |
| 数字の後ろに文字が続く値（例: `2abc`） | 数字部分の `2` |
| 先頭に空白がある値（例: ` 2`) | `2` |

大文字小文字の比較はありません。layer index はコード内で 0 から扱われるため、未設定時は layer 0 が選ばれます。モデルにない index や負の値はどの layer とも一致しません。

## 有効になる条件

- `STRATA_DUMP_MOE_INPUT` が設定されていること。判定は `getenv(...) != nullptr` であり、空文字も「設定あり」です。ただし空パスは通常ファイルを開けず、結果ファイルは作られません。
- `Prefill::run_impl` が MoE 入力を host 側で group する経路を実行し、指定 layer に到達すること。Metal は `Prefill::run` 内で別の `metal_engine::prompt_run` に分岐するため、この読み取り箇所を通りません。
- 1プロセスで一度だけ書き出されます。`dumped_moe` が `static` で、layer match 後にファイルを開けたかどうかにかかわらず `true` になるため、後続の prompt/chunk では再試行しません。

## 実行時の詳細

`STRATA_DUMP_MOE_INPUT` の値は、このコードブロックに最初に到達したときに `static const char*` として取得され、その後の環境変更では更新されません。パスが未設定のまま初回到達した場合、同じプロセス内で後から設定しても dump は有効になりません。一方、layer 値は `dump_moe` が有効で未出力の間、layer 判定のたびに `getenv` し直されます。

指定 layer に達すると、実装は `m.mixed` の `T × N` float 値を device-to-host コピーし、CUDA stream を同期した後、`STRATA_DUMP_MOE_INPUT` のパスを `wb` で開きます。成功時は次の順で書き込みます。

1. `int64_t` 3個のヘッダー `{T, N, K}`
2. `T × N` 個の `float`（MoE 入力）
3. `T × K` 個の `int32_t`（router が選んだ expert ID）

同名ファイルがあれば上書きされます。`fopen` に失敗した場合や `fwrite` の戻り値が短い場合、専用のエラー・警告ログは出しません。layer 一致後に dump 済み状態になるので、失敗しても再試行はありません。コード上、この変数による処理の有効化ログもありません。

## 根拠

- `src/prefill/prefill.cpp:3361-3376`: 変数の読み取りと比較、static な一回限りの状態、device-to-host copy、バイナリ出力形式。
- `src/prefill/prefill.cpp:4338-4349`: Metal backend では `metal_engine::prompt_run` を呼び、CUDA 側の `run_impl` へ進まない分岐。
- `docs/NVFP4.md:157-157,196-196`: 実 prompt の MoE 入力を `STRATA_DUMP_MOE_INPUT` で採取して `mmq_nvfp4_parity --real` に渡す用途への言及。layer 選択値や既定値はこの資料では説明されていません。
