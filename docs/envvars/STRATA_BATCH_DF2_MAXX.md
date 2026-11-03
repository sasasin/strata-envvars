# `STRATA_BATCH_DF2_MAXX`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`--serve` の batch DFlash2 で、各 slot が 1 window に持ち込む追加 draft 行数の上限です。window に入れる各 slot の通常 token 行には影響せず、DFlash2 draft を使う場合にその後ろへ追加する提案行を制限します。対象名を `std::getenv` で読むのは `src/program/generate.cpp` の 1 箇所です。

## 値と判定

値が unset または空文字列なら `df2_cap` は 99 です。空でない値は `std::atoi` で整数に変換し、`std::max(0, ...)` で負数を 0 にします。文字列全体の検証や変換失敗の通知はありません。

| 設定値の例 | `df2_cap` | 結果 |
|---|---:|---|
| unset、空文字列 | 99 | 上限なし同然。ただし DFlash2 の実装上限 7 行など、他の上限が適用される |
| `3`, `+3`, ` 3`, `3tail` | 3 | 変換された整数を上限として使う |
| `0`, `-3`, `word` | 0 | 追加 draft 行を要求しない |
| `99` など 7 より大きい数 | その整数 | 後段で DFlash2 の最大 7 行に制限される |

`atoi` の結果が 0 になる不正な文字列も、明示的な `0` と同じく追加行なしになります。空文字列だけは `atoi` に渡さず既定値 99 です。値を範囲外にした場合の専用 fallback、警告、エラーはありません。

## 有効になる条件

この上限が使われるのは `batch_df2` が有効な `batch_step()` です。slot DFlash2 は、少なくとも `--draft dflash2`（自動選択ではない）、`--batch 2` 以上、`--serve`、同一 GPU 内に収まる layer split ではないことを必要とします。Metal では `STRATA_BATCH_DF2` の要求自体が無効です。Metal 以外では `STRATA_BATCH_DF2` が `0` で始まる値なら無効、空でない別の値なら強制要求となり、未設定時は layer split があり batch groups が 1 以下の場合に既定で要求されます。DFlash2 が build に含まれず、または初期化されない場合、slot DFlash2 は使われません。

DFlash2 要求が `--batch-mtp` の他の条件と合わない場合、Strata は `WARNING: ... is off: ...` を stderr に出して batch MTP を無効にします。さらに slot drafter の割り当てが失敗するとエラーを stderr に出し、初期化経路は `1` を返します。これらは本変数の値判定による警告ではありません。

`STRATA_BATCH_DF2_CONF` は別の後段条件です。確信度が正で draft が ready の場合、確率の積が threshold 以上の間だけ draft 行を残し、`STRATA_BATCH_DF2_MAXX` の上限と併用されます。`--draft-conf` はこの環境変数が未設定または空の場合の確信度既定値に関係しますが、行数上限を上書きしません。

## 実行時の詳細

環境変数は batch slot 状態を初期化する際に 1 回読み、ローカル定数 `df2_cap` に保存されます。リクエストや window ごとには再読込しません。その実行中にプロセス環境が変わっても、この上限には反映されません。

各 window では active slot 数を verifier の row 上限から引いて spare 行数を出し、slot 間に分配します。その値を DFlash2 の最大 7 draft、slot の残り生成 token 数、context の残り行数、本環境変数の上限で順に絞ります。確信度設定が有効ならさらに確率積で短縮します。残った行数分だけ slot の draft token と位置を window に追加し、verifier の batch row 実行と prefix commit に渡します。したがって `0` は draft 行を止めますが、slot の通常 token 行や batch window 自体を止めません。

この変数の値を表示する専用ログはありません。parse 失敗や 0 による専用ログもありません。window 実行に失敗した場合は `ERR <理由>` が stdout に出ますが、これは row 実行側の失敗経路です。

## 根拠

- 読み取りと隣接する確信度・defer 設定: `src/program/generate.cpp:13600-13605`。
- DFlash2 を slot draft として要求する条件、batch MTP 条件、警告: `src/program/generate.cpp:6464-6506`。
- Metal 無効化: `src/program/generate.cpp:6470-6480`。
- build 時の DFlash2 有無で slot drafter 状態が決まる箇所: `src/program/generate.cpp:6684-6692`。
- slot drafter の生成と有効化、生成不可時のログ: `src/program/generate.cpp:6820-6840`。
- spare 行から各上限を適用する箇所: `src/program/generate.cpp:13884-13909`。
- 実際に draft 行を verifier に渡す箇所: `src/program/generate.cpp:13938-13960,14003-14005`。
- DFlash2 の上限が 7 行である根拠: `include/strata/core/dflash2.hpp:37-42`。
