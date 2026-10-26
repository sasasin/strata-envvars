# `strata-q36ref`

調査対象: Strata commit `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-q36ref` |
| コマンド | `strata-q36ref`（サブコマンドなし） |
| 主な実装 | `src/qwen35/q36ref.cu` |
| 用途 | Qwen3.6 reference path の推論結果を照合する開発・検証用 CLI |

## 役割

この executable は Qwen3.6-35B-A3B (`qwen35moe`) 用の reference path です。GGUF モデルを読み、token ID 列を1 tokenずつ GPU 上で処理し、greedy token ID を表示します。レイヤー出力、greedy 候補の上位2件、全 logits などをファイルへ保存して、llama.cpp との中間値・出力照合に使えます（`src/qwen35/q36ref.cu:1-7,25-31`）。

これは Terminal の `strata` サブコマンドや通常の推論 engine CLI ではなく、CMake が GPU backend build 内で生成する独立 executable です（`CMakeLists.txt:333-335,771-775`）。索引では照合・開発用として扱われ、現行 Release への同梱は確認できていません（[`docs/cli/README.md`](../../README.md) の `strata-q36ref` 節）。

## 使い方

基本実行では、GGUF ファイルと prompt の token ID を指定します。

```sh
strata-q36ref --model ./model.gguf --tokens 248045,846,198 --n 4
```

forced continuation を与えて同じ列で照合する例です。

```sh
strata-q36ref --model ./model.gguf --tokens 248045,846,198 \
  --force 320,13 --dump-full-logits ./q36ref-logits.bin
```

token ID 列はテキスト prompt ではありません。`--tokens-file` を使う場合はファイル内容を ID 列として読みます。モデル名と token の例はソース usage に沿った形式であり、ここでは実在ファイルや実行可能性を確認していません（`src/qwen35/q36ref.cu:25-27,708-717,734-742`）。

## 実行モード

この CLI にサブコマンドや対話モードはありません。parser が受け付ける主な実行パターンは次の通りです。

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| greedy 生成 | `strata-q36ref --model FILE.gguf --tokens ID,ID,...` | prompt を処理後、greedy token を次の入力に使って生成します。既定の生成位置数は64、context 上限は4096です。 |
| teacher forcing | `... --force ID,ID,...` | 指定 continuation を次の forward 入力に使います。`gen:` には各位置で選んだ greedy ID が出力されます。非空の `--force` は生成位置数を continuation の長さ+1にします。 |
| 中間値・logits dump | `... --dump-layers PATH`、`--dump-logits PATH`、`--dump-full-logits PATH` | レイヤー出力、各生成位置の top-2、全 vocabulary logits をそれぞれ raw binary で保存します。 |
| kernel 経路選択 | `... --kernels plain` または `--kernels strata` | 自前の plain kernel 経路、または Strata native kernel を使う経路を選びます。既定値は `strata` です。 |

全 parser option と各 option の挙動は [CLI 索引の `strata-q36ref` 節](../../README.md#strata-q36ref-srcqwen35q36refcu) と以下の個別文書を参照してください。

## 主な動作と副作用

- `--model` と空でない `--tokens` または `--tokens-file` が必要です。モデルは GGUF geometry と layout の検査後に読み込まれ、family が `qwen35moe` でなければ拒否されます（`src/qwen35/q36ref.cu:479-488,771-785`）。
- 実装コメントは1 GPU、モデル全体の VRAM 常駐、prompt を含む1 token ずつの処理を前提として説明しています。また expert cache、MTP、graph は使わない reference path としています（`src/qwen35/q36ref.cu:1-7`）。GPU state と各種 buffer を確保して forward を行うため、モデルの GPU メモリーを必要とします（同 `:551-585,786-805`）。
- `--kernels strata` は量子化 matmul などに Strata native kernel を使います。`--kernels plain` はこのファイルの plain kernel を選びますが、GPU を使わないモードではありません。router などは native path の対応条件を満たさない場合に host 側の処理へ fallback します（`src/qwen35/q36ref.cu:3-7,655-680`）。
- `--force` を使わない場合は生成時に得た greedy ID が次の forward に渡ります。使う場合は forced 列が次の forward 入力になりますが、表示される `gen:` 列と dump の候補は引き続き greedy 判定から得られます（`src/qwen35/q36ref.cu:766-770,802-819,826-830`）。
- `--dump-layers`、`--dump-logits`、`--dump-full-logits` の指定先は `wb` で開かれるため、既存ファイルは切り詰められます。出力が必要なときは既存データのない別 path を指定してください（`src/qwen35/q36ref.cu:790-793,805,815-819`）。
- context 判定は dump file を開いた後に行われます。処理位置数が `--ctx` を超えると終了コード2で失敗し、その場合でも指定ファイルが作成・切り詰め済みの可能性があります（`src/qwen35/q36ref.cu:797-800`）。dump の open/write 戻り値を検査する処理は確認できず、ファイル出力の失敗が診断や終了コードへ反映されない場合があります（同 `:790-793,805,815-825`）。
- token ID 列は `atoi` で変換され、parser に厳密な数値形式や語彙範囲の検査はありません。対象モデルに対応した有効な整数 ID を指定してください（`src/qwen35/q36ref.cu:708-717`）。

## 出力と失敗

- 正常終了時、stdout に `gen: <ID...>`、stderr に prompt/generated の位置数、経過時間、token 毎の処理速度が出ます（`src/qwen35/q36ref.cu:826-831`）。
- 値の欠落、未知 option、必須 model/prompt の欠落は stderr に診断または usage を出し、終了コード2です。専用の `--help` parser 分岐はなく、`--help` も未知 option として扱われます（`src/qwen35/q36ref.cu:727-764,771-774`）。
- model の load / layout / family 検査失敗や CUDA 呼び出し失敗は stderr にエラーを出し、非0で終了します。load 失敗は1、context 超過は2です（`src/qwen35/q36ref.cu:53-60,479-488,775-800`）。

## 関連文書

- [CLI 索引の `strata-q36ref` 節](../../README.md#strata-q36ref-srcqwen35q36refcu)
- [`--act`](--act.md)、[`--ctx`](--ctx.md)、[`--dump-full-logits`](--dump-full-logits.md)、[`--dump-layers`](--dump-layers.md)、[`--dump-logits`](--dump-logits.md)、[`--force`](--force.md)、[`--kernels`](--kernels.md)、[`--model`](--model.md)、[`--n`](--n.md)、[`--tokens`](--tokens.md)、[`--tokens-file`](--tokens-file.md)

## 根拠と調査範囲

- `src/qwen35/q36ref.cu:1-7,25-31` — reference path の想定、usage、出力用途。
- `src/qwen35/q36ref.cu:708-764` — token ID 変換、option parser、usage と未知 option の失敗処理。
- `src/qwen35/q36ref.cu:479-488,771-785` — GGUF 読み込み、family/layout 検査と失敗経路。
- `src/qwen35/q36ref.cu:551-585,655-680,786-831` — GPU state、kernel path、context 検査、生成・dump・標準出力。
- `CMakeLists.txt:333-335,771-775` — GPU backend 条件と executable target。
- `docs/cli/README.md:1420-1422,1487-1503` — 開発用 CLI としての分類、command scope、予定リンクと option inventory。

同一 revision のビルド済み executable、`--help` 出力、Release archive は確認していません。ソースには専用 help option がなく、同一 revision の CLI help を補助資料として実行することもしていません。記述は指定 commit の checkout 内ソースと索引に基づき、Release 配布状況は索引記載以上に断定していません。
