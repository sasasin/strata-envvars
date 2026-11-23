# `strata-inkling --info`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP root） |
| オプション | `--info` |
| 別名 | なし |
| 値 | 入力モデルまたは vision shard のパスを 1 個取る |

## 役割

指定した Inkling-2-Mini 形式のモデル、または VisionShard のメタデータを調べて標準出力に表示する。モデル情報には形式、build、層数、hidden size、語彙数、expert 数、EOS token、DSpark の有無、画像利用可否などが含まれる。backend の生成や推論を開始せず、`--info` モードとして入力を開いて情報を出力する（`engine/src/inkling2/ink_main.cpp:59-99,544-549`）。

## 使い方

```sh
# モデルのメタデータを表示
strata-inkling --info ./model.strata

# Hugging Face safetensors モデルを調べ、画像 encoder も probe する
strata-inkling --info ./model-dir --vision ./vision.strata

# GGUF モデルと、明示した DSpark drafter を含む情報を表示
strata-inkling --info ./model.gguf --dspark ./dspark.gguf
```

モデル入力は Strata ファイル、safetensors（ファイルまたは対応するモデルディレクトリ）、GGUF が実装上の対象。`--vision` は任意の vision shard パス、`--dspark` は任意の DSpark ファイルパスである（`engine/src/inkling2/ink_main.cpp:59-98,404-408,431-432`; `engine/src/inkling2/ink_manifest.h:454-477`; `engine/src/inkling2/ink_safetensors_loader.h:117-130`; `engine/src/inkling2/ink_gguf_loader.h:285-287`）。

## 値と既定値

- `--info` は直後の argv をそのまま入力パスとして受け取る。parser にパスの形式・存在確認はなく、実際の判定は `cmd_info` と各 loader が行う（`engine/src/inkling2/ink_main.cpp:381-389,59-84`）。
- 省略時に使われる既定パスはない。値が欠けると `missing value after --info` を stderr に出し、`std::exit(2)` で終了する（`engine/src/inkling2/ink_main.cpp:381-384`）。
- 同一コマンドラインに複数回指定すると、各指定が `info_file` を更新するため最後のパスが使われる（`engine/src/inkling2/ink_main.cpp:388-389`）。
- `--info` に値の検証・補正はない。空文字列なども parser は受け取り、その後の入力 open が失敗する（`engine/src/inkling2/ink_main.cpp:381-389,59-84`）。

## 実行時の動作

引数走査で `--info` と次の値を保存する。引数走査後、`mode_info` が有効なら `cmd_info(info_file, cfg.vision_path, cfg.bopts.dspark_path)` を呼び、その戻り値をプロセス終了値にする。したがって `--info` と別 mode（例: `--bench` や `--serve`）を同時に指定した場合も、`--info` が先に処理される（`engine/src/inkling2/ink_main.cpp:388-389,544-549`）。

入力が safetensors または GGUF と認識されない場合、まず Strata reader で開く。Strata ファイルの profile が `VisionShard` なら vision probe の結果（architecture、layers、hidden size、patch/merge、tensor 数、image token）を表示して終了する。それ以外は `InkModelFile::open` に進み、通常モデルの概要を表示する。モデル loader は safetensors/GGUF の場合に各 adapter を選び、その他を Strata として開く（`engine/src/inkling2/ink_main.cpp:61-99`; `engine/src/inkling2/ink_manifest.h:454-477`）。

`--vision` を併用すると、主モデルを開いた後に vision shard を probe し、probe 成功なら `images=1`、失敗なら `images=0` と診断を stderr に出す。`--dspark` はモデル loader に渡され、読み込んだ DSpark tensor が存在する場合に `drafter=dspark`、それ以外は `drafter=none` と表示される。safetensors loader は明示パスを companion `mtp.safetensors` より優先し、GGUF loader も明示パスを自動検出より優先する（`engine/src/inkling2/ink_main.cpp:80-98`; `engine/src/inkling2/ink_safetensors_loader.h:355-370,398-417`; `engine/src/inkling2/ink_gguf_loader.h:689-717,734-742`）。

## 適用条件と副作用

- ここで扱うのは索引上の CUDA/HIP root entry である。Metal と SYCL は別 parser・別 scope なので、本書の記述対象外（索引 `docs/cli/README.md:1509-1512,1549-1552,1572-1575`）。
- `--vision` が失敗しても主モデルの open が成功していれば警告後にモデル情報を出して終了する。主入力が VisionShard の場合は vision probe が失敗するとコマンド自体が失敗する（`engine/src/inkling2/ink_main.cpp:68-78,87-98`）。
- `--info` の処理分岐に入る前に、Linux HIP build では条件を満たす場合にプロセスの NUMA memory policy を設定し、CUDA build では未設定時に `CUDA_MODULE_LOADING` を設定する。検出した条件によって stderr に案内を出す場合もある。これらは `--info` 専用ではなく `main` 冒頭で行われる（`engine/src/inkling2/ink_main.cpp:360-370`; `engine/include/strata/platform/numa_balancing.hpp:71-94`; `engine/include/strata/core/volta_forever.hpp:81-94`）。
- `--info` の処理経路自体には backend 初期化・GPU 推論の呼び出しはない（`engine/src/inkling2/ink_main.cpp:59-99,544-549`）。loader 内のファイル読み込み量や OS による I/O 特性までは本調査では評価していない。

## 出力とエラー

- 通常モデルは `arch=inkling2_loop ...` の1行、VisionShard は `arch=inkling2_vision ...` の1行を stdout に出して終了コード 0 を返す（`engine/src/inkling2/ink_main.cpp:75-78,93-98`）。
- Strata reader、vision probe（主入力）、またはモデル open に失敗すると、`open: ...` または `vision shard: ...` を stderr に出し、終了コード 1 を返す（`engine/src/inkling2/ink_main.cpp:63-66,71-73,80-84`）。
- 任意の `--vision` の probe 失敗は `vision shard: ...` を stderr に出すが、`images=0` として処理を続ける（`engine/src/inkling2/ink_main.cpp:87-98`）。
- `--info` の値がない場合は前述のとおり終了コード 2。未認識のオプションも `unknown option: ...` を stderr に出して終了コード 2（`engine/src/inkling2/ink_main.cpp:381-384,499-501`）。

## 根拠

- `engine/src/inkling2/ink_main.cpp:381-389` — 手動 argv parser、必須値の取得と欠落時の終了。
- `engine/src/inkling2/ink_main.cpp:59-99` — 入力形式の分岐、optional vision probe、成功出力と失敗経路。
- `engine/src/inkling2/ink_main.cpp:544-549` — `--info` の実行優先順位。
- `engine/src/inkling2/ink_manifest.h:454-477` — Strata/safetensors/GGUF の loader 選択。
- `engine/src/inkling2/ink_safetensors_loader.h:355-370,398-417` — explicit DSpark の選択とモデル情報に反映される tensor の存在判定。
- `engine/src/inkling2/ink_gguf_loader.h:689-717,734-742` — GGUF における DSpark companion の選択・読込。
- `docs/cli/README.md:1509-1527` — `strata-inkling` root scope と `--info` の索引上の位置付け。Metal/SYCL 版は別 scope に列挙される。
