# `STRATA_SERVE_STOP_BOUND`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP ビルドの `--serve` decode で、採用済み token のうち要求が実際に出力できない分を verifier の状態へ commit しないようにします。採用済み token の並びに EOS token がある場合も、EOS までの行だけを commit します。これは `serve_stop_bound()` による commit 行数の制限です。CUDA など `STRATA_USE_HIP` でないビルドでは、この環境変数の読み取りも制限処理の呼び出しもコンパイルされません。

## 値と判定

実装は文字列全体を `strcmp(v, "0")` で比較します。数値変換や先頭文字比較はありません。

| 値 | `stop_bound` |
| --- | --- |
| 未設定 | 有効 |
| 完全一致の `0` | 無効 |
| 空文字、`00`、`0 `、`false`、その他の文字列 | 有効 |

既定値は有効です。明示的に無効にする方法は値をちょうど `0` にすることです。CLI 引数や別環境変数による上書きは、この判定箇所にはありません。根拠: `src/program/generate.cpp:17403-17410`。

## 有効になる条件

- `STRATA_USE_HIP` を定義してビルドした `strata` でのみ、値を読み取り、処理を有効化します。HIP 以外では参照箇所が `#if defined(STRATA_USE_HIP)` の中にあるため作用しません。
- 対象箇所は `--serve` のリクエスト decode ループです。HIP の pipelined decode と通常の decode の両方に制限処理があります。
- 通常 decode では merged window（prompt 行を含む最初の window）は対象外です。prompt の行をすべて commit する経路を保つためです。
- サーバーが許可した残りの生成数 `max_new - produced_n` と、request の EOS ID 一覧 `o.eos_ids` が制限に使われます。これらは環境変数で変更されません。

根拠: `src/program/generate.cpp:17964-17972,18488-18497`。

## 実行時の詳細

環境変数は `--serve` の request decode 部分で初回に到達したときに `static const bool` として読み取られます。初期化後は同一プロセス内の後続 request で再評価されません。プロセス起動後に環境を変えても、この値には反映されません (`src/program/generate.cpp:17406-17409`)。

有効時、採用数を `accepted`、生成可能な残数を `remaining` として、ヘルパーは `count = min(accepted, max(0, remaining))` を求め、候補出力の先頭 `count` 個を走査します。最初の EOS を見つけたら EOS 自身を含む個数を返し、なければ `count` を返します (`include/strata/core/serve_stop_bound.hpp:8-14`)。呼び出し側は返値から1を引いて採用末尾 `a` を更新し、その `a + 1` 行だけを commit します。通常 decode では同じ行数を `consumed` に記録します (`src/program/generate.cpp:17968-17973,18494-18496,18512-18535`)。したがって、生成上限の先にある採用行や EOS より後ろの行が request の verifier state に commit されないよう境界を合わせます。

この環境変数専用のログ、警告、終了経路はありません。commit 自体が失敗した場合の `ERR` 出力と request 終了は通常の verifier commit 経路であり、この変数の値判定が出すものではありません (`src/program/generate.cpp:18512-18516`)。

## 根拠

- 読み取り、HIP compile guard、既定値、文字列判定、static cache: `src/program/generate.cpp:17403-17410`
- pipelined decode の commit 上限: `src/program/generate.cpp:17964-17973`
- 通常 decode と merged prompt window の除外: `src/program/generate.cpp:18488-18497`
- 上限計算と EOS を含む走査: `include/strata/core/serve_stop_bound.hpp:8-14`
- commit と session state への反映: `src/program/generate.cpp:18512-18535`
