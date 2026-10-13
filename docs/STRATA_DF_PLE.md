# `STRATA_DF_PLE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

Verifier の複数 token window で、PLE の key/value 投影後に行う post-projection 処理を token ごとの反復から window 一括処理へ切り替えます。結果と token ごとの PLE history snapshot は従来経路と一致させる設計です。環境変数が有効でも、PLE の BF16 key/value 投影を一括実行する既存経路が成立しなければ切り替わりません。

## 値と判定

`src/core/verify.cpp` の関数内 `static const bool` が `getenv("STRATA_DF_PLE") != nullptr && std::atoi(e) != 0` を評価します（1005-1008行）。値全体の比較ではなく `atoi` による整数変換です。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| `1`、`2`、`-1` など、`atoi` が 0 以外に変換する値 | 有効 |
| 空文字、数値で始まらない文字列、`0`、`0suffix` | 無効 |
| 数字の後ろに文字が続く値（例: `1abc`） | 数字部分が 0 以外なら有効。後続文字は判定されない |

空白や符号などの細かな変換規則は C ランタイムの `atoi` に従います。変換可能な整数範囲を外れた値の結果はここでは保証できません。

## 有効になる条件

この変数が実際に選択する `ple_post` は、次のすべてが真の場合だけです（`src/core/verify.cpp:965-967,1009`）。

- `STRATA_PLE_BATCH` が未設定、または値の先頭文字が `0` ではない。これは別の static 判定です。
- `STRATA_DEC_BATCH` が未設定、または `atoi` の結果が 0 ではない。
- 対象の verify group の token 数 `n` が 1 より大きい。
- PLE の key と value の両方に BF16 weights がある。
- `ple_native_bf16_enabled()` と `ple_native_postops_enabled()` が真。
- `batch_rec_` が偽（batch recording 中ではない）。
- 呼び出しが `record_window()` 内の layer 1 かつ PLE が利用可能で有効な経路に到達する。

したがって、`STRATA_DF_PLE=1` 単独では機能を有効化しません。条件が不足すると token ごとの PLE 処理に進みます。`STRATA_DEC_BATCH=0` などで一括 projection が無効ならこの分岐も無効です。

## 実行時の詳細

`STRATA_DF_PLE` は、`record_window()` が layer 1 の PLE 処理に初めて到達した時に読み込まれ、その値がプロセス内で固定されます。最初の判定後に環境を変更しても反映されません（`src/core/verify.cpp:955,1005-1009`）。

有効な場合、既存の一括 key/value projection の後、各 row の hyper-connection residual write をまとめて実行し、`native_ple_postops_batch_snap()` で PLE post-ops、history の逐次更新、および各 token 後の history snapshot 作成を行います。native GR の複数 row 実装が無効なら residual write は row ごとに行います（`src/core/verify.cpp:1010-1028`）。その後に使われる各 token の snapshot は従来の commit 用データです。

無効または適用条件を満たさない場合は row ごとに residual write、PLE post-processing、history advance、history snapshot copy を行います（`src/core/verify.cpp:1029-1049`）。一括 post-ops が例外を投げた場合は `record_window()` が `verify PLE (window): <例外内容>` をエラー文字列に設定して失敗します（`src/core/verify.cpp:1023-1027`）。

## 根拠

- `src/core/verify.cpp:840-845` — PLE 有効状態、window group、`STRATA_DEC_BATCH` の既定値。
- `src/core/verify.cpp:955-974` — layer 1 の処理、`STRATA_PLE_BATCH` の判定、一括 projection 条件。
- `src/core/verify.cpp:1001-1049` — `STRATA_DF_PLE` の parse、適用条件、batch/per-token の分岐、snapshot とエラー処理。
- `include/strata/kernels/native_ple_postops.hpp:38-43` — window 版関数が per-token 呼び出しと同じ演算を行い、各 token 後の snapshot を書くというインターフェース上の説明。
- `src/kernels/cuda/native_ple_postops.cu:273-287` — snapshot 付き batch 関数の実処理と launch error 確認。
- `src/kernels/verify_batch_parity.cpp:100-152` — GPU 合成データで 2、3、4、8 token の結果、最終 history、各 snapshot を比較する parity 検証コード。これは測定値ではなく、調査中にテストを実行してはいません。

`docs/DETAILS.md` に `STRATA_DF_PLE` の説明や性能測定値は見つかりませんでした。ここではコードとインターフェースコメントから確認できる挙動だけを記載しています。
