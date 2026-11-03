# `STRATA_QSA_FUSE_NR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA 層の prefill で、K・attention query・indexer query の RMS normalization と rotary embedding を一つの `rms_rope_rows` kernel にまとめるかを選びます。query の fused 経路では Q の split も同じ処理に含まれます。OFF のときは、query を split してから RMS normalization と rotary を別々に実行します。設定値による分岐は `src/prefill/prefill.cpp` にあり、`src/prefill/kernels.cu` が CUDA/HIP の fused kernel を実装します（`src/prefill/prefill.cpp:554-565,4158-4163,4224-4237,7416-7421,7467-7480`; `src/prefill/kernels.cu:2416-2465,3375-3398`）。

## 値と判定

設定文字列全体や数値としての妥当性は検査せず、`getenv()` の結果の先頭文字だけを見ます。

| 値 | 判定 |
|---|---|
| unset | ON |
| 空文字 | ON（設定済みだが先頭文字は `\0`） |
| 先頭文字が `0` | OFF（例: `0`, `0anything`） |
| その他の先頭文字 | ON（例: `1`, `true`, `false`, 空白、負号） |

大文字小文字、後続文字、空白、数値変換、範囲 clamp はありません。したがって `false` も ON です。CLI 引数や設定ファイルとの優先順位、無効値時の fallback はなく、明示値のうち先頭が `0` の場合のみ旧 kernel 列へ切り替えます。根拠: `src/prefill/prefill.cpp:563-565`。

## 有効になる条件

- `strata_prefill` を使う CUDA/HIP engine の QSA prefill 経路で値が参照されます。通常の QSA 層処理と別の batched prefill 経路の双方で同じ判定関数を使います（`src/prefill/prefill.cpp:4138-4159,7399-7417`）。
- QSA 層を処理しないモデル・経路ではこの設定は kernel 選択に影響しません。値が ON なら K、Q、indexer query の各入力を fused 経路へ送り、OFF なら既存の複数 kernel に分岐します（`src/prefill/prefill.cpp:4158-4163,4224-4237,7416-7421,7467-7480`）。
- `src/prefill/kernels.cu` の fused 実装は CUDA/HIP kernel です。Metal host も `prefill.cpp` を含みますが、Metal 側の `rms_rope_rows` は未実装 entry point の stub で、到達すると `strata::metal_engine::missing` を呼びます。既定の stub は stderr に `strata metal: strata::prefill::rms_rope_rows has no Metal implementation yet` を出して exit code 86 で終了します（`metal/CMakeLists.txt:95-119`; `metal/src/engine/stubs_0291.cpp:15-19`; `metal/src/engine/missing.cpp:14-22`）。この環境変数は Metal kernel を実装・有効化しません。
- fused kernel wrapper は `T <= 0` なら何もせず戻り、`dim` が 64..256 の範囲外なら stderr に `prefill rms_rope_rows: dim ... is outside 64..256` を出して終了コード 1 で終了します。RoPE scaling が無効な場合も stderr に `prefill rope: invalid rope scaling: ...` を出して終了します。通常の呼び出しは `dim` 128 または 256 です（`src/prefill/kernels.cu:3375-3385`; 呼び出し寸法は `src/prefill/prefill.cpp:4159,4225,4233`）。

## 実行時の詳細

判定は `qsa_fuse_nr()` の最初の呼び出し時に一度行い、関数内の `static const bool` にキャッシュします。通常処理では K の後、Q と indexer query の前処理ごとに分岐を使い、同じ関数が別の batched prefill 経路からも呼ばれます。プロセス実行中に環境を変更しても、その後の判定には反映されません（`src/prefill/prefill.cpp:563-565,4158-4163,4224-4237,7416-7421,7467-7480`）。

通常処理の QSA prefill では、最初の該当層で stderr に `strata prefill: QSA layers: norm + rope in one pass on, attention gate in the attention epilogue ...`（ON 時）または `... off, ...`（OFF 時）を出します。この行は norm/rope と別機能である attention gate の状態も併記し、`told` により一度だけ出力されます。別の batched prefill 経路にはこの診断行がありません（`src/prefill/prefill.cpp:4392-4398,7514-7529`）。

既定 ON では、QSA の K・Q・indexer query の前処理を fused kernel に渡します。OFF では K と indexer query は `rms_rows` の後に `rope`、Q は `split_q`、`rms_rows`、`rope` の順に処理します。ここでの値判定による別環境変数との相互作用、値の転送、警告は確認できません（`src/prefill/prefill.cpp:563-565,4158-4163,4224-4237`）。

## 根拠

- 名前の全参照を調べたところ、環境から値を読むのは `src/prefill/prefill.cpp:564` のみです。同ファイルの `553-565` は fused norm/rotary 選択 helper、他の名前一致はコメント・kernel 宣言・parity 用ソース・Metal stub・診断用ツール・CMake の parity target です。`docs/envvars/000_envvers.md:1801` は候補名を掲載しています。
- `docs/DETAILS.md` を含む Strata の `docs/` には、この環境変数名や `rms_rope_rows` に関する記載が見つからず、照合できる説明・測定値はありません。
- CUDA/HIP 側の `strata_prefill` は `src/prefill/gemm.cu`、`src/prefill/kernels.cu`、`src/prefill/prefill.cpp` から構成されます（`CMakeLists.txt:838-844`）。
- 本文で述べた kernel 選択と診断文字列の根拠は `src/prefill/prefill.cpp:554-565,4158-4163,4224-4237,4392-4398,7416-7421,7467-7480`、fused kernel とその入力条件・失敗経路は `src/prefill/kernels.cu:2416-2465,3375-3398` です。
