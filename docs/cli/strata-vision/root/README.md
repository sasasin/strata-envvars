# `strata-vision`（画像 encoder CLI）

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の `git status --short --branch` は `## main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`（Terminal CLI のサブコマンドではない独立実行ファイル） |
| 主な実装 | `tools/vision/strata_vision.cpp` |
| build variant | `strata-vision`、`strata-vision-hip`、`strata-vision-sycl`（同一 parser） |

## 役割

画像と vision projector（`mmproj`）を読み込み、画像の embedding を作る常駐 helper process です。Strata server はこの実行ファイルを起動し、画像ごとに `ENC` 行を送り、返された embedding ファイルを推論 engine に渡します。同じ画像は server 側で hash を使ってキャッシュされます（`serve/server.py:2745-2748, 3008-3036`）。

このページはコマンド全体の概要です。各引数の値や実行時の詳細は [`docs/cli/README.md`](../../README.md) にある個別文書を参照してください。

## 基本的な使い方

通常は server が起動する補助プロセスで、対話型 CLI ではありません。単独で確認する場合は、モデルの GGUF と対応する projector のパスを指定して起動し、stdin にプロトコル行を送ります。

```sh
strata-vision --mmproj /models/mmproj.gguf --model /models/model.gguf --threads 8
```

起動後、標準入力に次の行を送ると `sample.sve` に embedding を書き出します。処理を終えるには `QUIT` を送ります。

```text
ENC /images/sample.png sample.sve
QUIT
```

パスに空白がある場合、`ENC` 行では最後の空白より前が画像パス、後ろが出力パスとして解析されます。出力ファイルは `wb` で開くため、同名ファイルがあれば上書きします（`tools/vision/strata_vision.cpp:57-67, 321-328`）。

```sh
# 起動時に GPU encoder を要求する例
strata-vision --mmproj /models/mmproj.gguf --model /models/model.gguf --gpu --max-tokens 1024
```

CPU/GPU の選択は build と実行環境に依存します。Mac の Metal build は同じ `strata-vision` で `--gpu` を付けた場合に GPU を使い、HIP/SYCL build はそれぞれ別名の実行ファイルを作ります（`tools/vision/CMakeLists.txt:18-31, 71-80, 96-116`）。

## 実行モードと入出力

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| CPU encoder | `strata-vision --mmproj M --model T` | GPU を要求せずに画像 encoder を初期化します。CPU の thread 数を省略した場合、最大16、通常は hardware concurrency の半分を使います。 |
| GPU encoder | `strata-vision --mmproj M --model T --gpu` | GPU 対応 build で GPU encoder を初期化します。HIP/SYCL/Metal build は GPU の有無を確認し、見つからない場合は `ERR` を出して終了します。 |
| version 表示 | `strata-vision --version` | build variant 名を表示して終了します。モデル指定は不要です。 |

正常に初期化すると stdout に `READY <embedding 次元>` を出し、その後 stdin の各 `ENC <image> <output>` 行を処理します。成功時は `OK <token 数> <grid 幅> <grid 高さ> <ms>`、失敗時は `ERR <理由>` を返します。`QUIT` または stdin 終了で常駐ループを抜けます（`tools/vision/strata_vision.cpp:11-15, 283-342`）。

GPU build は起動時に warm-up encode を行って GPU work buffer を確保してから `READY` を返します。CPU では warm-up を行いません（`tools/vision/strata_vision.cpp:249-283`）。ログと警告は stderr に出ます。CPU mode では CUDA/HIP device を隠す環境変数を設定し、GPU runtime が不要な GPU context を開かないようにします（`tools/vision/strata_vision.cpp:130-142`）。

## 主な動作と注意点

- `--mmproj` と `--model` が必要です。どちらかを省略すると usage を stderr に表示して exit 2 です。`--help` は実装されていません。`--version` を除く未知の引数も `unknown argument` と exit 2 になります（`tools/vision/strata_vision.cpp:93-128`）。
- `--model` は text model GGUF を指しますが、reader は語彙と header を開き、モデルの重みを読みません。画像出力は `SVE1` magic、token/grid/embedding 情報の header と float32 embedding 配列から成ります（`tools/vision/strata_vision.cpp:14-15, 208-212, 320-330`）。
- `--max-tokens` は正の値のとき画像 token 数の上限として encoder に渡されます。上限を 1/8 超える画像は拒否されます。`--min-tokens` は正の値のとき encoder に渡され、`--flash-attn` は `on` / `off` 以外を `auto` として扱います。数値引数は `atoi` で変換され、値の厳密な形式検証はありません（`tools/vision/strata_vision.cpp:114-122, 227-230, 275-279, 316-319`）。詳細は各 option 文書を参照してください。
- CPU は `--threads` が正の値ならそれを使用し、省略または0以下なら自動設定します。`--flash-attn` は既定 `auto` ですが、CPU かつ AVX-512 build で明示指定がない場合は off に補正されます（`tools/vision/strata_vision.cpp:90-92, 218-229`）。
- 画像の読込、前処理、encoder 実行、出力ファイル作成に失敗すると `ERR` 行を返し、その `ENC` 要求を処理して常駐を続けます。モデル・encoder 初期化や GPU 検出時の失敗は `READY` 前に stdout の `ERR` を出し、通常 exit 1 または GPU 不在で exit 3 です（`tools/vision/strata_vision.cpp:150-192, 231-248, 291-342`）。
- server は HIP GPU reader の起動に失敗すると CPU reader に切り替える経路を持ちます。これは `strata-vision` 単独実行の自動 fallback ではありません（`serve/server.py:2774-2777, 2829-2842`）。

## オプションと関連文書

- [`--mmproj`](--mmproj.md)、[`--model`](--model.md): projector と text model の入力
- [`--gpu`](--gpu.md)、[`--threads`](--threads.md): 実行 device と CPU thread 数
- [`--max-tokens`](--max-tokens.md)、[`--min-tokens`](--min-tokens.md): 画像 token 数の調整
- [`--flash-attn`](--flash-attn.md): flash attention の選択
- [`--version`](--version.md): build variant 表示

Terminal 側の vision 設定と server 統合は Strata `docs/DETAILS.md:935-963`、画像 reader の起動失敗例は `docs/TROUBLESHOOTING.md:173-184` も参照してください。

## 根拠

- Strata `tools/vision/strata_vision.cpp:7-15, 71-128` — 起動形式、protocol、parser、必須引数、未知引数の処理。
- Strata `tools/vision/strata_vision.cpp:130-192, 208-283` — device の扱い、GPU 検出、model/encoder 初期化、thread・token・warm-up の設定。
- Strata `tools/vision/strata_vision.cpp:286-342` — stdin protocol、画像処理、出力形式、失敗経路、終了処理。
- Strata `tools/vision/CMakeLists.txt:18-31, 71-80, 94-127` — build variant、生成名、GPU backend と platform 条件。
- Strata `serve/server.py:2745-2849, 2997-3043` — server による reader 起動、fallback、画像 embedding の受け渡しと cache。
- Release archive の各 revision への同梱状況はここでは個別に確認していません。実配布物の一覧は [`docs/cli/000_cli_tools.md`](../../000_cli_tools.md) の記録を参照してください。
