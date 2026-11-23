# `strata-hy4-metal`（Hy4-Flash / Apple Metal）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| 入口 | Apple Silicon 向け Metal 実行ファイル。`engine/src/hy4flash/metal/build_mac.sh` の `run` / `all` ターゲットが生成する |
| 主な実装 | `engine/src/hy4flash/metal/hy4_metal_main.cpp`、serve 処理は `engine/src/hy4flash/metal/hy4_metal_serve.h` |

## 役割

Hy4-Flash の `.strata` モデルを Metal runner に読み込み、トークン ID 列をオフラインで推論するか、`--serve` で標準入出力の行プロトコルを使う常駐エンジンとして推論します。起動時にはモデルをロードして Metal context とカーネルを準備し、オフライン実行では入力トークンを chunk ごとに prefill し、必要なら生成・ログ出力を行います。serve 実行では `GEN` 要求を受け付け、`QUIT` または EOF まで処理を続けます。モデル情報の表示、バージョン表示、tokenizer 関連ファイルの書き出しも別モードとして備えます。

## 基本的な使い方

```sh
# モデルファイルを開いてメタデータを表示する（GPU は使わない）
strata-hy4-metal --info /models/hy4.strata

# トークン ID を含むテキストファイルをオフラインで評価し、生成を行う
strata-hy4-metal --model /models/hy4.strata --engram /models/engram.strata \
  --tokens ./prompt-ids.txt --gen 32 --out ./run-output

# 常駐モードを起動し、標準入力の行プロトコルから要求を受け取る
strata-hy4-metal --model /models/hy4.strata --engram /models/engram.strata --serve

# モデルをロードできるかだけを確認し、ロード後に終了する
strata-hy4-metal --model /models/hy4.strata --load-only
```

オフライン実行では `--tokens` が空または読み込めない場合に `no tokens` で終了します。例の `--out` 先はあらかじめ作成してください。オフライン実行は `top5.txt`、生成時は `gen_ids.txt`、`--dump` または `--save-logits` 指定時は `logits.npy` をその出力先に書きます。既存ファイルは上書きされます。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| メタデータ表示 | `strata-hy4-metal --info MODEL.strata` | モデルファイルと sidecar manifest を読み、architecture・層数・語彙数などを 1 行で表示。GPU context 作成より前に終了する。引数なしの `--info` はビルド情報のみを表示する。 |
| バージョン表示 | `strata-hy4-metal --version` | `strata-hy4 <version>` を表示して終了する。 |
| tokenizer の書き出し | `strata-hy4-metal --export-tokenizer MODEL.strata DIR` | manifest から `tokenizer.hf.json` と `chat_template.jinja` を指定ディレクトリへ書く。出力ファイルは同名の既存ファイルを上書きする。 |
| ロード確認 | `strata-hy4-metal --model MODEL.strata --load-only` | Metal context を作成してモデルをロードし、load-only 指定があればその時点で終了する。 |
| オフライン推論（既定） | `strata-hy4-metal --model MODEL.strata --tokens IDS.txt [--gen N]` | トークン ID ファイルを prefill し、最後の位置（または `--all-logits` 指定時は全位置）の top-5 を出力する。`--gen` が正なら後続 token ID も生成する。 |
| 常駐 serve | `strata-hy4-metal --model MODEL.strata --serve` | Metal runner を初期化し、標準出力へ `INFO` と `READY` を出した後、標準入力から `GEN`、`STOP`、`QUIT` を受け取る。プロトコル出力は stdout、診断は stderr。 |

## 主な動作

- 通常の実行では最初に GPU 名、Metal 4 対応状況、buffer / working-set 上限を stderr に表示し、モデルをロードします。ロード失敗は `load: ...` を表示して終了コード 1 です。`--warm` を指定するとモデルのページを読み込み、`--load-only` を指定するとその後で終了します。
- serve 以外の通常モードでは、`--tokens` の空白区切り整数をトークン ID として読み取ります。入力が空なら終了コード 2 です。`--ctx` を正値で指定しない場合は、入力 token 数 + 生成数 + 16 を context 長にします。入力を chunk に分けて forward し、最後の chunk の logits から top-5 を標準出力へ出します。
- `--gen` によるオフライン生成は既定で greedy decode ですが、sampling 関連の CLI 値を指定するとサンプリング経路を使います。EOS に達した場合はそこで停止します。生成 token ID は標準出力と `gen_ids.txt` に出力されます。`top5.txt` は最後に常に出力され、`--dump` または `--save-logits` を指定すると `logits.npy` も保存されます。ファイル出力先は `--out`（既定 `.`）です。
- `--serve` は通常の `--tokens` 経路へ進まず、`hy4_serve_main` に処理を渡します。既定の context は 131072、chunk は cold-expert モデルで 2048、それ以外で 4096 です。開始時に `INFO` と `READY <context> stop` を stdout に出力し、要求ごとに `GEN <max_new> ... <comma-separated-ids>` を処理します。`STOP` は次の token / chunk 境界で要求を止め、`QUIT` または EOF で終了します。
- serve の要求は空 prompt や context 超過などで拒否され、エラーは `ERR ...` 行として返ります。`--draft dfly2` はモデルに drafter がなく chunk が 16 未満の場合に開始時エラーとなります。画像要求は serve 起動時に有効な Vision shard（`--vision`）が必要です。
- Metal カーネルがバイナリに埋め込まれたビルドでは、実行時にカーネル群を `${TMPDIR:-/tmp}/strata-hy4-kernels-<hash>/` へ展開します。カーネル指定は `--kernels`、`STRATA_HY4_KERNELS`、埋め込みカーネル、実行ファイル近くの `hy4.metal` の順で解決します。利用環境でカーネルをコンパイルできない場合などはロード / 初期化段階で失敗し得ます。
- `--export-tokenizer` は GPU context の作成前に処理します。指定先ディレクトリは事前に存在する必要があり、出力先を開けない場合は `cannot write ...` を表示して終了コード 1 です。`--info MODEL` も GPU を使わず、モデルを開けない場合は `open: ...` を表示して終了コード 1 です。
- 引数 parser は `--help` を特別扱いせず、未知の引数を `unknown arg ...` と stderr に出し、stdout に `ERR unknown flag ...` を出力して終了コード 2 で終了します。引数値の一般的な数値範囲チェックは parser ではなく各処理側にあります。

## オプションの文書

Metal scope のオプション一覧と各文書へのリンクは [`docs/cli/README.md`](../../README.md#strata-hy4) の `strata-hy4-metal` 節を参照してください。値や個別オプションの効果は各オプション文書に記載しています。

## 根拠

- `engine/src/hy4flash/metal/build_mac.sh:2-3,35-47` — Metal ツールの build script と `strata-hy4-metal` の生成。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1398-1433` — 埋め込みカーネルの一時ディレクトリへの展開。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1441-1481` — `--info` と `--export-tokenizer` の処理、GPU を使わない情報表示と書き込み。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1614` — parser、早期終了モード、未知引数・必須モデルの失敗経路。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1615-1675` — Metal context とモデルのロード、load-only、serve への分岐、serve 用カーネル解決。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1676-1718` — token ファイルの読み込み、画像指定、空入力エラー、context / chunk / カーネルの既定値。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1753-1782,1789-1817,1818-1848,1944-1986` — 推論初期化、prefill、top-5、sampling / greedy 生成、診断と出力ファイル。
- `engine/src/hy4flash/metal/hy4_metal_serve.h:1-9,219-256,302-365` — serve protocol、初期化と draft 条件、INFO/READY、要求の解析と代表的な失敗経路。
- 索引上の位置と scope は `docs/cli/README.md:1358-1361` を確認。コマンド概要リンクは `strata-hy4/metal/README.md`、option は同じ Metal scope に列挙されています。

調査範囲は指定 checkout の parser と実装です。実機での Metal 実行や GPU 動作は確認していません。
