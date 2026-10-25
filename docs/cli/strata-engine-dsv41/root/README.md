# `strata-dsv41`（DeepSeek-V4.1 エンジン）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main` で、`git status --short --branch` は `## main...origin/main`（未コミット変更なし）でした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（Windows は `strata-dsv41.exe`） |
| 主な実装 | `src/dsv41/ds4_main.cpp`、`src/dsv41/ds4_model.cu` |
| build 条件 | CMake の `STRATA_BUILD_DSV41=ON`。`STRATA_HIP_GFX906` が有効な build では生成条件から除外 |

## 役割

DeepSeek-V4.1-Flash 用の独立した推論エンジンです。CMake では `strata-dsv41` executable に `src/dsv41` の実装を結び付け、オプション `STRATA_BUILD_DSV41` は既定で OFF です。CMake のコメントでは、現時点では通常の `strata` からの family switch ではなく独立 executable とされています。GitHub Release での配布有無はこの調査では確認していません。

この CLI はトークナイザーを内蔵せず、token ID を入力に取る単発推論と server protocol を提供します。画像の span encoding、pack 情報表示、score/profile/spec 評価の補助モードもあります。

## 代表的な使い方

```sh
# token ID を prompt として読み、16 token まで生成
strata-dsv41 --pack /models/example/maya-ds4 --ids 0,128803,42 --n 16

# prompt の logits をバイナリファイルへ保存
strata-dsv41 --pack /models/example/maya-ds4 --ids 0,128803,42 --dump-logits /tmp/prompt.f32

# StrataEngine 用 server protocol で起動（標準入力から要求を受け付ける）
strata-dsv41 --pack /models/example/maya-ds4 --serve

# pack の説明を表示（GPU・weights の load を行わない）
strata-dsv41 --pack /models/example/maya-ds4 --pack-info
```

`--ids @FILE` とすると token ID 列をファイルから読みます。詳細な引数形式は、ビルド済み同一 revision の実行ファイルで `strata-dsv41 --help` を参照してください。help は `maya-ds4` という名称で構文を表示しますが、CMake が生成する executable 名は `strata-dsv41` です。

## 実行モード

| モード | 呼び出し | 動作 |
| --- | --- | --- |
| 単発生成 | `--ids IDS [--n N]` | prompt ID を feed し、生成 token ID を stdout にカンマ区切りで出します。`--n` の初期値は 0 のため、生成を行うには正の数を指定します。既定は greedy sampling です。 |
| server | `--serve` | 起動時に `READY <context> stop` を出し、stdin の `GEN` / `GENI` 要求を処理します。出力には `T`, `STAT`, `DONE` 行が含まれます。`STOP` は現在の要求を止め、`QUIT` はエンジンを終了します。 |
| 画像 encoding | `--encode-image FILE.rgb --size WxH [--dump-image OUT]` | RGB bytes を vision tower に通し、画像 span を生成します。`--dump-image` を指定すると BF16 row bytes をファイルに書きます。 |
| pack 情報 | `--pack-info` | pack の説明を stdout に出します。pack のパスが必要で、ソースコメント上は device・weights の読み込みや lock を行いません。 |
| 評価・計測 | `--score FILE`、`--profile-run FILE`、`--spec-eval FILE` | 入力 ID データに対する評価または計測を行います。score は `--score-out` がなければ入力ファイル名に `.tsv` を付けた出力先を使います。 |

## 主な動作と副作用

- `--pack` はモデル pack の場所を指定します。`--serve` 以外の実行では、単発入力の `--ids`、画像 encoding、score/profile/spec のいずれかの処理入力が必要です。処理モードへ進む前に `Model::load` が実行され、失敗時はエラーを stderr に出して終了コード 1 になります。
- `--gpus`、`--max-context`、`--reserve-mib`、`--vram-experts`、expert/SSD cache、CPU thread、tensor parallel、prefill、vision、DSpark などの設定は、モデル load・実行計画・推論に作用します。個別の値の規則と組合せは [オプション索引](../../README.md) の `strata-engine-dsv41` 節にある各文書を参照してください。
- 既定の expert profile は `<pack>/expert-profile.bin` です。推論・server 終了経路では profile を保存するため、既定では pack 配下へ書き込みが発生します。`--expert-profile none` は profile のパスを空にします。
- server は prompt 状態を同一プロセス内で再利用します。設定により conversation slot を pack 配下または `STRATA_DS4_SLOT_DIR` で指定したディレクトリに保存し、後続実行で再利用することがあります。server の要求処理・終了は標準入力と stdout のプロトコルを使います。
- `--dump-logits`, `--dump-image`, `--score-out` はファイルを作成・書込します。出力先の既存ファイルを指定すると上書きされる可能性があるため、必要なファイルがある場所は避けてください。

## 注意点

- `--help` / `-h` は usage を stderr に表示して終了コード 0、未知の option は stderr にエラーと usage を表示して終了コード 2 です。値を要する option で値が欠けても終了コード 2 になります。
- 構文 parser は多くの数値を `atoi` / `atof` / `atoll` で読み、全 option に対する一律 validation を行いません。特定 option の値域や不正値の扱いは parser と使用箇所ごとに異なるため、個別文書を確認してください。
- 画像 encoding の RGB 入力は `--size WxH` に合う `width × height × 3` bytes が必要です。読み込みに失敗した場合はエラーを stderr に出し、終了コード 1 で終了します。
- ここで記載した機能と引数は指定 commit のソースに基づきます。利用可能な GPU backend、モデル pack、build 構成ごとの実行可否や Release 配布物は確認していません。

## 関連文書

- [CLI 索引](../../README.md) — `strata-engine-dsv41` の option 文書一覧。
- [CLI ツールと入口](../../000_cli_tools.md) — エンジンの入口、build・配布境界。
- [調査基準](../../001_investigation.md) — 文書配置と調査方法。

## 根拠

- Strata `CMakeLists.txt:797-811` — DeepSeek-V4.1 engine の独立 target と `STRATA_BUILD_DSV41`（既定 OFF）。
- Strata `CMakeLists.txt:812-819` — build ID の設定元。
- Strata `src/dsv41/ds4_main.cpp:85-93` — CLI usage が示す主な実行形態。
- Strata `src/dsv41/ds4_main.cpp:1187-1273` — parser、既定値、`--help`、未知 option と不足値の処理。
- Strata `src/dsv41/ds4_main.cpp:1275-1301` — pack-info、必須入力、profile 既定値、model load と mode dispatch。
- Strata `src/dsv41/ds4_main.cpp:1303-1327` — vision encoding、RGB 読込、span 出力。
- Strata `src/dsv41/ds4_main.cpp:1329-1350` — ID file と画像入力の取り扱い。
- Strata `src/dsv41/ds4_main.cpp:1505-1507` — 単発実行後の expert profile 保存。
- Strata `src/dsv41/ds4_main.cpp:9-16,318-321,917-930,957` — server protocol と起動・応答・終了時の処理。
