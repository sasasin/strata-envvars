# `--dump-full-logits`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査開始時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | Qwen3.6 専用 parser（`strata --model QWEN35MOE.gguf` または `strata-q36`） |
| オプション | `--dump-full-logits` |
| 別名 | なし |
| 値 | 出力ファイルのパス（1 引数） |

## 役割

`--tokens` による Qwen3.6 の単発生成で、各生成ステップの語彙全体の logits を float32 のバイナリファイルへ書き出します。実装コメントでは `tools/qwen35/kl.py` の比較用インターフェースとして位置付けられています。出力は通常の生成トークン表示とは別です（`src/qwen35/q36_engine.cu:17-18, 3960-3977`）。

## 使い方

```sh
strata-q36 --model QWEN35MOE.gguf --tokens 1,2,3 --n 4 --dump-full-logits /tmp/q36-logits.bin
```

同じ parser は `strata` にも組み込まれており、`--model` / `--native` で指定した GGUF の architecture が `qwen35moe` のとき選択されます。独立実行ファイル `strata-q36` は `src/qwen35/q36_main.cpp` から同じ `strata::qwen35::run` を呼びます（`src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:776-794`）。

## 値と既定値

- 値は次の argv 要素から取得されます。値を省略すると `strata-q36: --dump-full-logits needs a value` を stderr に出して終了コード 2 で終了します（`src/qwen35/q36_engine.cu:3742-3747, 3762`）。値のパス形式や拡張子の検証はありません。
- 既定ではダンプしません。指定値は `dump_full` に保存され、トークン生成経路で空でなければ `fopen(path, "wb")` が呼ばれます。空文字列は空パスとして保持されますが、`dump_full.empty()` によりダンプ無効として扱われます（`src/qwen35/q36_engine.cu:3735-3741, 3916-3920`）。
- 1回の通常トークン生成につき、既定の生成数は64ステップです。`--n N` または `--max-new N` が同じ `n_gen` を設定します。`--force IDS` が空でない場合は強制列の長さ + 1 に上書きします（`src/qwen35/q36_engine.cu:3736-3738, 3750, 3759-3762, 3916-3918`）。

## 実行時の動作

- ダンプ対象の実行経路は `--tokens IDS` を使う単発生成です。各反復で greedy token を選び、その直後に現在の logits 行をホストへコピーし、float 4バイト単位でファイルに書きます（`src/qwen35/q36_engine.cu:2785-2789, 3960-3969`）。
- ファイルは生成ループの前に `wb` で開くため、同名の既存ファイルは切り詰められます。書き込みレイアウトはステップ順の float32 logits 行列 `[steps][vocab]` です。Qwen3.6 比較スクリプトは語彙幅を 248320 として読み込んでいます（`src/qwen35/q36_engine.cu:3916-3920, 3960-3965`; `tools/qwen35/q36_lgcmp.py:1-5`）。出力バイト順は実行環境のネイティブ表現です。コードは各行の書き込み結果や `fclose` の結果を検査しません。
- `--force` を指定すると、ログ出力後に次の入力 token を強制列から選びます。したがって各行は生成ステップの logits で、同じ行の次 token が forced token になる比較用途に利用できます（`src/qwen35/q36_engine.cu:3916-3918, 3960-3970`）。
- ダンプファイルを正常に開けた場合は `ff` が有効になり、通常なら MTP を使う条件（MTP 有効、forced 列なし）から外れて、通常の greedy ループで各行を書き出します（`src/qwen35/q36_engine.cu:3935-3950, 3960-3965`）。
- `--serve` は serving 処理へ、`--bench-pp` / `--bench-tg` は benchmark 処理へ先に分岐するため、これらのモードではこのオプションによるファイル出力は行われません。ダンプ用ファイルを開く処理は両分岐より後です（`src/qwen35/q36_engine.cu:3888-3919`）。

## 適用条件と副作用

- `strata` では `--model` または `--native` の GGUF architecture が `qwen35moe` の場合に限り、この Qwen3.6 parser へ切り替わります。他の model family は通常の engine parser です（`src/program/generate.cpp:2393-2407`）。
- 通常経路では `--tokens` が空だと usage error（終了コード 2）になります。`--serve`、benchmark は別経路です（`src/qwen35/q36_engine.cu:3789-3795, 3888-3918`）。
- `fopen` の戻り値をエラー確認せず `ff` に入れます。パスが開けず `ff == nullptr` になると、エラー表示なしにダンプを行わず、MTP 条件判定でも「ダンプなし」と同じ扱いになります。書き込み失敗やディスク容量不足も明示的に報告する処理は確認できません（`src/qwen35/q36_engine.cu:3919-3920, 3935-3950, 3960-3971`）。
- ファイル作成・切り詰めの副作用があります。指定先を上書きしてよいことを確認し、必要な場合は新しいパスを使ってください。

## 出力とエラー

値の欠落は stderr にエラーを出して終了コード 2 です。未知の引数は通常モードでは usage を stderr に出して終了コード 2 ですが、`--serve` モードでは未知の `--` 引数を警告して読み飛ばす分岐があります（`src/qwen35/q36_engine.cu:3744-3746, 3782-3795`）。通常生成では stdout に `gen:` と token ID 列、stderr に prompt / 生成の所要時間と速度が出ます。ダンプファイルを開けない場合の専用エラーや警告はありません（`src/qwen35/q36_engine.cu:3969-3977`）。

## 根拠

- `src/qwen35/q36_engine.cu:3735-3765` — parser、値の取得、関連 option。
- `src/qwen35/q36_engine.cu:3789-3797, 3888-3919` — usage、model 必須条件、serve / benchmark / tokens の経路とファイルオープン。
- `src/qwen35/q36_engine.cu:2785-2789, 3916-3977` — logits のホストコピー、force/MTP との関係、ファイル書き込みと通常出力。
- `src/program/generate.cpp:2393-2407`、`src/qwen35/q36_main.cpp:1-5`、`CMakeLists.txt:776-794` — family switch と独立 executable の entry point。
- `tools/qwen35/q36_lgcmp.py:1-5` — 比較ツールが読む float32 `[steps][248320]` 形式。

この調査ではソースと既存の比較スクリプトを確認しました。CLI `--help` や実行バイナリの出力、Release 配布物は確認していません。
