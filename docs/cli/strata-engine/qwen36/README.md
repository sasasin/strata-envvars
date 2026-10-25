# `strata` / `strata-q36`（Qwen3.6 専用エンジン）

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata` の Qwen3.6 family 経路、または `strata-q36` |
| 主な実装 | `src/program/generate.cpp`、`src/qwen35/q36_main.cpp`、`src/qwen35/q36_engine.cu` |
| 対象モデル | GGUF architecture `qwen35moe`（Qwen3.6-35B-A3B） |

## 役割

Qwen3.6-35B-A3B を処理する専用エンジンです。通常の推論エンジンとは異なる parser と実行経路を使います。`strata` は `--model` または `--native` に渡された GGUF の family をヘッダーから判定し、`qwen35moe` なら専用実装に引き渡します。CMake では同じ実装を包む `strata-q36` executable も生成します（`src/program/generate.cpp:2393-2408`、`src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:776-794`）。

このコマンド概要は parser と主要経路を説明します。オプションごとの値・既定値・相互作用は[CLI 索引の Qwen3.6 節](../../README.md)にある個別文書を参照してください。

## 代表的な使い方

Terminal CLI から通常起動する場合:

```sh
strata launch --model qwen36 --no-tui
```

直接エンジンを使う場合（GGUF のパスと実行モードを指定）:

```sh
strata-q36 --model /path/to/Qwen3.6-35B-A3B.gguf --serve
```

engine の `--serve` は標準入出力上の server protocol で待ち受けるモードです。テスト・検証用途の token 入力と benchmark の例は次のとおりです。

```sh
strata-q36 --model /path/to/Qwen3.6-35B-A3B.gguf --tokens 1,2,3 --n 16
strata-q36 --model /path/to/Qwen3.6-35B-A3B.gguf --bench-pp 512 --bench-tg 64
```

ここでの token 値は token ID の列です。`--tokens` と `--n` は単発生成、`--bench-pp` / `--bench-tg` は測定用経路、`--serve` は常駐プロトコル経路を選びます（`src/qwen35/q36_engine.cu:17-18,3748-3794,3888-3917`）。通常の利用でサーバーを起動する場合は Terminal CLI の [`strata launch` 概要](../../strata-terminal/launch/README.md)も参照してください。

## 実行モード

| モード | 主な引数 | 動作 |
| --- | --- | --- |
| server protocol | `--serve` | `READY` を出力して標準入力から要求を受け付け、生成結果・状態を標準出力、進捗情報を標準エラーへ出します。終了時は `STOP` / 入力 EOF を扱います（`src/qwen35/q36_engine.cu:3678-3724`）。 |
| 単発生成 | `--tokens IDS`、任意で `--n N`、`--force IDS` | 指定した token ID 列を prompt として処理し、greedy token ID 列を `gen:` 行で出力します。性能・処理時間は標準エラーに表示されます（`src/qwen35/q36_engine.cu:3916-3978`）。 |
| benchmark | `--bench-pp N`、`--bench-tg N` | 固定 seed から作った token 列で prompt processing と token generation を各 3 回実行し、速度を出力して終了します（`src/qwen35/q36_engine.cu:3890-3914`）。 |

## 起動時の主な動作と副作用

- モデルを読み込み、GGUF family、tensor layout、kernel が扱える geometry と tensor type を確認します。違う family、非対応 geometry、欠損 tensor、非対応 tensor type はエラーになります（`src/qwen35/q36_engine.cu:959-973,980-1004`）。
- 起動時に CUDA/HIP の device とメモリを使い、モデル重みや推論用バッファを GPU に確保します。expert が GPU に収まらない場合、CPU expert pool を含まない build では失敗します。CPU pool 有効時の hybrid 配置では CPU メモリと転送も使います（`src/qwen35/q36_engine.cu:1339-1371,2792-2813,2881-2886`）。
- chunk が `auto`（既定）なら空き VRAM 等から値を選び、`STRATA_Q36_CHUNK` が設定されていれば 256〜4096 の範囲に補正して使用します。warmup は既定で有効で、prompt、decode（MTP 使用時は speculative step も）を一度実行してから状態を reset します。`--no-warmup` はこの処理を省きます（`src/qwen35/q36_engine.cu:3737-3741,3818-3862,2752-2777,3888-3889`）。
- `--vision` は画像対応を有効にします。単発入力で `--emb` を使う場合にも `--vision` が必要です。画像 embedding ファイルが読めない・形式不正などのときは入力処理が失敗します（`src/qwen35/q36_engine.cu:3775,3922-3929`）。この engine 自体が encoder を呼び出す形ではなく、前処理済み embedding を受け取る作りです（`src/qwen35/q36_engine.cu:17-18`）。
- 通常の `strata` から `--gpu` を指定した場合、family switch より前に `CUDA_VISIBLE_DEVICES` または HIP build の `HIP_VISIBLE_DEVICES` と `CUDA_DEVICE_ORDER=PCI_BUS_ID` を設定します。既存の可視 device 環境変数と値が異なる場合は警告を出して上書きします。専用 `strata-q36` 側の `--gpu` は値を読み飛ばすだけなので、device 選択は起動環境側で行ってください（`src/program/generate.cpp:2370-2391`、`src/qwen35/q36_engine.cu:3752-3753`）。

## 注意点

- この parser は `--help` / `-h` を実装していません。未知引数として usage を標準エラーへ出して終了コード 2 になります。実際の option と scope は[索引](../../README.md)および該当 option 文書で確認してください（`src/qwen35/q36_engine.cu:3782-3795`）。
- `--model` と `--native` はこの family では同じモデル引数として扱われます。`strata` の family switch は先に見つかった `--native` または `--model` の直後のファイルを調べ、Qwen3.6 と判定した場合に引数列全体を専用 parser に渡します（`src/program/generate.cpp:2397-2408`、`src/qwen35/q36_engine.cu:3748-3750`）。
- parser の数値変換は `atoi` / `atof` を使う引数があります。値域チェックは一律ではありません。確認できた範囲では `--mtp` は 0〜7、`--chunk` は 0〜4096、`--max-context` は 256 以上を検査します。その他の値域やモデル・build 依存の制約は各 option 文書を参照してください（`src/qwen35/q36_engine.cu:3750-3781,3807-3808`）。
- CMake では `STRATA_HIP_GFX906` の build を除いて `strata-q36` と family switch を `strata` にリンクします。したがって executable や family の利用可否は build 構成によって異なります（`CMakeLists.txt:778-794`）。この checkout から Release 配布物の有無は確認していません。

## 関連文書

- [CLI 文書索引](../../README.md) — `strata-engine/qwen36` の option 文書一覧。
- [Terminal CLI の `strata launch`](../../strata-terminal/launch/README.md) — 対話画面・preset 等を含む通常の利用者向け起動方法。

## 根拠

- `src/program/generate.cpp:2370-2408` — GPU 選択環境の設定と Qwen3.6 family switch。
- `src/qwen35/q36_main.cpp:1-5` — `strata-q36` の入口。
- `src/qwen35/q36_engine.cu:3735-3815` — option parser、未知引数の扱い、必須モデルと値検査、モデル読込エラー。
- `src/qwen35/q36_engine.cu:3817-3889` — chunk 選択、engine 初期化、expert 配置、warmup、serve 分岐。
- `src/qwen35/q36_engine.cu:3890-3978` — benchmark と単発生成の実行・出力。
- `src/qwen35/q36_engine.cu:959-1004,1339-1371,2792-2886` — 対象 GGUF と kernel 制約、GPU buffer、expert 配置と CPU pool 不在時の失敗。
- `CMakeLists.txt:776-794` — family engine と専用 executable の build 条件。
