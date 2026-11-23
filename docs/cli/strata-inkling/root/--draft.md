# `--draft`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（root。特に `--serve` と `--bench`） |
| オプション | `--draft` |
| 別名 | なし |
| 値 | 文字列。help に記載された値は `auto`、`dspark`、`off` |

## 役割

Inkling-2-Mini の DSpark speculative drafter を有効にするか選びます。値が正確に `off` の場合は backend に DSpark を有効化しないよう渡し、それ以外の値では有効化を試みます。`--serve` ではさらにモデルに drafter があり backend が利用可能と判定した場合にのみ、実際の speculative decoding が有効になります。既定値は `auto` です。parser は `auto` / `dspark` / `off` 以外の値を拒否せず、`auto` と `dspark` も同じ有効化経路に入ります。`engine/src/inkling2/ink_main.cpp:371-377,428-430`、help 表示は同 `:488-498`。

## 使い方

```sh
# serve で DSpark を自動利用（既定値も auto）
strata-inkling --serve --native model.strata --draft auto

# serve で DSpark を無効化
strata-inkling --serve --native model.strata --draft off

# 明示した DSpark ファイルを指定して serve（ファイルの読み込み指定は --dspark）
strata-inkling --serve --native model.strata --dspark ./mtp.safetensors --draft dspark
```

## 値と既定値

- `--draft` を省略すると `ServeConfig::draft_mode` の初期値 `auto` が使われます（`engine/src/inkling2/ink_serve.h:431-439`）。
- `auto`、`dspark` は `off` 以外なので `BackendOpts::enable_dspark` を `true` にします。`off` は `false` にします（`engine/src/inkling2/ink_main.cpp:428-430`）。
- 値の列挙による検証や大小文字変換はありません。例えば `--draft anything` も受理され、`auto` / `dspark` と同様に有効化を試みます（同 `:428-430`）。複数回指定した場合は parser が順に読み、最後に指定した値が設定に残ります（同 `:379-384,428-430`）。
- 値を省略すると `missing value after --draft` を stderr に出して終了コード `2` で終了します（同 `:381-384`）。

## 実行時の動作

`--serve` では `run_serve_loop` が `draft_mode != "off"`、読み込んだモデルの `dspark.present`、backend の `dspark_ready()` の三条件をすべて確認して利用可否を決めます。したがって `auto` と `dspark` は同じ動作で、モデルに drafter がない場合や backend が準備できない場合は drafting が `off` になります。起動時の `INFO` 行にはモデル内 drafter の有無と実際の drafting 状態が別々に出ます（`engine/src/inkling2/ink_serve.h:441-446,479-485`）。有効な場合、単一リクエストの greedy 経路などで speculative step を使い、通常の batch 経路では tap capture を有効にします（同 `:762-775,883-887`）。

`--bench` では同じ `enable_dspark` 値が benchmark に渡されます。単一 slot では生成中に speculative greedy step を試し、複数 slot では batch の tap capture を有効にします（`engine/src/inkling2/ink_main.cpp:130-145,194-229,549`）。通常の直接生成モードでは `enable_dspark` に応じて tap capture を設定しますが、その生成ループは通常の logits sampling と forward を繰り返し、DSpark speculative step を呼びません（同 `:575-613`）。

モデルを開く処理は backend 初期化より前に行われ、指定された `--dspark` のパスは `--draft off` でも `InkModelFile::open` に渡されます（`engine/src/inkling2/ink_main.cpp:556-565`）。明示パスが空なら loader はモデルのディレクトリから `mtp.safetensors` または名前に `dspark` を含む `.gguf` を探します。したがって `off` は backend の drafter 利用を止めますが、モデル/sidecar の探索や読み込み自体を省略する指定ではありません（`engine/src/inkling2/ink_gguf_loader.h:689-717`）。

## 適用条件と副作用

- 本文書の scope は索引が示す CUDA/HIP の `strata-inkling` root parser です。Metal / SYCL の別 parser もありますが、別の option scope として索引に分かれています（`docs/cli/README.md:1509-1518,1549-1555,1572-1578`）。
- backend は `enable_dspark` とモデル中の DSpark の有無を見て drafter を初期化します。CUDA では有効時にモデル読み込み時の VRAM 見積もりに DSpark 分を含め、条件が合えば初期化します（`engine/src/inkling2/cuda/ink_cuda_backend.cu:182-198,243-246`）。CPU backend も同じ enable フラグとモデル設定で DSpark tensor を有効化します（`engine/src/inkling2/ink_cpu_backend.cpp:221-229`）。
- `--draft` 自体の値に対する validation error はありません。値なしの場合は上記の終了コード `2`、未知のオプションは `unknown option` を stderr に出して `2` で終了します（`engine/src/inkling2/ink_main.cpp:381-384,499-501`）。モデル open や backend init が失敗した場合は `--serve` ならプロトコルの `ERR open` / `ERR init`、それ以外では stderr にエラーを出し、終了コード `1` です（同 `:556-568`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:371-384,428-432` — 既定設定、値取得、値検証がないこと、`--dspark` との隣接する parser 定義。
- `engine/src/inkling2/ink_main.cpp:488-501,540-572` — help の値表記、モード分岐、モデル open / backend init とエラー経路。
- `engine/src/inkling2/ink_main.cpp:130-145,194-229,575-613` — benchmark と直接生成時の設定・使用経路。
- `engine/src/inkling2/ink_serve.h:431-446,479-485,762-775,883-887` — serve の有効条件、起動状態表示、speculative step と tap capture。
- `engine/src/inkling2/ink_gguf_loader.h:689-717` — sidecar の自動探索と safetensors 読み込み開始。
- `engine/src/inkling2/cuda/ink_cuda_backend.cu:182-198,243-246`、`engine/src/inkling2/ink_cpu_backend.cpp:221-229` — backend における DSpark 有効化。
