# `STRATA_PIPELINE_LOG`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

パイプライン decode の chain 生成と verdict の詳細を stderr に出す診断スイッチです。値によってパイプラインの選択、verdict、出力 token を変える処理はありません。CUDA/HIP 共通実装と SYCL 実装にそれぞれ読み取りがあります（`engine/src/program/generate.cpp:21872,22302-22304,22455-22461`、`engine/sycl/src/program/generate.cpp:11817,12321-12323,12430-12432`）。

この変数は単独では有効になりません。`pipe_dbg_env` が `STRATA_PIPELINE_DEBUG` を先に判定し、その値が有効な場合に限りこの名前を環境から取得します（`engine/src/program/generate.cpp:681-687`、`engine/sycl/src/program/generate.cpp:325-326,337-340`）。

## 値と判定

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `STRATA_PIPELINE_DEBUG` が有効で、パイプライン decode のログ初期化まで到達 | `pl_log=false` | 空文字、`0`、`false`、`1` など、設定されていればすべて `pl_log=true` | なし。内容・数値・大文字小文字は検査しない |
| `STRATA_PIPELINE_DEBUG` が unset、空文字、または先頭文字が `0` | `pl_log=false` | なし。この場合 `pipe_dbg_env` は対象名を読まず `nullptr` を返す | 対象変数を設定しても無効 |

`STRATA_PIPELINE_LOG` 自体は `getenv(...) != nullptr` 相当の設定有無判定で、文字列全体の比較や変換はしません。したがって `STRATA_PIPELINE_DEBUG` が有効なら、対象変数の `0` や空文字も有効です。`STRATA_PIPELINE_DEBUG` 側は `v != nullptr && v[0] != 0 && v[0] != '0'` で判定するため、unset・空文字・`0`・`0anything` は無効、`1`・`true`・空白で始まる値は有効です（`engine/src/program/generate.cpp:684-686`、`engine/sycl/src/program/generate.cpp:337-339`）。

## 有効になる条件

- サーバーの decode で `--pipeline-windows` のパイプラインが構成されている必要があります。CUDA/HIP 共通実装では `pipe` が成立し（パイプライン window 数が正、2 段以上、同一 GPU への split ではなく、全 stage が構成済み）、さらに `pl_want` が真、すなわち window 数が 2 以上で GDN snapshot が利用可能な場合に対象のログ初期化へ進みます（`engine/src/program/generate.cpp:13263-13267,21802-21822`）。SYCL では 2 段の layer split、同一 GPU split ではないこと、2 window 以上、および snapshot の存在が条件です（`engine/sycl/src/program/generate.cpp:7708-7717,11775-11799`）。
- その request がキャンセル済みでなく、生成上限に達していない必要があります。repetition penalty の履歴がある request と coupled draft sampling の request はパイプライン decode を使わず、stderr に serial decode の理由を出します（CUDA/HIP: `engine/src/program/generate.cpp:21811-21822`、SYCL: `engine/sycl/src/program/generate.cpp:11783-11799`）。
- `STRATA_PIPELINE_DEBUG` は必要条件です。`STRATA_PIPELINE_LOG` だけを設定しても、このデバッグログは有効になりません。CLI や他の環境変数がこのログ設定の値を上書きする処理はありません。

## 実行時の詳細

両実装の `pipe_dbg_env` は、翻訳単位ごとに `STRATA_PIPELINE_DEBUG` の有効判定を関数内 `static` に一度だけ保存します。無効なら以後の呼び出しも `nullptr` を返し、有効なら引数で渡された環境変数名を `getenv` で取得します（`engine/src/program/generate.cpp:684-686`、`engine/sycl/src/program/generate.cpp:337-339`）。

`pl_log` も関数内 `static const bool` なので、実際の pipeline decode が初めてこの初期化箇所に達したときに `STRATA_PIPELINE_LOG` の設定有無を読み、そのプロセス内でキャッシュします。初期化後に環境を変更しても反映されません。pipeline decode に到達しなければ、この対象名の読み取りも行われません（`engine/src/program/generate.cpp:21872`、`engine/sycl/src/program/generate.cpp:11817`）。

`pl_log` が真の場合、chain の作成時に `strata pipeline: chain ...` の行を stderr に出し、各 verdict の後に `strata pipeline: verdict ...` を出します。CUDA/HIP 実装の verdict 行は `out` に続けて token ID も列挙しますが、SYCL 実装の行は verdict と B window の状態までです。このスイッチによる終了、失敗、timeout の分岐はありません（CUDA/HIP: `engine/src/program/generate.cpp:22302-22304,22455-22461`、SYCL: `engine/sycl/src/program/generate.cpp:12321-12323,12430-12432`）。

## ログと測定値

ログは stderr への `fprintf` です。実装上の書式は次のとおりです。

- CUDA/HIP と SYCL の chain 行: `strata pipeline: chain %d for p=%lld T=%d: B T=%d p_on %.3f (%d outputs)`（`engine/src/program/generate.cpp:22302-22304`、`engine/sycl/src/program/generate.cpp:12321-12323`）。
- CUDA/HIP の verdict は `strata pipeline: verdict p=%lld T=%d a=%d B %s%s (B front %d%s, A com %x) out` に token ID 群が続きます（`engine/src/program/generate.cpp:22455-22461`）。
- SYCL の verdict は `strata pipeline: verdict p=%lld T=%d a=%d B %s%s` です（`engine/sycl/src/program/generate.cpp:12430-12432`）。

`STRATA_PIPELINE_LOG` に関する測定値はありません。この変数は診断行の出力だけを切り替えます。

## 根拠

- 全参照の実装側読み取り: `engine/src/program/generate.cpp:21872`、`engine/sycl/src/program/generate.cpp:11817`。他の出現は `engine/sycl/src/core/verify.cpp:4497` のコメントと `terminal/data/settings-register.json:33868` の設定レジストリ項目で、いずれも値を読むコードではありません。
- helper の debug gate とキャッシュ: `engine/src/program/generate.cpp:681-687`、`engine/sycl/src/program/generate.cpp:325-326,337-340`。
- パイプラインの構成条件と request ごとの serial fallback: `engine/src/program/generate.cpp:13263-13267,21811-21822`、`engine/sycl/src/program/generate.cpp:7708-7717,11783-11799`。
- 有効時の stderr 出力: `engine/src/program/generate.cpp:22302-22304,22455-22461`、`engine/sycl/src/program/generate.cpp:12321-12323,12430-12432`。
