# `PC_GU`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`PC_GU` は Metal の `prompt_chain` ハーネスで、MoE expert の gate/up GEMM に使うカーネル系列と、v3 系列を選んだときのタイル寸法を指定します。Strata の通常の生成経路でこの名前を読む箇所は確認できません。したがって、通常の Strata サーバーや CLI の動作を切り替える環境変数としては確認できず、対象は `metal/tests/prompt_chain.cpp` の計測用プログラム内に限られます。同ファイル冒頭も、実 GGUF 重みを使う prompt 処理時間の計測プログラムと説明しています。

## 値と判定

| `PC_GU` の状態・値 | ハーネス内の選択 |
|---|---|
| 未設定 | `COOP_K4` 由来の `k4` が真なら `v3:auto`、偽なら `v2` |
| 空文字を含む設定値 | 値をそのままモード文字列として使う。空文字は `v3:` で始まらないため v2 系列 |
| `v3:auto` | v3 系列。gate/up タイルは `TM=16, TN=32, TK=32, SG=4` |
| `v3:` で始まる別の文字列 | v3 系列。文字列の3文字目以降から `sscanf("%d,%d,%d,%d", ...)` で4整数を順に読む |
| 上記以外 | v2 系列 |

比較は大文字小文字を区別する完全一致（`v3:auto`）または先頭一致（`v3:`）です。整数列は文字列全体の妥当性検査をせず、`sscanf` の戻り値も確認しません。タイル配列は `{16,64,16,2}` で初期化され、読み取れた整数だけが順に置き換わります。したがって、部分的な列や不正な列も拒否されず、その時点で配列に残る値が使われます。

## 有効になる条件

`PC_GU` は `metal/tests/prompt_chain.cpp` の `main()` が実行されるときだけ参照されます。環境変数の値を渡すことで `prompt_chain` 内の計測対象 MoE 経路を変更できます。ソース全体を検索した範囲では、通常の `src/`, `include/`, `sycl/`, `metal/src/` 実装に読み取り箇所はありません。

未設定時の `k4` 判定は同じテストハーネスの `coop_k4(cx)` によります（`metal/tests/prompt_chain.cpp:105`, `metal/tests/coop_probe.h:10`）。これは既定値の選択にのみ関係し、`PC_GU` が明示設定されていれば `k4` による `v2` / `v3:auto` 選択を上書きします。`PC_GU` を通常のサーバーや CLI に設定しても、このソース調査で確認できた範囲では効果はありません。

## 実行時の詳細

ハーネスは `getenv("PC_GU")` を `main()` 内で一度読みます。未設定時は前述の既定値を選び、選択結果の `gu_mode` から v3 系列かどうかを判定します。v3 系列なら `mm_gu3_<量子化型>_<TM>_<TN>_<TK>_<SG>` のパイプラインを選び、threadgroup の幅を `32 * SG` とします。v2 系列なら `mm_gu2_<量子化型>_<固定タイル>` を選び、幅は `64` です。また、間接 dispatch 用メタデータの gate/up task 数も、v3 では `NFF / (TN * SG)`、v2 では `NFF / 64` として設定されます (`metal/tests/prompt_chain.cpp:205,428-443`)。

このコード経路に `PC_GU` 専用の警告やエラー処理はありません。未知の値はエラーにせず v2 として扱い、`v3:` 値のタイル解析失敗も検出しません。テスト実行や GPU での挙動確認は行っていません。

## 根拠

- `metal/tests/prompt_chain.cpp:1-19` — `prompt_chain` が実 GGUF 重みによる prompt 計測用ハーネスであること、および MoE 経路の概要。
- `metal/tests/prompt_chain.cpp:105` — `COOP_K4` 判定を用いた `k4` の取得。
- `metal/tests/prompt_chain.cpp:134-149` — `PC_GU` の読み取り、既定値、v3 タイル文字列の解析、v2/v3 判定。
- `metal/tests/prompt_chain.cpp:205` — gate/up の間接 dispatch 用 task 数。
- `metal/tests/prompt_chain.cpp:428-443` — 選択した gate/up パイプラインと threadgroup 幅。
- `metal/tests/coop_probe.h:10` — `k4` 判定 helper の定義。
