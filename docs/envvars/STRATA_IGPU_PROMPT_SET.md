# `STRATA_IGPU_PROMPT_SET`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

HIP エンジンの統合 Radeon 向けに、プロンプト処理用の行列コア設定5個をまとめて有効・無効にします。対象は `STRATA_HIP_WMMA`、`STRATA_PF_GEMM`、`STRATA_PA_FAST`、`STRATA_SELECT_WMMA`、`STRATA_HC_UPMIX` です。これらはプロンプト側の演算設定で、個別に値が既に設定されているものはこの処理では上書きされません。

## 値と判定

Strata は値全体や数値としての妥当性を parse せず、先頭文字だけを調べます。空文字は `getenv` 上は設定済みですが、`e[0]` は `\\0` なので下表の「その他」に該当します。

| `STRATA_IGPU_PROMPT_SET` | 判定 |
|---|---|
| 未設定 |既定条件に従う（Linux の `gfx1103` のみ ON） |
| 先頭文字が `1` | ON。`1`, `10`, `1anything` など |
| 先頭文字が `0` | OFF。`0`, `0anything` など |
| 空文字、または先頭文字が `1` / `0` 以外 | 既定条件に従う。例: `true`, `false`, ` 1` |

ただし先に `STRATA_IGPU_DEFAULTS` を確認し、その先頭文字が `0` なら本変数の値にかかわらず OFF です。`STRATA_IGPU_DEFAULTS` の空文字や先頭が `0` 以外の値は、この全体 OFF 条件を満たしません。

## 有効になる条件

- `STRATA_USE_HIP` でビルドされた `strata generate` の経路で適用されます。CUDA / Metal の経路ではこの既定値設定呼び出しはありません。
- 選択デバイスのアーキテクチャが `gfx1103`、`gfx1150`、`gfx1151` のいずれかであり、デバイスプロパティの `integrated` が真である必要があります。アーキテクチャ名は完全一致で判定します。
- さらに、可視 GPU がすべて統合型で、先頭 GPU と同じアーキテクチャである必要があります。混在構成、異なるアーキテクチャ、または追加デバイスの照会失敗では `all_igpu` が偽になり、セットは適用されません。
- 本変数が未設定、空文字、または先頭文字が `0` / `1` 以外の場合の既定 ON は Linux の `gfx1103` だけです。Windows と `gfx1150` / `gfx1151` は既定 OFF です。先頭が `1` なら対象アーキテクチャの統合 Radeon で opt-in できます。
- `STRATA_IGPU_DEFAULTS` の先頭が `0` なら、上記 opt-in も含めて全体を無効にします。
- 個別5変数が既に設定されている場合は、その値を空文字も含めて保持します。たとえば個別変数を `0` に設定すれば、その設定はセットから除外されます。

## 実行時の詳細

`strata generate` は CLI 引数処理後、モデル／エンジン側が各スイッチを初回参照する前に GPU プロパティを調べ、`apply_arch_defaults()` を呼び出します。通常の実行ではこの判定は生成処理の初期化時に一度行われます。`igpu_prompt_set_enabled()` 自体は `getenv()` の値を static cache せず呼び出し時に読みますが、適用済み設定はプロセス環境に反映されます。

有効条件を満たすと、未設定の個別スイッチへ `"1"` を設定します。POSIX では `setenv(..., 0)` を使い既存値を上書きせず、Windows では既存変数の上書きを避けたループの後に `_putenv_s()` を呼びます。1個以上設定した場合は stderr に `strata: integrated GPU (%s): the matrix-core prompt set is on ...` の行を出し、設定したスイッチ名と停止方法を表示します。何も新たに設定しなかった場合は、この処理からの有効化ログは出ません。

`docs/DETAILS.md` はこのセットが演算の丸め方を変え、測定は Radeon 780M に限られると記しています。そこに記載された測定は P2006 / Q2_0 / `--kv int8` の4K prompt で、最初の4スイッチ有効時 109.5→214.7 tok/s、5個すべてで 233 tok/s、decode は 16.6 対 17–19 tok/s とされています。別節の 6 組 interleaved 測定では 1K が 98.5→157.3 tok/s、4K が 115.1→233.3 tok/s で greedy token ids が全組一致と記載されています。これらは資料記載の条件と結果であり、他環境の性能・出力を保証するものではありません。

## 根拠

- `src/core/arch_defaults.cpp:62-74`: 対象アーキテクチャ判定、全体 OFF の優先、先頭文字判定、プラットフォーム別の既定値。
- `src/core/arch_defaults.cpp:88-107`: 統合 GPU 条件と有効化される5変数。
- `src/core/arch_defaults.cpp:109-148`: 未設定変数への値設定、stderr ログ。
- `src/program/generate.cpp:2769-2798`: HIP ビルド条件、全可視 GPU の integrated / architecture 判定、既定値の適用時期。
- `include/strata/core/arch_defaults.hpp:24-54`: 対象アーキテクチャと挙動の宣言・説明。
- `docs/DETAILS.md:598-630`、`docs/RADEON_780M.md:82-90`: 適用対象、個別設定、丸め差、測定条件と資料上の測定値。
