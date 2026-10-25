# `STRATA_IGPU_DEFAULTS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

統合 AMD GPU 向けの「matrix-core prompt set」をまとめて無効にするスイッチです。対象セットは `STRATA_HIP_WMMA`、`STRATA_PF_GEMM`、`STRATA_PA_FAST`、`STRATA_SELECT_WMMA`、`STRATA_HC_UPMIX` の5個で、適用されると未設定の変数だけを値 `1` にします。通常の gfx1151 / gfx12 アーキテクチャ既定値テーブル全体を止める変数ではありません。

## 値と判定

| `STRATA_IGPU_DEFAULTS` | 結果 |
|---|---|
| 未設定 | 他の条件と `STRATA_IGPU_PROMPT_SET` に従う |
| 空文字 | 無効化しない（設定値の先頭文字が `\0`） |
| 先頭文字が `0`（例: `0`, `0anything`） | prompt set を無効化する |
| それ以外（例: `1`, `true`, `false`, ` 0`） | 無効化しない |

文字列全体の parse や数値変換はなく、先頭文字だけを大文字小文字区別ありで比較します。無効化判定は `STRATA_IGPU_PROMPT_SET` より先に行われるため、`STRATA_IGPU_DEFAULTS=0 STRATA_IGPU_PROMPT_SET=1` でも set は無効です。

## 有効になる条件

この変数が無効化する set が適用されるのは HIP ビルドです。`src/program/generate.cpp` は HIP の場合にデバイス 0 の GPU 情報を取得し、統合 GPU かつ対象アーキテクチャであることを調べてから既定値を適用します。複数 GPU がある場合、見えている全 GPU が統合 GPU で、先頭7文字の GCN アーキテクチャ名も一致するときだけ `all_igpu` が真になります。離散 GPU が同居する構成では set は適用されません。

対象アーキテクチャは `gfx1103`、`gfx1150`、`gfx1151` です。既定で有効なのは Linux の統合 `gfx1103` のみです。他の対象アーキテクチャでは `STRATA_IGPU_PROMPT_SET` の先頭文字が `1` なら opt-in できますが、`STRATA_IGPU_DEFAULTS` の先頭文字が `0` なら opt-in よりも優先して無効になります。Windows では既定で有効にならず、AMD_HIP の説明では未テストとされています。

## 実行時の詳細

判定箇所は `igpu_prompt_set_enabled()` で、環境をその呼び出し時に読みます。`apply_arch_defaults()` は `strata generate` の引数処理後、GPU の既定値を各エンジン機能が読む前に実行されます。環境変数は static cache されていません。プロセス起動後に値を変更した場合に再評価されるかどうかは、この起動時の呼び出し経路からは通常の生成処理で再評価されないと判断できます。

prompt set が有効なら5個のスイッチを順に確認し、環境にすでに存在するものは値が空でも `0` でも上書きせず、それ以外を `1` に設定します。1個以上を設定したときは stderr に `strata: integrated GPU (<arch>): the matrix-core prompt set is on ...` の行を出力します。ログには各スイッチ名が並び、Windows ビルドでは `Not yet tested on Windows` も付加されます。

`STRATA_IGPU_DEFAULTS` は `arch_default_env()` の gfx1151 / gfx12 テーブルを参照しません。そのテーブルは `STRATA_GFX1151_DEFAULTS` / `STRATA_GFX12_DEFAULTS` が制御します。また、この変数は UMA arena の登録方法を制御しません。

## 文書との照合

`docs/AMD_HIP.md` は set の対象、個別スイッチ、`STRATA_IGPU_PROMPT_SET` との関係、およびこの変数が set 全体を無効にする点を記述しており、現行コードと一致します。同文書にある Radeon 780M の性能値や出力差の説明は同文書記載の測定報告であり、本調査で測定を再実施したものではありません。

## 根拠

- `src/core/arch_defaults.cpp:62-74` — 先頭文字による無効化、`STRATA_IGPU_PROMPT_SET` との優先順位、gfx1103/Linux の既定条件。
- `src/core/arch_defaults.cpp:88-107` — 統合フラグとアーキテクチャ条件、set を構成する5変数。
- `src/core/arch_defaults.cpp:117-150` — 既存環境値の保持、未設定値への `1` の設定、stderr ログ。
- `src/program/generate.cpp:2769-2786` — HIP ビルドでの起動時呼び出しと全 GPU の統合・アーキテクチャ確認。
- `include/strata/core/arch_defaults.hpp:28-33,43-54` — 既定値と適用関数の説明。
- `docs/AMD_HIP.md:598-630` — 利用者向け説明と測定報告。
