# `--force`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | Qwen3.6 専用 parser（`strata --model MODEL.gguf` または `strata-q36`） |
| オプション | `--force` |
| 別名 | なし |
| 値 | 10進 token ID の列。カンマまたは空白区切り（1 argv 引数） |

## 役割

単発の `--tokens` 生成で、モデルが次に選んだ token の代わりに指定 token を次の入力として与えます。モデルの greedy 出力を指定列に沿って評価する teacher-forcing 用の経路です。指定列の各 token 自体は `gen:` 出力を置き換えず、その位置の greedy 予測が出力列に加わります（`src/qwen35/q36_engine.cu:3916-3918, 3960-3973`）。

## 使い方

```sh
strata-q36 --model QWEN35MOE.gguf --tokens 1,2,3 --force 4,5,6
```

同じ parser は `strata` にも組み込まれており、モデルの GGUF architecture が `qwen35moe` の場合に選ばれます。CMake 条件が満たされる build では `strata-q36` も生成されます（`src/program/generate.cpp:2393-2407`; `CMakeLists.txt:776-794`; `src/qwen35/q36_main.cpp:1-5`）。

## 値と既定値

- 値は次の argv 要素を1つ取得します。省略すると `strata-q36: --force needs a value` を stderr に出して終了コード 2 で終了します。`--force` 自体に既定値はなく、未指定なら forced 列は空です（`src/qwen35/q36_engine.cu:3742-3747, 3760`）。
- 値は `parse_ids` で10進整数として読み取られ、カンマと空白を区切りとして扱います。変換できない文字に当たるとそこで解析を止め、既に得た prefix があればそれを返します。したがって不正な末尾が明示的にエラーになるとは限りません。複数回指定すると parser が `force` 文字列を上書きするため最後の値が残ります（`src/qwen35/q36_engine.cu:3058-3069, 3758-3762`）。
- 空文字列、または先頭が整数でない値からは空列になります。空列なら生成数の上書きや forced token の入力は起こりません（`src/qwen35/q36_engine.cu:3058-3069, 3916-3918`）。
- この単発生成経路では、読み取った token ID の語彙範囲を検査する処理を確認できません。server request 経路には別途範囲検証がありますが、それは `--force` の単発生成経路には適用されません（`src/qwen35/q36_engine.cu:3494, 3511-3512, 3916-3918`）。範囲外 ID の挙動はこの調査では実行確認していません。

## 実行時の動作

- `--force` は `--tokens` と同じ単発生成経路で使われます。prompt を処理した後、各反復で greedy token を `gen` に追加し、次の反復があれば `forced[i]` を次の入力にします。forced 列を最後まで使い切った後は greedy token を次の入力に戻します（`src/qwen35/q36_engine.cu:3916-3918, 3931-3933, 3960-3970`）。
- forced 列が空でない場合、`--n` または `--max-new` の値にかかわらず生成数は forced 列の長さ + 1 に設定されます。末尾の `+1` は、最後の forced token を入力した後の greedy 予測も出力するためです（`src/qwen35/q36_engine.cu:3750, 3759-3762, 3916-3918, 3967-3970`）。
- forced 列が空でなければ、Qwen3.6 内蔵 MTP の生成分岐（`--mtp N`）を通らず、通常の逐次 greedy loop に進みます。`--dump-full-logits` でファイルを開けた場合も同じ MTP 分岐条件から外れます（`src/qwen35/q36_engine.cu:3935-3969`）。
- `--serve` は parser 後に serve 処理へ先に分岐し、benchmark (`--bench-pp` / `--bench-tg`) も token 単発生成より先に処理されるため、これらのモードでは `--force` の値は生成入力に使われません（`src/qwen35/q36_engine.cu:3755, 3888-3918`）。

## 適用条件と副作用

- `--tokens` による単発生成に適用されます。通常 engine parser ではなく、Qwen3.6 専用 parser が選択された場合に限ります（`src/program/generate.cpp:2393-2407`; `src/qwen35/q36_engine.cu:3916-3918`）。
- `--tokens` が空または解析結果が空の場合、単発生成は `strata-q36: --tokens, --serve or --bench-pp is required` を stderr に出し終了コード 2 になります。`--force` 列が空でもこの条件は変わりません（`src/qwen35/q36_engine.cu:3916-3918`）。
- この option 自体はファイルやネットワークへ出力せず、forced token を engine の次入力へ渡します。`--dump-full-logits` を同時指定した場合は同 option のファイル出力が発生し得ますが、その挙動は [`--dump-full-logits`](--dump-full-logits.md) を参照してください。

## 出力とエラー

通常の単発生成では stdout に `gen:` と生成 token ID 列、stderr に prompt と生成時間・速度が出ます。forced token 列そのものを別表示する処理は確認できません（`src/qwen35/q36_engine.cu:3972-3977`）。値欠落は parser 内で終了コード 2、不明 option は通常モードで usage を出し終了コード 2 です。`--serve` 時は未知の `--` option を警告して読み飛ばす特別扱いがあり、`--force` 自体は認識されますが serve の生成処理には使用されません（`src/qwen35/q36_engine.cu:3744-3747, 3782-3795, 3888-3918`）。

## 根拠

- `src/qwen35/q36_engine.cu:3742-3762` — parser、引数取得、`--force` の保存、隣接する生成数 option。
- `src/qwen35/q36_engine.cu:3058-3069` — token ID 列の区切りと整数変換。
- `src/qwen35/q36_engine.cu:3888-3919` — serve / benchmark の先行分岐、単発生成への到達、forced 列による生成数決定。
- `src/qwen35/q36_engine.cu:3935-3977` — MTP 条件、forced token の投入、標準出力と統計出力。
- `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:776-794` — model family の切り替えと `strata-q36` の生成。

この調査ではソースを確認しました。CLI `--help`、実行バイナリの出力、Release 配布物、および範囲外 token ID の実行時挙動は確認していません。
