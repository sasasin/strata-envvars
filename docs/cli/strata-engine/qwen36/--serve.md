# `--serve`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` / `strata-q36`（Qwen3.6 parser） |
| オプション | `--serve` |
| 別名 | なし |
| 値 | なし。指定すると serve mode を有効化 |

## 役割

モデルと engine を起動時に一度ロードし、その後 stdin からリクエストを受け付ける常駐モードです。Qwen3.6 family の実装では通常の `GEN` / `GENI` 要求を逐次処理し、`--batch` が有効な場合は `BGEN` / `BGENI` で slot に要求を登録して複数 slot を decode します（`src/qwen35/q36_engine.cu:3174-3178, 3728-3730`）。

`strata` は `--model` または `--native` が指す GGUF の family を調べ、architecture が `qwen35moe` なら通常 parser の処理へ進まず Qwen3.6 engine の `run()` に引き渡します。したがって、この文書の `--serve` は `strata-engine/root/--serve.md` の通常 engine parser と区別される Qwen3.6 scope です（`src/program/generate.cpp:2393-2407`）。専用 executable `strata-q36` も同じ `run()` を呼びます（`CMakeLists.txt:781-794`, `src/qwen35/q36_main.cpp:1-5`）。

## 使い方

```sh
strata --model ./qwen36.gguf --serve
```

専用 executable を使う場合:

```sh
strata-q36 --model ./qwen36.gguf --serve
```

いずれも `--model` が必須です。`--serve` 自体は値を取りません（`src/qwen35/q36_engine.cu:3741-3756, 3797`）。モデルは Qwen3.6 engine が扱える GGUF である必要があります。

## 値と既定値

- parser の既定値は `serve_mode = false`、`--serve` を指定すると `true` になります。値・alias・回数指定に関する専用 validation はありません（`src/qwen35/q36_engine.cu:3741-3756`）。
- `--serve` でなければ、`--tokens`、benchmark などの別 mode に進みます。serve mode では prompt は起動引数でなく stdin の要求が持ち込みます（`src/qwen35/q36_engine.cu:3888-3917`）。
- 実際の要求には `GEN <max_new> [key=value ...] <id,id,...>`、画像要求には `GENI <max_new> [keys] <embeddings-file> <id,id,...>` を使います。`max_new` は 1 以上、token ID 列は空でなく語彙範囲内である必要があり、prompt と生成上限の合計は context 以下でなければなりません（`src/qwen35/q36_engine.cu:3431-3438, 3494-3516`）。

## 実行時の動作

起動後、stdout に `READY <context> stop` を出して stdin を行単位で読みます。複数 session slot がある場合はその前に `INFO batch_slots=<N> slot_cache=1` も出力します（`src/qwen35/q36_engine.cu:3678-3684`）。通常要求では処理中に `PP`（prompt 進捗）と生成 token ごとの `T <id>` を stdout に出し、最後に `DONE ... <stop|length|cancel> ...` を出します。リクエスト単位の計測ログは stderr に出ます（`src/qwen35/q36_engine.cu:3544-3559, 3573-3578, 3596-3603, 3667-3675`）。

`STOP` は実行中要求を次の処理境界で止める制御行です。stdin が EOF になると、実行中 slot があれば処理を終えた後に serve loop を抜けて正常終了します（`src/qwen35/q36_engine.cu:3682-3695, 3701-3724`）。この Qwen3.6 serve loop は `QUIT` を終了コマンドとして扱う実装ではありません。未知の制御行は `ERR expected: ...` を stdout に出し、要求 parser が扱えない要求についても `ERR ...` を返して処理を継続します（`src/qwen35/q36_engine.cu:3434-3438, 3495-3516, 3711-3722`）。

`--batch N` と組み合わせると `BGEN <slot> <max_new> ...` / `BGENI ...` で prompt を slot に割り当て、各 decode window の出力は `BT <slot> <id>`、slot 完了は `BDONE <slot> ...` になります。`BSTOP <slot>` はその slot を次の window で終了させます（`src/qwen35/q36_engine.cu:3174-3178, 3283-3304, 3431-3449`）。画像要求 `GENI` / `BGENI` は起動時の `--vision` が必要です（`src/qwen35/q36_engine.cu:3500-3503, 3775`）。

## 適用条件と副作用

- Qwen3.6 parser は `--model` が空なら stderr に `strata-q36: --model is required` を出して終了コード 2、モデル読み込み失敗は stderr に理由を出して終了コード 1 です。`--serve` はモデル読込・engine 初期化後に serve loop へ入ります（`src/qwen35/q36_engine.cu:3797, 3810-3816, 3863-3889`）。
- CMake では `strata-q36` と `strata` への Qwen3.6 family engine 組込みは `NOT STRATA_HIP_GFX906` の条件下にあります（`CMakeLists.txt:781-794`）。実行ファイルが生成・配布される全 build 構成はこの調査では確認していません。
- parser は引数を左から読むため、未知の `--option` は `--serve` より前に現れると usage を出して終了コード 2 になります。一方、`--serve` より後で未知の `--option` が現れると、stderr に無視した旨を出し、直後の次引数が `--` で始まらなければその値も読み飛ばします。設定由来の共通引数が Qwen3.6 engine に存在しない場合の互換処理です（`src/qwen35/q36_engine.cu:3742-3747, 3782-3795`）。
- 起動後は stdin/stdout をプロトコル通信に使います。ログは stderr です。別プロセスと接続する場合、stdout に通常の対話文や別出力を混ぜないでください（`src/qwen35/q36_engine.cu:3678-3695`, 出力箇所 `3547-3550, 3596-3603`）。

## 出力とエラー

要求の構文、空 prompt、`max_new < 1`、語彙外 token、context 超過、画像機能未起動などの要求エラーは stdout の `ERR ...` 行で返り、serve process 自体はその要求の後も待受を続けます（`src/qwen35/q36_engine.cu:3434-3438, 3494-3516`）。起動引数の不足・不正は stderr と終了コード 2、モデル読込や expert 配置の失敗は stderr と終了コード 1 です（`src/qwen35/q36_engine.cu:3790-3798, 3810-3816, 3863-3867`）。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3795` — Qwen3.6 parser、`--serve` の bool 設定、未知 option の扱い、usage と model 必須条件。
- `src/qwen35/q36_engine.cu:3882-3889` — 初期化後に serve mode を選ぶ分岐。
- `src/qwen35/q36_engine.cu:3174-3178, 3431-3516, 3544-3675, 3678-3724` — stdin protocol、request validation、出力、STOP/EOF の処理。
- `src/program/generate.cpp:2393-2407` — `qwen35moe` model に対する family switch。
- `CMakeLists.txt:781-794`、`src/qwen35/q36_main.cpp:1-5` — build 条件、専用 `strata-q36` entry point。

同一 revision の CLI `--help` は補助資料として実行していません。parser と runtime のソースを根拠にしています。
