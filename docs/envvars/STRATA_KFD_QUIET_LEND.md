# `STRATA_KFD_QUIET_LEND`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux の HIP ビルドで対応する統合 GPU を使うとき、プロンプト処理が expert cache の slot を借りていた状態から、プロンプト専用 buffer を確保して slot を借りない方式へ切り替えるための実験用スイッチです。既定は無効です。対象のクラスで値 `1` を指定すると、条件を満たす場合に切り替えを試みます。cache の slot 数は借用ありで決めた値を維持し、専用 buffer 分の空き VRAM が不足すれば借用を続けます。生成計算や chunk の token 数自体をこの判定で変更しません（`include/strata/core/kfd_quiet.hpp:125-161`, `src/program/generate.cpp:8861-8894`）。

実際に環境から読むのは `src/program/generate.cpp:8870-8871` の `std::getenv("STRATA_KFD_QUIET_LEND")` です。共通 helper は `Fix::Lend` をこの名前に対応づけ、`lend_rule_on` が対象クラス・全体スイッチ・この変数・`STRATA_PREFILL_BORROW` を判定します（`include/strata/core/kfd_quiet.hpp:54-65,135-144`）。

## 値と判定

数値変換や文字列全体の parse は行いません。先頭 1 文字だけを検査し、大文字小文字や後続文字列の妥当性も検査しません。未設定・空文字・`1` でも `0` でもない先頭文字は、この変数単独では既定値 `false` に戻ります。`STRATA_KFD_QUIET=0` は対象変数の `1` より優先して機能を止めます（`include/strata/core/kfd_quiet.hpp:127-143`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 対象クラスで HIP/Linux 経路に入る | 既定 `false`（借用を維持） | 先頭が `1` の値（`1`, `1abc`）で、全体スイッチと借用 override が遮らない | 先頭が `0`（`0`, `0anything`）、`true`, `2`, 空文字、先頭空白の ` 1` はこの変数による有効化にならない |
| 対象外の build / GPU クラス | 読み取り経路がなく、挙動に影響しない | なし | すべて無効 |

判定順は次のとおりです。まず `STRATA_PREFILL_BORROW` の先頭が `1` なら、値が `1abc` のような場合も借用を維持します。次に `STRATA_KFD_QUIET` または対象変数の先頭が `0` なら無効です。その後、対象変数の先頭が `1` なら有効化し、それ以外は `kNoLendDefaultOn`（`false`）です。したがって `STRATA_KFD_QUIET_LEND=1` と `STRATA_KFD_QUIET=0` の併用は無効、`STRATA_KFD_QUIET_LEND=1` と `STRATA_PREFILL_BORROW=1` の併用も無効です。空白除去や警告を伴う無効値処理はありません（`include/strata/core/kfd_quiet.hpp:127-143`）。

## 有効になる条件

- ソースが `STRATA_USE_HIP` と `__linux__` の両方でコンパイルされている必要があります。LEND の判定と適用箇所はこの build 条件で囲まれています（`src/program/generate.cpp:8861-8896`）。
- 起動時に認識された GPU が統合 GPU で、アーキテクチャが `gfx1103`、`gfx1150`、`gfx1151` のいずれかである必要があります。判定 helper は Windows ではなく integrated であることを見て、この 3 アーキテクチャを許可し、HIP/Linux 経路で `class_flag` を設定します（`src/core/arch_defaults.cpp:151-158`, `src/program/generate.cpp:4074-4089,4124-4127`）。混在 GPU や別アーキテクチャは対象外です。
- prompt borrowing が既に選ばれている必要があります。コード上では `pf_borrow = !o.no_prefill_borrow && !o.expert_profile.empty()` です。従って expert profile が無い場合や `--no-prefill-borrow` 指定時は、この環境変数では有効化できません。parser に `--prefill-borrow` のような明示的な有効化引数はなく、この変数は既に成立した借用経路を条件付きで切り替えます（`src/program/generate.cpp:3851,4011,6450`）。
- `o.prefill_chunk > 0` が必要です。チャンク上限は `16384` token で、`0` 以下または `16384` 超では no-lend に切り替えません（`src/program/generate.cpp:8869`, `include/strata/core/kfd_quiet.hpp:131-133,146-161`）。
- 単一 GPU 条件（multi-GPU でない、stage がない、peer device がない、remote expert cache がない）が必要です（`src/program/generate.cpp:8872-8873`）。
- 専用 buffer の見積もりに加えて `3072 MiB` を残せる必要があります。見積もりは `bytes_needed_owned(...) >> 20` に `64 MiB` を足した値です。空き量から cache bytes、`--vram-reserve-mib`、`pipe_first` を引いた値がこの見積もりと `3072 MiB` の合計以上でなければ借用を維持します（`src/program/generate.cpp:8874-8882`, `include/strata/core/kfd_quiet.hpp:129-130,155-161`）。
- 対象変数の有効化より前に `STRATA_PREFILL_BORROW=1` が借用維持を指定できます。先頭が `1` なら値の残りに関係なく LEND の規則自体を無効にします（`include/strata/core/kfd_quiet.hpp:137-143`）。
- `STRATA_KFD_QUIET=0` はこのスイッチを含む KFD quiet の全体スイッチを止めます（`include/strata/core/kfd_quiet.hpp:47-51,135-143`）。

## 実行時の詳細

GPU を特定して `class_flag` を設定した後、expert cache の slot sizing 後に `std::getenv` で値を読み、LEND の可否と VRAM を判定します。関数内 static cache はなく、環境値はこのエンジン起動時の判定で使われます。判定後にプロセス環境を変更しても、この起動で選んだ方式は再判定されません（`src/program/generate.cpp:4124-4127,8861-8882`）。

切り替える場合は `o.no_prefill_borrow=true`、`pf_borrow=false` とし、`o.prefill_auto=false` にして、もとの `o.prefill_chunk` を維持します。専用 buffer の fit 判定は成立した場合に限り適用されるため、空き不足、chunk 条件外、単一 GPU でない場合は cache lending を継続します。既定状態または `STRATA_KFD_QUIET_LEND=1` 以外の文字列だけでは切替えません（`src/program/generate.cpp:8889-8894`, `include/strata/core/kfd_quiet.hpp:146-161`）。

## ログと測定値

`STRATA_TRACE` が設定されていて、外側の borrowing・chunk・クラス・環境スイッチ条件を通過すると、stderr に次の形式で判定が出ます（`src/program/generate.cpp:8883-8888`）。

```text
strata trace: kfd quiet: prompt path without a loan: yes (own buffers ... MiB for a ...-token chunk, ... MiB free beside the ...-slot cache and the ... MiB reserve, 3072 kept)
```

`yes` の代わりに `no, not one GPU` または `no, they do not fit` が出る場合があります。後者は fit 不足のほか、chunk が許容上限を超えて `no_lend_pick` が拒否した場合にも同じ表示です（`src/program/generate.cpp:8882-8888`, `include/strata/core/kfd_quiet.hpp:155-161`）。`STRATA_TRACE` が無い場合、この判定ログは出ません。スイッチだけを理由にしたエラー終了や警告はありません。

`docs/DETAILS.md` および関連する設計資料には、この LEND の測定値は見つかりませんでした。ソースコメントには p2006 での過去の観察値（borrowed slots 数と短い prompt ごとの時間差）が記されていますが、モデル・prompt 長などの測定条件が揃っていないため、性能値として一般化していません（`src/program/generate.cpp:8862-8868`）。

## 根拠

- 環境変数名の helper 解決、共通スイッチ、先頭文字規則、既定値、borrow override、fit 条件: `include/strata/core/kfd_quiet.hpp:47-68,125-161`。
- Linux HIP の適用箇所、単一 GPU 制約、VRAM 算出、切替後の状態変更、trace 文言: `src/program/generate.cpp:8861-8894`。
- borrow 初期状態と CLI による抑止: `src/program/generate.cpp:3851,4011,6450`。
- 対象 GPU の integrated / architecture 判定と quiet class flag: `src/core/arch_defaults.cpp:151-158`, `src/program/generate.cpp:4074-4089,4124-4127`。
