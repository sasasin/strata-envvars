# `strata-hy4 --dump-dfly-temp`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root） |
| オプション | `--dump-dfly-temp` |
| 別名 | なし |
| 値 | 数値文字列を `float` に変換した温度。既定値は `-0.6`。 |

## 役割

`--dump-dfly-batch` による DFly バッチ書き出しで、プロンプトごとの次 token 選択を greedy にするか、上位候補から温度付きでサンプリングするかを制御します。負値はプロンプト系列のうち3件に1件を `abs(値)` の温度でサンプリングし、残り2件を greedy にします。非負値では、0 は全件 greedy、正値は全件サンプリングです（`engine/src/hy4flash/run/hy4_main.hip.cpp:183-184, 249-275`）。

このオプション単体ではなく、`--dump-dfly-batch MANIFEST` を指定し、通常の offline 初期化からバッチ書き出し分岐に到達した場合にだけ使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:421-424, 613-615, 659-665, 707-708`）。

## 使い方

```sh
strata-hy4 --model MODEL.strata --dump-dfly-batch prompts.txt --dump-dfly-temp 0.7 --seed 42 --dump-dfly-out ./dfly-samples
```

`prompts.txt` は token ID の列を含むマニフェストです。例は非破壊の新規出力先を指定しています。既存の `seq_NNNN.bin` は `fopen(..., "wb")` で上書きされます（`engine/src/hy4flash/run/hy4_main.hip.cpp:189-207, 309-324`）。

## 値と既定値

- 値は `atof` で `float` に変換され、既定値は `-0.6f` です。負値は絶対値をサンプリング温度として使います。0 は greedy、正値はその温度でサンプリングします（`engine/src/hy4flash/run/hy4_main.hip.cpp:368-370, 424`）。
- parser に範囲検査や変換結果の検査はありません。数値として解釈できない文字列は `atof` の結果（通常は 0）になり、負値の大きさ・正値の上限もこのオプションでは検査されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:424`）。
- 値を省略すると、共通の `nxt()` が `ERR --dump-dfly-temp needs a value` を標準出力へ出し、flush 後に終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-383, 424`）。

## 実行時の動作

- `--dump-dfly-batch` が空でないと、初期化後に `run_dump_dfly_batch` を呼び、`dump_dfly_temp` をその第5引数として渡します。通常の生成ループには渡されません（`engine/src/hy4flash/run/hy4_main.hip.cpp:707-708`）。
- 各マニフェスト行は token ID 列として読み込まれ、空行と `#` で始まる行は除外されます。8個以上の ID を読めた行だけがプロンプトになり、負値モードの3件周期もこの採用済みプロンプトの添字で決まります（`engine/src/hy4flash/run/hy4_main.hip.cpp:191-207, 217-220, 249`）。
- 負値では添字 `pi % 3 == 2` の系列だけを `-値` の温度でサンプリングし、他の2系列は上位候補の先頭を選びます。0 以下の系列は `ids[0]` を選択します（`engine/src/hy4flash/run/hy4_main.hip.cpp:249-253`）。
- 正の温度では、各位置の上位64候補の log probability を温度でスケーリングし、候補内で累積確率が0.95以上となるところまでを残して乱数抽選します。したがって語彙全体に対する通常の sampling 設定ではなく、候補は上位64件に限られます（`engine/src/hy4flash/run/hy4_main.hip.cpp:122-180, 253-275`）。
- `--seed` の値は `cli_samp.seed` を通して RNG に渡ります。seed が0（既定）なら `20261120` が使われます（`engine/src/hy4flash/run/hy4_main.hip.cpp:213, 420, 708`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35`）。`--temperature`、`--top-p`、`--top-k`、`--min-p` は別フィールドを更新しますが、バッチ出力関数へ渡されるのは seed と `--dump-dfly-temp` だけなので、この経路でそれらの設定は使われません（`engine/src/hy4flash/run/hy4_main.hip.cpp:416-424, 708`）。

## 適用条件と副作用

- 適用対象は CUDA/HIP 版 `strata-hy4` の root parser です。CLI 索引はこの scope を `engine/src/hy4flash/run/hy4_main.hip.cpp` として登録しています（`docs/cli/README.md:1277-1300`、`docs/cli/000_cli_tools.md:11`）。
- `--serve` は serve 処理へ移るため、`--info` は情報表示後に戻るため、`--load-only` はモデル読み込み後に戻るため、いずれもバッチ関数に到達せずこの値は使われません（`engine/src/hy4flash/run/hy4_main.hip.cpp:507, 544-565, 611-615, 659-665, 707-708`）。
- バッチ関数は manifest を開けないと `dump-dfly-batch: cannot open PATH` を標準エラーへ出し、1を返します。出力ディレクトリは `create_directories` で作られます。各系列は `seq_NNNN.bin` にバイナリ出力され、同名ファイルは上書きされます。`fopen` 失敗時は `cannot write PATH` を標準エラーへ出して1を返します（`engine/src/hy4flash/run/hy4_main.hip.cpp:184-189, 309-315`）。
- 正常な系列の進捗と最終 `DONE` は標準エラーへ出力されます。ファイル書き込みの `fwrite` / `fclose` 戻り値は検査されていないため、書き込み途中の I/O エラーを検出する経路はソース上確認できません（`engine/src/hy4flash/run/hy4_main.hip.cpp:316-331`）。

## 出力とエラー

値自体に対する不正値エラーや範囲エラーは定義されていません。モデル初期化に失敗すると `init: ...` を標準エラーへ出して1を返し、その時点でバッチ書き出しは始まりません。manifest を開けない場合と出力ファイルを開けない場合のエラーも上記のとおりです（`engine/src/hy4flash/run/hy4_main.hip.cpp:703-708, 184-188, 311-315`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:368-370, 421-424` — 既定値と parser 登録、`atof` 変換。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:183-213, 217-275` — マニフェスト処理、seed、温度ごとの token 選択。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:707-708` — バッチ出力関数への値の引き渡し。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:309-331` — 出力ファイル形式、上書き、進捗表示と完了処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:507, 544-565, 611-615, 659-665` — 先行 return とバッチ経路の適用条件。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35` — `SampleOpts` の seed 既定値。
- `docs/cli/README.md:1277-1300`、`docs/cli/000_cli_tools.md:11` — ツール ID、コマンド階層、parser scope と索引リンク。
