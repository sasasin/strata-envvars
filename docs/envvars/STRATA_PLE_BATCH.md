# `STRATA_PLE_BATCH`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

PLE（layer 1 の n-gram / history block）の key/value projection を、複数行まとめて計算する経路を選びます。プロンプト prefill と decode の verify window の両方で参照されます。どちらも PLE が実行される場合に限って関係します。

同じ名前でも、prefill は `atoi()` の結果、verify window は先頭文字を使って判定します。さらに verify window 内でも、BF16 key/value projection 用と別の multi-row projection 用とで判定条件が分かれています。

## 値と判定

| 経路 | 未設定 | 設定時の判定 |
|---|---|---|
| プロンプト prefill | 有効 | `atoi(value) != 0` なら有効。それ以外は無効 |
| verify window: BF16 key/value projection | 有効 | 先頭文字が `0` でなければ有効 |
| verify window: 別の multi-row projection | 無効 | 先頭文字が `1` の場合だけ有効 |

prefill の `atoi()` は文字列全体の妥当性を検証しません。たとえば空文字や `true` は 0 となり無効、`1junk` や `-1` は非ゼロとなり有効です。verify window の BF16 key/value 判定では `0`, `0anything` は無効ですが、空文字、`true`、`2` は先頭文字が `0` ではないため有効です。別の multi-row projection は `1`, `10`, `1anything` のように先頭が `1` の場合だけ有効で、空文字や `true` は無効です。大文字小文字、空白の trim、文字列全体の数値 parse は行いません。

読み取り結果は各経路の関数内 `static const bool` に保存されます。その経路で初めて評価された後にプロセス環境を書き換えても、値は再評価されません。

根拠: `src/prefill/prefill.cpp:2111-2120`, `src/core/verify.cpp:955-974`。

## 有効になる条件

prefill の batched PLE は、PLE が ready で対象 layer 範囲が layer 1 を含むこと、native postops が有効であること、BF16 または native の PLE key projection があること、scratch 領域から計算した token 収容数が 64 以上であることを要します。条件を満たさないときは、変数が有効でも従来の token ごとの PLE 処理に進みます。実際の batched 部分は chunk 内を scratch 容量に合わせて sub-batch に分けて実行します。

verify window では次の2経路があります。

- BF16 key/value projection をまとめる経路は、変数が上表の BF16 判定で有効、`STRATA_DEC_BATCH` が有効、verify group の行数 `n > 1`、key と value の BF16 weights があり、native BF16 projection と native postops が有効な場合に使われます。
- もう一つの multi-row projection は、値の先頭が `1`、`n > 1`、key weight が BF16 または native、native BF16 projection が有効で、BF16 経路が選ばれていない場合に使われます。

このため、たとえば `STRATA_PLE_BATCH=true` は prefill では `atoi()` が 0 となって無効ですが、verify window の BF16 経路では値判定上は有効です（ただし残りの条件も必要です）。`STRATA_PLE_BATCH=2` も prefill と verify の BF16 経路では有効になり得ますが、verify の別の multi-row projection では選ばれません。

HIP の gfx1151（Strix Halo）では、起動時に `STRATA_PLE_BATCH=1` が既定設定されます。利用者が変数を何らかの値（空文字を含む）で設定済みならその値を保持します。`STRATA_GFX1151_DEFAULTS=0` で既定値テーブル全体を無効にできます。CUDA ビルド、gfx1151 以外の HIP GPU にはこの既定設定は適用されません。

根拠: `src/prefill/prefill.cpp:2111-2120,2504-2518`, `src/core/verify.cpp:845,955-975`, `src/core/arch_defaults.cpp:32-35,61-69`, `src/program/generate.cpp:2190-2196`, `docs/STRIX_HALO.md:83-97`。

## 実行時の詳細

prefill の有効経路は layer 1 で chunk の PLE rows に対して key/value projection を複数行まとめて実行し、native batched postops を呼びます。変数が無効、または条件を満たさない場合は `ple_block()` を token ごとに呼ぶ経路です。PLE rows の読み込みと device への転送は、この分岐とは別に chunk ごとに行われます。

verify window の BF16 経路は key/value projection を multi-row kernel で計算した後、通常は各行の PLE postprojection と history advance を行います。`STRATA_DF_PLE` も有効で、batch recording 中でない場合には `native_ple_postops_batch_snap()` の経路に進みます。別の multi-row projection 経路も key/value を先に計算しますが、その後の PLE block と history advance は行ごとに処理します。

投影処理で例外が発生した場合、prefill は `prefill PLE: ...`、verify window の BF16 multi-row 投影は `verify PLE multi: ...`、別の multi-row 投影は `verify PLE batch: ...` をエラー文字列に設定します。これらの呼び出し側で処理が失敗として返されます。この変数自体に専用の有効・無効ログはありません。gfx1151 の起動時既定値が設定された場合は、`arch_defaults.cpp` が変更したスイッチ名を含む stderr の行を出します。

根拠: `src/prefill/prefill.cpp:2225-2257,2499-2545`, `src/core/verify.cpp:975-999,1029-1049`, `src/core/arch_defaults.cpp:61-80`。

## 文書との照合

`docs/STRIX_HALO.md` は gfx1151 の既定スイッチとしてこの変数を挙げ、verify window の PLE key/value projection をまとめるものと説明しています。`include/strata/core/arch_defaults.hpp` と `src/core/arch_defaults.cpp` の実装も gfx1151 のみで既定値 `1` を設定します。文書の説明は verify window の projection に絞られていますが、ソースではプロンプト prefill も同じ変数を読み、異なる parse 規則で batched PLE を選びます。既定設定と環境値の取り扱いはコードを根拠に記載しました。
