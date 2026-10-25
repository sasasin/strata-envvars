# `STRATA_SCORES_HALVE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。対象は Strata 所有ソース。外部ライブラリや driver の環境変数動作は含めない。

## 役割

QSA の block score 計算で、通常の `block_scores_multi_kernel` の代わりに warp 内の和を再帰的に半減する `block_scores_halve_kernel` を使うか選びます。各 query/head の dot product と head ごとの ReLU、head の加算順を保つ実装として記述されており、通常 kernel と同じ score bits を意図しています。スコア計算の結果を変える設定ではなく、CUDA カードの Turing 向け最適化として `docs/DETAILS.md` に列挙されています。

## 値と判定

`src/kernels/cuda/qsa_select.cu:1694-1706` で `std::getenv` と `std::atoi` を使います。環境変数全体の厳密な文字列比較はしません。

| 値 | 判定 |
|---|---|
| 未設定 | デバイスの compute capability が 7.5（または `STRATA_EMULATE_CC=75` で 7.5 として扱われる）かつ `STRATA_SM75_PERF` が非ゼロなら有効。それ以外は無効。 |
| 設定値 | `atoi(value) != 0` なら有効、0 なら無効。明示値は未設定時の Turing 判定を上書きする。 |
| 空文字・数値で始まらない文字列 | `atoi` の結果は 0 なので無効。 |
| 数字の後ろに文字が続く値 | 数字の prefix だけが変換される。例: `1tail` は有効、`0tail` は無効。先頭空白や符号も `atoi` の変換規則に従う。 |

`atoi` の範囲外入力の結果には依存できません。設定値の判定結果は `static const int` に保存され、最初にこの分岐を評価した後の環境変更は反映されません。未設定時のデバイス判定もデバイス番号ごとの `ok[64]` に保存されます。デバイス取得に失敗するか番号が 0–63 の範囲外なら無効です。

## 有効になる条件

値判定が有効でも、`qsa_block_scores()` が次の分岐に入った場合だけこの kernel が使われます（`src/kernels/cuda/qsa_select.cu:1709-1744`）。

- `STRATA_SCORES_MULTI` が有効である。これは未設定時 ON、設定時は `atoi(value) != 0` です（同ファイル:1547-1549）。
- query 数 `nq` が `MQ` 以下（`MQ` は 8）である。
- `active_blocks <= 0` である。
- 先行する `STRATA_QSA_ROWS=1` の完全一致判定が選ばれていない。同ファイル:1717-1721 では rows kernel を先に試し、成功すると halve 判定に進みません。

そのため、通常の prompt selection は適用対象外です。prompt の通常経路は `active_blocks` を正数で渡します（`src/prefill/prefill.cpp:3148-3162`）。QSA decode は `qsa_block_scores` を `active_blocks` なしで呼ぶため、他の分岐条件を満たせば対象になります（`src/core/layer.cpp:1176-1179`; verifier からの呼び出し例: `src/core/verify.cpp:1544-1548`）。

未設定時の既定判定は `sm75_default()` を通り、Turing（実 compute capability 7.5、または `STRATA_EMULATE_CC` による 7.5 の模擬）かつ `STRATA_SM75_PERF` が非ゼロのときに限り有効です（`include/strata/core/sm75_series.hpp:24-37`）。一方、`STRATA_SCORES_HALVE=1` の明示設定には、この関数内で compute capability の制限はありません。ソースはその値で分岐を有効にしますが、資料で最適化として説明されているのは Turing です。

## 実行時の詳細

`qsa_block_scores()` は `nq` に応じて `V=4/8/16` の kernel を選び、1–4 query なら1回、5–8 query なら前半4 queryと残りに分けて2回起動します。kernel は pooled/dead の index key と query から block ごとの score を計算し、tail block に対する補正も通常 kernel と同じ形で適用します（`src/kernels/cuda/qsa_select.cu:1588-1674,1721-1738`）。

起動エラー時は stderr に `qsa_block_scores halve: <CUDA error string>` を出して `exit(1)` します（同ファイル:1736-1738）。この環境変数を読む専用ログはありません。

## 根拠

- 読み取り、`atoi`、既定値、デバイス別 cache: `src/kernels/cuda/qsa_select.cu:1694-1706`
- halve kernel の計算と用途: `src/kernels/cuda/qsa_select.cu:1579-1587,1588-1674`
- 分岐、先行する rows 選択、query 数ごとの起動、エラー時動作: `src/kernels/cuda/qsa_select.cu:1717-1744`
- `STRATA_SCORES_MULTI` の既定値: `src/kernels/cuda/qsa_select.cu:1547-1549`
- Turing 系の共有既定判定と `STRATA_SM75_PERF` の parse: `include/strata/core/sm75_series.hpp:24-43`
- QSA decode / prompt の呼び出し: `src/core/layer.cpp:1176-1179`, `src/prefill/prefill.cpp:3148-3162`
- 文書との照合: `docs/DETAILS.md:2250-2254` はこの変数を compute capability 7.5 向けの bitwise Turing kernel switch として列挙しています。資料にこの変数単体の測定値は見当たらないため、個別の性能向上率は記載していません。
