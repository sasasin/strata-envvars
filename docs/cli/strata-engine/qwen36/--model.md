# `--model`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 専用 parser、または `strata-q36` |
| オプション | `--model GGUF` |
| 別名 | `--native GGUF`（この Qwen3.6 parser では同じ値として処理） |
| 値 | 読み込む GGUF モデルファイルのパス |

## 役割

Qwen3.6 engine がロードするモデル GGUF のパスを指定します。通常の `strata` engine では `--model` または `--native` の値から GGUF architecture を先に調べ、`qwen35moe` の場合にだけ Qwen3.6 専用 parser に引き渡します。`strata-q36` はこの専用 parser を直接呼び出します（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`）。

## 使い方

```sh
strata --model /models/qwen36.gguf --serve
strata-q36 --model /models/qwen36.gguf --tokens 1,2,3
```

通常の `strata` から使う場合、モデルの architecture が `qwen35moe` である必要があります。Qwen3.6 用の独立 executable `strata-q36` では family switch を経由しません（`src/program/generate.cpp:2394-2407`、`src/qwen35/q36_main.cpp:5`）。

## 値と既定値

- 値は引数文字列をそのままモデルパスとして保持します。専用 parser は `--model` と `--native` を同じ分岐で受け取り、両方を指定した場合は後から解析した値が残ります。数値形式やパス文字列の parser 側 validation はありません（`src/qwen35/q36_engine.cu:3742-3749`）。
- 既定値はありません。値を指定しない場合は `strata-q36: --model is required` を stderr に出して終了コード 2、オプション末尾で値自体が欠けている場合は `strata-q36: --model needs a value`（または `--native needs a value`）を出して終了コード 2 で終了します（`src/qwen35/q36_engine.cu:3744-3747,3797`）。空文字列は受け取りますが、最終的に空パスとして必須値検査で拒否されます（同 `:3749,3797`）。
- 値が空でなければ、拡張子・ファイル存在・GGUF の妥当性は parser では検証しません。実際の GGUF 読込・family・geometry・layout 検査は後続の `load()` で行います（`src/qwen35/q36_engine.cu:959-974`）。

## 実行時の動作

専用 parser は保存したパスを `load()` に渡し、`GgufModel::open(path)` でモデルを開きます。続けて GGUF から geometry を読み、Qwen3.6 の `Qwen35Moe` family、GGUF layout、およびこの engine の kernel が扱う geometry 条件を検査します。モデルの tensor は読み取り、GPU buffer へコピーされます（`src/qwen35/q36_engine.cu:959-974,979-1023`）。読込に成功すると engine と expert の配置を初期化します（同 `:3817-3818,3863-3866`）。

`strata` 本体での family switch は `--model` または `--native` の値を見て GGUF header を調べます。Qwen3.6 なら全引数を専用 parser へ渡します。header をここで読めない場合は例外を捕捉して通常経路へ進むため、そこでの診断は通常 parser / 読込経路によります（`src/program/generate.cpp:2397-2407`）。一方、`strata-q36` では最初から専用 parser なので、この事前振り分けはありません。

Qwen3.6 parser はモデル必須検査後に、未設定の場合だけ `CUDA_MODULE_LOADING=EAGER`、`STRATA_Q8_PACKED=1`、`STRATA_MMQ_KQ=1` を環境へ設定します。POSIX では既存値を上書きせず、Windows でも既存値がある変数は維持します（`src/qwen35/q36_engine.cu:3797-3805`）。これは `--model` 自体のパス処理ではなく、この専用 engine の起動時副作用です。

## 適用条件と副作用

- `--model` は Qwen3.6 専用 parser のオプションです。通常の `strata` ではモデル header が `qwen35moe` のときにこの parser が使われます。Qwen3.6 対応コードは `STRATA_HIP_GFX906` build では有効にならず、CMake はその build で `strata-q36` を追加せず、`strata` にも Qwen3.6 library をリンクしません（`src/program/generate.cpp:2393-2407`、`CMakeLists.txt:776-794`）。
- 指定したパスの読込、tensor の GPU 転送、engine 初期化によってファイル I/O と GPU memory allocation が発生します。モデルパス指定そのものがファイルへ書き込む処理は確認できません（`src/qwen35/q36_engine.cu:959-962,994-1023,3810-3818`）。
- `load()` は geometry が `Qwen35Moe` でない場合、layout 不正、または非対応 geometry の場合にエラーを返します。専用 `strata-q36` では診断を stderr に出し終了コード 1 です。`strata` の family switch 前に header を開けなかった場合は、通常 engine 経路に委ねられます（`src/qwen35/q36_engine.cu:963-974,3810-3815`、`src/program/generate.cpp:2400-2407`）。
- `src/qwen35/q36_engine.cu` 内では `--native` は `--model` と同じ GGUF パスとして処理され、独立した Qwen3.6 動作は確認できませんでした。ただし索引 `docs/cli/README.md:1341-1344` は `--model` の別名として示すほか、独立オプションとしても `--native` を列挙しています。この索引上の重複は本調査対象のソースと食い違います。

## 出力とエラー

- パスが開けないなど `load()` が例外を投げる場合、`strata-q36: <例外メッセージ>` を stderr に出し終了コード 1 です。geometry / layout / family 条件を満たさない場合も診断を stderr に出し終了コード 1 になります（`src/qwen35/q36_engine.cu:959-974,3810-3815`）。
- 必須値の欠落は終了コード 2 です。`load()` 内で必須 tensor が見つからない場合や、非対応 tensor 型の場合には stderr への診断後、終了コード 1 でプロセスを終了する経路があります（`src/qwen35/q36_engine.cu:979-985,994-1004`）。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3797` — Qwen3.6 parser、`--model` / `--native` の同一処理、既定値なし、必須値検査。
- `src/qwen35/q36_engine.cu:959-974,979-1023` — GGUF open、family / geometry / layout validation、model tensor の読み込み・GPU 転送。
- `src/qwen35/q36_engine.cu:3797-3815,3863-3866` — 起動時環境変数、読込エラー経路、engine・expert 初期化。
- `src/program/generate.cpp:2393-2407` — `strata` における GGUF architecture 判定と Qwen3.6 専用 parser への振り分け。
- `src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:776-794` — 独立 `strata-q36` の入口と Qwen3.6 build 条件。
- `docs/cli/README.md:1318-1344` — Qwen3.6 parser の索引スコープと `--model` / `--native` の索引上の食い違い。

調査範囲は上記 commit の checkout に含まれるソースです。同一 revision の既存 CLI binary、Release artifact、実機での GPU 実行は確認していません。
