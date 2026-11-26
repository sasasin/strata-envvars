# `STRATA_IGPU_DEFAULTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

統合 Radeon GPU 向けの行列コア prompt set をまとめて無効化する停止スイッチ。設定値を真偽値として parse するのではなく、値の先頭文字が `0` かを見ている。先頭が `0` なら `STRATA_IGPU_PROMPT_SET=1` より優先して set 全体を無効にする。それ以外は `STRATA_IGPU_PROMPT_SET` と OS・GPU に応じた既定判定へ進む（`engine/src/core/arch_defaults.cpp:124-138`）。

set が有効な場合、Strata は対象の prompt 用環境変数を、まだプロセス環境に存在しないものだけ設定する。通常の対象は `STRATA_HIP_WMMA`、`STRATA_PF_GEMM`、`STRATA_PA_FAST`、`STRATA_SELECT_WMMA`、`STRATA_HC_UPMIX`。Windows の `gfx1151` では `STRATA_SELECT_WMMA` を含む12個の表に差し替わる（`engine/src/core/arch_defaults.cpp:172-215,406-421`）。

## 値と判定

この変数に「有効化する値」はない。`getenv` の結果が非 null で、最初の文字が `0` のときだけ全体を止める。文字列全体の比較、数値変換、空白除去、大文字小文字変換はしない（`engine/src/core/arch_defaults.cpp:124-129`）。

| 条件 | unset | 設定時に停止する値 | 設定しても停止しない値 |
|---|---|---|---|
| `igpu_prompt_set_enabled` を呼ぶ経路 | `STRATA_IGPU_PROMPT_SET` と OS・GPU の既定判定へ進む | 先頭が `0`（`0`, `00`, `0anything`） | 空文字、`1`, `true`, `false`, ` 0`, `anything` など。これらは次の判定へ進む |

停止しない値の場合、続いて `STRATA_IGPU_PROMPT_SET` を同じく先頭文字だけで判定する。先頭 `1` なら有効、先頭 `0` なら無効。それ以外（unset、空文字を含む）は OS・GPU 既定へ進む。したがって `STRATA_IGPU_DEFAULTS=0` は `STRATA_IGPU_PROMPT_SET=1` を上書きして停止し、逆に `STRATA_IGPU_DEFAULTS=1` は prompt set を強制有効化せず、次の変数・既定判定に委ねる（同 `:124-138`）。

## 有効になる条件

全て満たす必要がある。

- HIP の通常の生成経路で、デバイス情報取得が成功し、`apply_arch_defaults` が呼ばれること。呼び出しは `STRATA_USE_HIP` ビルド条件内にある（`engine/src/program/generate.cpp:4287-4320`）。
- 使用 GPU が統合 GPU で、アーキテクチャが `gfx1103`、`gfx1150`、`gfx1151` のいずれかであること。複数 GPU の場合、この呼び出し元は device 0 と device 1〜63 を調べ、それらが統合 GPU かつ device 0 と同じ先頭7文字の arch 名であるときだけ `integrated=true` を渡す（64台を超える場合、index 64 以降はこの判定ループの対象外。同 `:4291-4302,4320`; 対象 arch は `engine/src/core/arch_defaults.cpp:119-121,172-180`）。
- `STRATA_IGPU_DEFAULTS` の先頭が `0` でないこと。
- `STRATA_IGPU_PROMPT_SET` が先頭 `0` でなく、またはその変数が set を有効化する値であること。set の既定有効は Linux の `gfx1103` と Windows の `gfx1151`。他の対象 arch / OS の組み合わせは既定で無効（同 `:127-138`）。

CUDA 生成経路はこの HIP 条件付き初期化を通らない。SYCL 側にある呼び出しは `apply_arch_defaults(ad.gcnArchName)` と1引数で、宣言上 `integrated` は既定値 `false` のため、この iGPU set は適用されない（`engine/sycl/src/program/generate.cpp:2223-2229`; `engine/include/strata/core/arch_defaults.hpp:157-162`）。CPU / Metal についても、この iGPU 用の呼び出し経路は確認できない。

対象変数自体が無効条件となるほか、個別の set 変数が環境に既に存在すれば値が何であっても Strata は上書きしない。空文字や `0` も「ユーザー設定あり」として保持される（`engine/src/core/arch_defaults.cpp:406-410,218-223`）。

## 実行時の詳細

`STRATA_IGPU_DEFAULTS` は `igpu_prompt_set_enabled` の呼び出しごとに `std::getenv` で読み、static cache はない。通常の HIP 生成経路では CLI 引数を処理した後、エンジンが各スイッチを読む前の初期化中に一度 `apply_arch_defaults` から評価される（`engine/src/program/generate.cpp:4287-4320`; 適用順の説明は `engine/include/strata/core/arch_defaults.hpp:157-162`）。CLI 引数との上書き関係はなく、別の環境変数 `STRATA_IGPU_PROMPT_SET` が次の判定を担う。

set が有効なら、Strata は表の各名前について `getenv(...) != nullptr` のものを維持し、未設定のものだけ値を設定する。Windows では `_putenv_s`、それ以外では `setenv(..., 0)` を使ってプロセス環境へ設定する。この処理後に `STRATA_IGPU_DEFAULTS` を変更しても、すでに挿入された個別スイッチは取り消されない（`engine/src/core/arch_defaults.cpp:218-223,406-421`）。通常経路での起動後再評価や子プロセスへの引き渡しは、この実装からは確認できない。

通常の表は5スイッチをすべて `1` にする。Windows の `gfx1151` は12スイッチに差し替わり、`STRATA_PF_F16` は `2`、残りは `1`（`engine/src/core/arch_defaults.cpp:183-213`）。スイッチ値をすでに設定している場合は、その値を保持するため一部だけが適用されることもある。

## ログと測定値

少なくとも1個のスイッチを新たに設定した場合、stderr に `strata: integrated GPU (%s): the matrix-core prompt set is on (1.6x to 2x faster prompts on a Radeon 780M, the answers differ in the last bits): ` で始まる行を出し、今回設定した名前を並べる。末尾は `Turn one off with NAME=0 (for example STRATA_HC_UPMIX=0), all of them with STRATA_IGPU_PROMPT_SET=0`。Windows ビルドではさらに `.  Not yet tested on Windows` を付加する。全スイッチがすでに環境にある場合、または set が無効ならこの行は出ない（`engine/src/core/arch_defaults.cpp:406-420`）。この文言中の性能値はログ文字列であり、本調査で再測定した値ではない。

## 根拠

- `engine/src/core/arch_defaults.cpp:124-138` — 対象変数の値判定、`STRATA_IGPU_PROMPT_SET` との優先順位、OS / arch の既定。
- `engine/src/core/arch_defaults.cpp:172-215` — 統合 GPU・対象 arch 条件、通常表と Windows `gfx1151` 表。
- `engine/src/core/arch_defaults.cpp:218-223,302-310,406-421` — 環境への反映とログ。
- `engine/src/program/generate.cpp:4287-4320` — HIP 生成経路での GPU 検出と適用時点。
- `engine/sycl/src/program/generate.cpp:2223-2229`, `engine/include/strata/core/arch_defaults.hpp:157-162` — SYCL 呼び出しと `integrated` 引数の既定値。
