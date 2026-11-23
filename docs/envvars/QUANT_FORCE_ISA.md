# `QUANT_FORCE_ISA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

これは通常の Strata engine 起動用設定ではなく、量子化 oracle テストを走らせる `engine/tests/quant/run_oracle.sh` 専用の入力である。値が空でなければ、スクリプトは `quant_parity` の起動時だけ同じ値を `STRATA_FORCE_ISA` として子プロセス環境に設定する。`quant_selftest`、ビルド、`--regen-check` の起動には渡さない（`engine/tests/quant/run_oracle.sh:35-45`）。

`quant_parity` 側では x86 の CPU feature probe を制限する用途に使われる。これは同プログラムが表示する Strata quant layer の ISA と default arithmetic contract に加え、テスト対象 kernel の ISA 適合フィルターにも影響する。`QUANT_FORCE_ISA` 自体を engine が読む実装はない。変数名の唯一の参照はこのテストスクリプトである（`engine/tests/quant/run_oracle.sh:6,39`、転送先の実装は `engine/src/quant/isa.cpp:48-57,84-87`、フィルターは `engine/tests/quant/quant_parity.cpp:307-317`）。

## 値と判定

シェル側は `${QUANT_FORCE_ISA:-}` を `-n` で判定する。未設定と空文字はどちらも転送されず、それ以外は文字列を加工せず `STRATA_FORCE_ISA` に設定する。数値変換、trim、大文字小文字変換、入力値の検証はしない（`engine/tests/quant/run_oracle.sh:39-40`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| スクリプトから x86 `quant_parity` への転送 | 上限指定なし | `avx2`、`avx`、`sse`（そのまま `STRATA_FORCE_ISA` に転送） | 空文字は転送なし。`AVX`、`avx `、`0` などは転送自体はされるが、転送先で認識されない |
| Arm64 `quant_parity` | 上限指定なし | スクリプトは値を転送するが、quant layer probe はこの値を参照しない | 同左 |

x86 で転送先が認識する値は完全一致の小文字 `avx2` / `avx` / `sse` のみ。空または未設定の `STRATA_FORCE_ISA` は cap 3、`avx2` は cap 2、`avx` は cap 1、`sse` は cap 0 となる。その他の非空文字列は警告を stderr に出し、cap 3（制限なし）に戻る。値は CPU が持つ機能を増やさず、probe 結果を上限で落とすだけである（`engine/src/quant/isa.cpp:49-57,84-87`）。

## 有効になる条件

- `engine/tests/quant/run_oracle.sh` を実行し、ビルドと `quant_parity` の起動まで到達すること。スクリプトは CUDA/HIP を無効にして quant test targets を構成する（`engine/tests/quant/run_oracle.sh:33-40`）。
- この値が量子化 layer の probe に作用するのは x86 build の `quant_parity` に限られる。Arm64 ではスクリプトが値を転送しても、`isa_cap()` と cap 適用コードは `STRATA_QUANT_X86` の条件内にあり、Arm64 の probe はその値を使わない（`engine/src/quant/isa.cpp:8-16,48-57,84-103`）。
- `QUANT_PARITY_ARGS` などの CLI 引数は別に `quant_parity` へ渡される。ISA 指定を CLI で上書きする分岐はなく、選択した flavour はビルド時の ggml-cpu 構成を決めるため、実行時の ISA cap とは別である（`engine/tests/quant/run_oracle.sh:23-40`）。

## 実行時の詳細

スクリプトは各 flavour のループで `QUANT_FORCE_ISA` を参照する。非空ならその一回の `quant_parity` 起動にだけ `STRATA_FORCE_ISA=$QUANT_FORCE_ISA` を付け、次の flavour の起動時にも再判定する。スクリプト自身は値を cache せず、子プロセス起動後の親環境変更はその子には反映されない。環境変数は `quant_selftest` や後続の `--regen-check` 起動に渡されない（`engine/tests/quant/run_oracle.sh:23,35-45`）。

`quant_parity` の x86 probe は `caps()` の関数内 static 値として初回評価時に保存される。`main` の起動ログ作成で `best_isa()` を呼ぶため、通常はその時点で読み取られ、同一プロセス内での後続呼び出しでは再読込しない（`engine/src/quant/isa.cpp:49-57,109-120`、`engine/tests/quant/quant_parity.cpp:664-669`）。

## ログと測定値

`QUANT_FORCE_ISA` 固有のログはない。x86 で転送値が不正なら、`quant_parity` は stderr に `strata: STRATA_FORCE_ISA=<値> is not avx2, avx or sse; ignored` を出し、制限なしで続行する（`engine/src/quant/isa.cpp:50-56`）。

スクリプトは `quant_parity` の非ゼロ終了を `rc=1` に記録し、最終的に非ゼロで終了する。スクリプトの `QUANT_FORCE_ISA` 分岐自体は理由を表示しない（`engine/tests/quant/run_oracle.sh:39-47`）。この変数について `docs/DETAILS.md` に測定値の記載はない。

## 根拠

- `engine/tests/quant/run_oracle.sh:1-11,23-47` — テスト runner の用途、ビルド flavour、値の空判定、子プロセスへの転送、終了状態。
- `engine/src/quant/isa.cpp:8-16,48-57,59-105,109-120` — x86/Arm64 条件、転送先の値判定、probe への適用、初回評価後の cache。
- `engine/tests/quant/quant_parity.cpp:637-669` — CLI 引数の処理と起動時の `best_isa()` / arithmetic 表示。
