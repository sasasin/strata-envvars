# `strata-inkling-metal --gen`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal`（Metal backend） |
| オプション | `--gen` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換されるトークン。既定値は `32`。明示値の範囲検証なし |

## 役割

`--gen` は生成デコードの最大トークン数を設定する。`--spec-check` と `--bench` では単一 slot のデコード長に使われ、`--par-sweep` では各 slot のデコード反復数に使われる。トークン列を通常表示するオプションではなく、これらのチェック・ベンチマークモードの実行量を調整する。

## 使い方

```sh
# 単一 slot のベンチマークで最大 128 トークン分をデコードする
strata-inkling-metal --model ./model.strata --bench --gen 128

# 通常デコードと DSpark デコードの比較を最大 64 トークンで行う
strata-inkling-metal --model ./model.strata --spec-check --gen 64

# 並列ベンチマークの各 slot のデコード反復を 32 回にする（既定値と同じ）
strata-inkling-metal --model ./model.strata --par-sweep --gen 32
```

## 値と既定値

引数解析時の初期値は `32` で、`--gen` を指定すると直後の引数文字列を `atoi` で整数化して上書きする。専用の範囲検証や変換エラー検出はなく、整数に変換できない文字列は `atoi` の結果である `0` になる。繰り返し指定した場合は後の指定が前の値を上書きする。値を省略すると `missing value for --gen` を標準エラーに出して `exit(2)` する（`engine/src/inkling2/metal/ink_metal_main.cpp:423,432-437,451`）。

## 実行時の動作

- `--spec-check` は同じ `gen_n` を通常デコードと spec デコードの両方へ渡し、生成列の一致と速度を比較する（`engine/src/inkling2/metal/ink_metal_main.cpp:560-583`）。
- `--bench` は `gen_n` を `run_greedy_decode` に渡し、デコード結果の件数・時間・速度を集計する。プロンプトは `--prompt-len` の値から作るベンチマーク用列（既定長 `128`）である（`engine/src/inkling2/metal/ink_metal_main.cpp:424,589-603`）。
- `--par-sweep` は `gen_n` を各 slot の生成反復数として `run_parallel_bench` に渡す。並列数ごとの測定は `1, 4, 8, 32, 64` slot の順で、`--parallel` が十分大きい場合に実施される（`engine/src/inkling2/metal/ink_metal_main.cpp:606-613`）。各反復で全 slot の forward を実行し、測定値を標準出力へ出す（同 `:362-414`）。
- 単一 slot のデコードでは、指定値以下のトークンを目標にするが、EOS 到達または `--max-context` による位置上限で先に終了する。`max_new <= 0` の場合はプロンプトの prefill 後にデコードせず戻る（`engine/src/inkling2/metal/ink_metal_main.cpp:138-164,174-176`）。
- `--gen` 単独では生成処理を開始しない。`--bench`、`--spec-check`、`--par-sweep` のいずれもない場合、モデルのロードと初期化後に該当するデコード処理はなく終了する（同 `:481-495,560-616`）。

## 適用条件と副作用

指定数は上限であり、単一 slot の実デコード数は EOS と context 上限の影響を受ける。`--gen 0` や負値では単一 slot の prefill は実行されるが、デコードは行われない。`--par-sweep` では `gen_steps` 回の反復ループが 0 回以下となり、モデル初期化とプロンプト prefill の後にデコード反復なしで集計へ進む。いずれの経路も Metal モデルをロードして GPU forward を実行するベンチマーク／検査用途である。`--gen` 自体によるファイル出力は確認できず、ベンチマーク結果は標準出力に表示される（`engine/src/inkling2/metal/ink_metal_main.cpp:362-414,481-495,589-616`）。

## 出力とエラー

`--gen` 値の形式や範囲が不正でも専用エラーにはならず、`atoi` 後の値で処理されるため、非数値文字列は実質 `0` として扱われる。引数そのものがない場合は標準エラーに不足を表示して終了コード `2`。デコード処理が失敗した場合は `--spec-check` で `[ERROR] plain decode` または `[ERROR] spec decode`、`--bench` で `[ERROR] bench`、`--par-sweep` で `[ERROR] par c=...` を標準エラーに出し、終了コード `1` となる（`engine/src/inkling2/metal/ink_metal_main.cpp:434-437,564-570,596-611`）。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:423,432-437,451` — 既定値、引数の取得、`atoi` 変換、および値省略時の終了経路。
- `engine/src/inkling2/metal/ink_metal_main.cpp:138-164,174-176` — 生成上限、0 以下の場合の prefill 後の早期終了、EOS/context 条件。
- `engine/src/inkling2/metal/ink_metal_main.cpp:560-613` — `--spec-check`、`--bench`、`--par-sweep` への値の適用とエラー表示。
- `engine/src/inkling2/metal/ink_metal_main.cpp:362-414` — 並列ベンチマークにおける `gen_steps` の使用と測定出力。
