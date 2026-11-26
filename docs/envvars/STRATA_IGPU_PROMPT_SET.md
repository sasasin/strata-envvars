# `STRATA_IGPU_PROMPT_SET`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

統合型 Radeon の prompt 用 matrix-core 設定群を、機種・OSごとの既定値から上書きして有効／無効にする。変数自身がカーネルを切り替えるのではなく、HIP エンジンの起動時に `STRATA_HIP_WMMA`、`STRATA_PF_GEMM`、`STRATA_PA_FAST`、`STRATA_SELECT_WMMA`、`STRATA_HC_UPMIX`（通常のセット）などを、未設定の場合に値 `1` でプロセス環境へ追加する。Windows の統合 `gfx1151` では追加項目があり、`STRATA_PF_FUSED`、`STRATA_PF_F16` などもセットに含む。これらの個別設定が実際に有効になるかは各設定の実装条件にも従う。`STRATA_IGPU_DEFAULTS=0` は本変数の指定より優先してセットを無効にする。実装は `igpu_prompt_set_enabled` と `igpu_default_env`（`engine/src/core/arch_defaults.cpp`）。

本番での呼び出しは `STRATA_USE_HIP` のビルドに限られ、CLI 引数の解析後、GPU 情報取得時に起動プロセス内で一度 `apply_arch_defaults` を呼ぶ。CUDA / SYCL の通常経路はこの処理を呼ばない（`engine/src/program/generate.cpp:4287-4320`、`engine/sycl/src/program/generate.cpp:2223-2228`）。

## 値と判定

`std::getenv` で取得し、文字列全体や数値としては parse せず先頭 1 byte だけを見る。先に `STRATA_IGPU_DEFAULTS` の先頭が `0` なら常に無効。その後、本変数の先頭が `1` なら有効、`0` なら無効。それ以外（未設定、空文字を含む設定値、未知の先頭文字）は OS・architecture の既定規則へ進む。したがって `1anything` は有効、`0anything` は無効、`true` と `false` はどちらも既定規則、` 1` も既定規則になる。大文字小文字、空白除去、数値妥当性の検証はない（`engine/src/core/arch_defaults.cpp:124-138`）。

| 条件（統合 Radeon であることは別途必要） | unset / 空文字 / その他の先頭文字 | 先頭 `1` | 先頭 `0` |
|---|---|---|---|
| `STRATA_IGPU_DEFAULTS` の先頭が `0` | 無効 | 無効 | 無効 |
| Linux `gfx1103` | 有効（既定 ON） | 有効 | 無効 |
| Windows `gfx1151` | 有効（既定 ON） | 有効 | 無効 |
| その他の対象 arch（`gfx1150`、Linux `gfx1151` を含む） | 無効（既定 OFF） | 有効 | 無効 |
| 対象外 arch、非統合 GPU、HIP 以外の起動経路 | 適用されない | 適用されない | 適用されない |

対象 arch の判定は `gfx1103`、`gfx1150`、`gfx1151`。ただし arch 名が一致しても、`integrated` が false なら設定群は空になる。`STRATA_IGPU_DEFAULTS` の判定も `integrated` と arch の条件を通った後に行われる（`engine/src/core/arch_defaults.cpp:119-138,172-180`）。

## 有効になる条件

- HIP ビルドで `STRATA_USE_HIP` が定義され、デバイス情報の取得に成功して `apply_arch_defaults` が呼ばれること。失敗時は呼び出し自体がなく、この変数による既定値設定もない（`engine/src/program/generate.cpp:4287-4320`）。
- 対象 arch は `gfx1103` / `gfx1150` / `gfx1151` で、かつ選択 GPU が統合型として判定されること。起動コードは最初の GPU の `integrated` を確認し、追加 GPU は最大 index 63 まで、統合型かつ arch 名の先頭 7 文字が最初の GPU と同じかを確認する。これらの条件を満たさないと `all_igpu` が false になり、セットは適用されない（`engine/src/program/generate.cpp:4291-4302`）。
- `STRATA_IGPU_DEFAULTS` が設定されていて先頭文字 `0` でないこと。空文字や `0abc` 以外の値はこの全体停止条件にはならない（`engine/src/core/arch_defaults.cpp:124-126`）。
- 本変数が有効扱いとなるか、機種／OS既定が ON であること。Linux `gfx1103` と Windows `gfx1151` は unset 時に ON、Windows `gfx1103`、`gfx1150`、Linux `gfx1151` は unset 時に OFF（`engine/src/core/arch_defaults.cpp:130-138`）。
- 個別スイッチが既に環境に存在する場合はそのスイッチを上書きしない。値が空文字でも存在するだけで保持されるため、その項目についてセットの `1` は設定されない（`engine/src/core/arch_defaults.cpp:406-410,218-223`）。個別スイッチの値の意味は各スイッチ側の判定による。

モデル状態や CLI オプションによる本変数の追加ゲートは `apply_arch_defaults` までの経路にはない。`--batch` は同関数へ別目的の引数として渡されるだけで、iGPU prompt set 判定には使われない（`engine/src/program/generate.cpp:4320`、`engine/src/core/arch_defaults.cpp:172-180`）。

## 実行時の詳細

CLI 引数解析後、HIP デバイス情報取得後の初期化で helper が本変数を読み、条件が成立すれば個別スイッチの既定値を `setenv(..., 0)`（Windows は `_putenv_s`）でプロセス環境へ設定する。既存の個別変数は保持される。変数の読み取り箇所に `static` cache はなく、関数呼び出し時に環境を読む。通常の生成起動経路では `apply_arch_defaults` をこの位置で一度呼ぶ。設定後にプロセス環境を変更しても、すでに実施された既定値注入は遡って変わらない。個別スイッチ側には初回利用時に `static` cache する実装もあるため、以降の切替反映はそれぞれのスイッチ実装に依存する（例: `engine/src/kernels/cuda/qsa_prompt_attn.cu:2348`）。

この関数は prompt の計算を直接実行せず、環境値を通じて後段の個別機能を選択させる。通常の統合 GPU 向けセットの構成は上記 5 項目。Windows `gfx1151` の場合は 12 項目に拡張される。新規に設定した項目が一つ以上あると stderr に起動メッセージを出し、個別設定が事前にすべて存在する場合はこのメッセージも出ない（`engine/src/core/arch_defaults.cpp:183-214,406-420`）。

## ログと測定値

セットの項目を新規設定した場合、stderr に `strata: integrated GPU (%s): the matrix-core prompt set is on ...` で始まり、設定したスイッチ名と `all of them with STRATA_IGPU_PROMPT_SET=0` を含む行が出る。Windows ではさらに `.  Not yet tested on Windows` が付く。すべての個別設定が既にあればこの行は出ない。ソース内の表示文字列は Radeon 780M での prompt 性能差を案内するが、測定値は機種・条件つきで読む必要がある（`engine/src/core/arch_defaults.cpp:412-420`）。

資料では Radeon 780M `gfx1103`、Linux、Q2_0、`--kv int8` の測定として、個別スイッチなしの prompt 109.5 tok/s、最初の4項目で214.7 tok/s、5項目すべてで233 tok/s（1回ずつ）を記載する。別の6組 interleaved 測定では1K prompt x1.60、4K x2.03、decode x0.999、greedy token id は全組一致と報告される。これは資料にある測定結果で、他機種・モデルへの一般化ではない（`docs/AMD_HIP.md:445-474`）。

## 根拠

- `engine/src/core/arch_defaults.cpp:119-138` — 対象 arch、`STRATA_IGPU_DEFAULTS` の優先、対象変数の先頭文字判定と OS／arch 既定値。
- `engine/src/core/arch_defaults.cpp:172-215` — 統合 GPU 条件、設定群の内容と Windows `gfx1151` の追加項目。
- `engine/src/core/arch_defaults.cpp:218-223,302-312,406-420` — 個別環境変数の既存値を保つ処理、プロセス環境への設定と stderr ログ。
- `engine/src/program/generate.cpp:4287-4320` — HIP 起動時の呼び出し、デバイス統合判定と複数 GPU 条件。
- `engine/sycl/src/program/generate.cpp:2223-2228` — 同じ `STRATA_USE_HIP` guard 下にある別起動経路。
- `engine/include/strata/core/arch_defaults.hpp:41-50,112-117,157-162` — 宣言と既定規則の補足。
- `docs/AMD_HIP.md:445-474` — 対応クラスと条件つきの測定結果。
