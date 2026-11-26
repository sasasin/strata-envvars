# `STRATA_SERVE_STOP_BOUND`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の生成で、検証 window が受理した行のうち、そのリクエストが実際に出力できる範囲だけを会話セッションへ commit する制御です。既定で有効で、commit 範囲は `STRATA_SERVE_STOP_BOUND=0` で無効化できます。Strata のソースコメントは、出力される token はどちらの設定でも同じで、変わるのはセッションが保持する受理済み行だと説明しています（`engine/src/program/generate.cpp:21739-21745`）。

実際の読み取りは `generate.cpp` の一か所で、判定 helper は `engine/include/strata/core/serve_stop_bound.hpp` の `serve_stop_bound_on` です。`--serve` では要求を stdin から受け取る常駐エンジンを通ります（`engine/src/program/generate.cpp:11095-11116,4069`）。

## 値と判定

`std::getenv` の結果を文字列全体で `std::strcmp(value, "0")` と比較します。数値変換や真偽値文字列の解釈はありません（`engine/src/program/generate.cpp:21742`, `engine/include/strata/core/serve_stop_bound.hpp:60-65`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `--serve` の decode 経路 | 有効 | 空文字、`1`、`true`、`false`、`00`、`0anything`、` 0`、`0 ` | 厳密に `0` のみ |

大文字小文字・空白・数値としての妥当性は判定しません。したがって `TRUE` も有効、` 0` や `0 ` も有効です。CLI 引数や他の環境変数による値の上書き・優先順位はありません。`--serve` 以外の通常生成経路では、この変数を読むコードは確認できません（読み取り箇所: `engine/src/program/generate.cpp:21742`）。

## 有効になる条件

- `--serve` の要求処理で使われる通常の verify window、または `--pipeline-windows` の window 処理が対象です。両方の commit 前に `stop_bound` が判定されます（`engine/src/program/generate.cpp:22378-22405,23029-23049`）。
- `--batch` の slot が admission 後に進む window は別の slot 処理です。調査対象 commit ではその slot 用の行 commit に `serve_stop_bound` の呼び出しがなく、この環境変数による上限処理は確認できません（slot admission と後続処理: `engine/src/program/generate.cpp:23586-23615`; helper 呼び出し箇所は同ファイルの `22380-22385,23044-23049`）。
- 読み取り・分岐に OS、GPU backend、GPU 世代の条件はありません。ソースコメントは bound が「every backend」で既定有効と記しています（`engine/src/program/generate.cpp:21739-21745`）。

## 実行時の詳細

`stop_bound` は関数内 `static const bool` で初回に初期化され、以後プロセス内で cache されます。実行中に環境を書き換えても再評価されません。初回評価は要求の decode 設定を読む位置（`engine/src/program/generate.cpp:21674-21680,21739-21745`）で行われます。

各 window でまず draft の受理数を求め、その `a + 1` 行と、残りの出力上限 `max_new - produced_n`（hold が有効なら hold の残りも考慮）を `serve_stop_bound` に渡します。helper は行数を `min(accepted, max(remaining, 0))` に制限し、その範囲に EOS token があれば EOS の行までを含めて終了します。戻り値に合わせて verifier の commit 行数を縮め、commit された token だけを `consumed` に追加します（`engine/include/strata/core/serve_stop_bound.hpp:9-15,22-29`; 呼び出しと commit: `engine/src/program/generate.cpp:22378-22405,23029-23049,23066-23088`）。

その後 `consumed` が要求終了時の live conversation になり、次の要求がそこから続行できます（`engine/src/program/generate.cpp:23393-23408`）。bound を切ると、出力されない後続の受理行もセッションへ commit され得ます。コードコメントによれば、生成してクライアントへ出す token 列自体は変わりません（`engine/src/program/generate.cpp:21739-21742`）。

## ログと測定値

この変数専用のログ、警告、エラー、終了経路はありません。要求の通常プロトコルは出力 token ごとの `T <id>` と最後の `DONE ...` です（`engine/src/program/generate.cpp:11101-11113,23111-23123,23575-23585`）。

実装コメントには、HIP、R9700 4 枚、Qwen3.8-Flash-Next IQ3_S の測定として、16 continuation 中、bound 有効時は古い checkpoint への fallback が 0 件、無効時は 4 件だったとの記録があります。これはソースコメントに記載された測定値であり、今回の調査で再測定した値ではありません（`engine/src/program/generate.cpp:21739-21742`）。

## 根拠

- `engine/src/program/generate.cpp:21739-21745` — 既定値、環境変数の読み取り、static cache、意図のコメント。
- `engine/include/strata/core/serve_stop_bound.hpp:9-15,60-65` — commit 上限・EOS 判定と値の厳密比較。
- `engine/src/program/generate.cpp:22378-22405,23029-23049,23066-23088` — 通常/pipeline window での上限適用と session 行の commit。
- `engine/src/program/generate.cpp:23393-23408` — 要求後に commit 済み会話を live state として保持。
- `engine/src/program/generate.cpp:23586-23615` — batch admission と slot 後続処理への移行。
