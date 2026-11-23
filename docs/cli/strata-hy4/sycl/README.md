# `strata-hy4-sycl`（SYCL）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl` |
| 入口 | `strata-hy4-sycl` 実行ファイル |
| 主な実装 | `engine/src/hy4flash/sycl/sy_main.cpp`、serve 処理は `engine/src/hy4flash/sycl/sy_serve.h` |

## 役割

Hy4-Flash の `.strata` モデルを SYCL バックエンドで読み込み、トークン ID ファイルからの一括 prefill・任意の生成、または Strata エンジンの標準入出力 line protocol による常駐生成を行う実行ファイルです。モデル情報の表示と tokenizer / chat template の書き出しも備えます。SYCL ビルドスクリプトは oneAPI `icpx` を使い `strata-hy4-sycl` を生成し、Alchemist / Battlemage 向けのビルドモードを用意しています（`engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-6,62-68`）。

## 基本的な使い方

```sh
# モデル情報を表示する（モデル指定なしの概要。GPU の初期化は行わない）
strata-hy4-sycl --info

# トークン ID を prefill し、続けて greedy で最大 32 token 生成する
strata-hy4-sycl --native ./model.strata --tokens ./prompt.ids --gen 32

# モデルをロードして初期化経路を確認し、推論せず終了する
strata-hy4-sycl --native ./model.strata --load-only

# 常駐 line protocol を起動し、1 件生成して終了する
printf 'GEN 16 1,2,3\nQUIT\n' | strata-hy4-sycl --serve --native ./model.strata --engram ./engram.strata
```

`--tokens` のファイルは空白区切りの整数として読み込まれます。通常実行では最後に `top5.txt` を `--out` のディレクトリ（省略時はカレントディレクトリ）へ書きます。生成を行う場合はさらに `gen_ids.txt` を書き、`--dump` 指定時は `logits.npy` も出力します。出力先ディレクトリはこの処理では作成されないため、事前に用意してください（`engine/src/hy4flash/sycl/sy_main.cpp:266-275,283-289,355-364,527-606`）。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| メタデータ・バージョン確認 | `strata-hy4-sycl --info [FILE.strata]` / `strata-hy4-sycl --version` | `--info` はモデル指定なしならエンジン能力の key=value 行を、ファイル指定時は vision shard またはモデル manifest の情報を出力します。ファイルを開く経路は GPU 実行へ進みません。`--version` はバージョンを表示して終了します。 |
| tokenizer 書き出し | `strata-hy4-sycl --export-tokenizer FILE.strata DIR` | `.strata` の manifest から tokenizer JSON と chat template を取り出し、`DIR/tokenizer.hf.json` と `DIR/chat_template.jinja` に書きます。出力先ディレクトリは作成せず、開けない場合や書き込みに失敗した場合は stderr にエラーを出して終了コード 1 になります。 |
| 一括実行 | `strata-hy4-sycl --native FILE.strata --tokens ids.txt [--gen N]` | モデルと実行環境を初期化し、トークン列を chunk ごとに prefill します。`--gen` が正なら greedy decode し、生成 ID を出力します。`--load-only` ではモデル・runner・expert pool などの初期化後、token file の読み込みと推論を行わず終了します。 |
| 常駐 line protocol | `strata-hy4-sycl --serve --native FILE.strata --engram FILE.strata` | 起動時にモデル等を初期化して stdout に `INFO` と `READY` を出し、stdin の `GEN ...` 要求を順に処理します。`STOP` は実行中要求を境界で中断し、`QUIT` または EOF でプロセスを終了します。ネットワーク待受ではなく標準入出力を使います。 |

## 主な動作

引数を走査して `--serve`、モデル、実行設定などを決めます。`--info`、`--version`、`--export-tokenizer` は通常の推論初期化より前に終了する専用経路です。通常経路では `--native` または同義の `--model` でモデルを選び、GPU 情報を stderr に表示してモデルをロードします。`--load-only` 以外は `--tokens` の整数列を読み、空なら `no tokens` を stderr に出して終了コード 2 です。prefill 後、必要なら生成し、進捗や診断値は主に stderr、top-5 行と生成 ID は stdout に出します（`engine/src/hy4flash/sycl/sy_main.cpp:105-197,250-297,338-373,527-616`）。

serve 経路では `--native` が必須です。設定を `ServeOpts` に渡し、モデル、Engram、expert pool、必要な Vision shard 等を初期化した後、stdout に `INFO` / `READY` を出して要求ループに入ります。要求ごとに `GEN <max_new> [key=value ...] <id>,<id>,...` を読み、prefill と token 生成の進捗を `PP` / `T` / `DONE` 行で返します。`--session-reuse` が有効な場合は、前回 prompt の完全一致 prefix など条件を満たす要求で KV cache を再利用します（`engine/src/hy4flash/sycl/sy_serve.h:28-48,236-338,408-427,451-527`）。

起動時に `UR_LOADER_USE_LEVEL_ZERO_V2` が未設定なら `0` を設定します。`ONEAPI_DEVICE_SELECTOR` が未設定の場合は `HY4S_BACKEND=opencl` に応じた OpenCL GPU、または既定の Level Zero GPU を選択する値を設定します。利用者が `ONEAPI_DEVICE_SELECTOR` を設定済みならその値を維持します（`engine/src/hy4flash/sycl/sy_main.cpp:79-92`）。

## 注意点

- この実行ファイルは `--help` を専用処理していません。引数なしでは usage を stderr に出して終了コード 2、未対応引数も `unknown arg` として終了コード 2 になります（`engine/src/hy4flash/sycl/sy_main.cpp:190-197,250-254`）。
- `--warm` は parser でフラグを受け取りますが、この revision の通常経路では変数を未使用として破棄しており、効果は確認できません（`engine/src/hy4flash/sycl/sy_main.cpp:99,161,318`）。
- `--export-tokenizer` は指定ディレクトリに既存ファイルがあれば `wb` で開くため上書きします。またディレクトリ自体は作りません（`engine/src/hy4flash/sycl/sy_main.cpp:19-41`）。
- コードは SYCL 例外を通常経路では stderr に出して終了コード 4、serve 経路では protocol の `ERR sycl: ...` を stdout に出して終了コード 1 とします（`engine/src/hy4flash/sycl/sy_main.cpp:612-615`、`engine/src/hy4flash/sycl/sy_serve.h:532-535`）。

## オプションの文書

SYCL 版の parser scope と個別オプション文書は[CLI 索引の `strata-hy4-sycl` 節](../../README.md)を参照してください。主な関連項目: [`--native`](--native.md)、[`--tokens`](--tokens.md)、[`--gen`](--gen.md)、[`--load-only`](--load-only.md)、[`--serve`](--serve.md)、[`--info`](--info.md)、[`--export-tokenizer`](--export-tokenizer.md)、[`--out`](--out.md)、[`--dump`](--dump.md)。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:1,79-105` — 実行ファイルの役割・起動時の環境設定・parser 初期値。
- `engine/src/hy4flash/sycl/sy_main.cpp:105-197,215-254` — 引数処理、serve 分岐、必須モデル確認、usage と失敗コード。
- `engine/src/hy4flash/sycl/sy_main.cpp:19-67` — tokenizer 書き出しと `--info` の実装。
- `engine/src/hy4flash/sycl/sy_main.cpp:255-337,338-373,527-616` — モデル初期化、一括 prefill / 生成、出力ファイルと例外処理。
- `engine/src/hy4flash/sycl/sy_serve.h:28-48,236-338,335-390,408-527,528-535` — serve の設定、初期化、標準入出力 protocol、画像・要求処理、終了経路。
- `engine/src/hy4flash/sycl/build_hy4_sycl.sh:1-6,62-68` — SYCL 実行ファイルの名称、対象アーキテクチャ、生成物。
