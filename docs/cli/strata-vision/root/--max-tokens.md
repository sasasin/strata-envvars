# `--max-tokens`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

- 対象: `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` の root scope
- 調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`
- 調査日: 2026-11-01
- 対象 checkout の状態: `main...origin/main`、working tree clean

## 使い方

```sh
strata-vision --mmproj ./mmproj.gguf --model ./model.gguf --max-tokens 1024
```

`--max-tokens` は画像 encoder が画像から作る image token 数の上限値として指定します。`strata-vision` は `--mmproj` と `--model` を必須とし、標準入力から `ENC <画像パス> <出力パス>` を受け付ける常駐プロセスです。オプションを指定するだけで画像を処理する形式ではありません（`tools/vision/strata_vision.cpp:7-15, 125-128, 283-291`）。

## 値と既定値

値は `N` の位置に整数文字列を1つ取ります。parser は `std::atoi` で変換し、明示的な範囲・書式検証を行いません。したがって数値に変換できない値は `0` となり、値が `0` 以下の場合と同じく context へ上限を設定しません。オプションを省略した場合も内部値は `0` で、上限は設定されません。値を省略すると `--max-tokens needs a value` を stderr に出して終了コード `2` で終了します（`tools/vision/strata_vision.cpp:90, 93-97, 115`）。

同じオプションを複数回指定した場合、parser は値を順に代入し、最後に読んだ値が残ります（`tools/vision/strata_vision.cpp:93-97, 115`）。

## 実行時の動作

値が正数の場合、`mtmd_context_params.image_max_tokens` に設定され、vision encoder の context 初期化に渡されます。`--min-tokens` も正数なら別途 `image_min_tokens` に設定されますが、Strata 側に両値の組み合わせを検証する処理はありません（`tools/vision/strata_vision.cpp:214-231`）。

この設定だけで全モデルに対して厳密な上限が保証されるわけではありません。GPU 利用時は起動時の warm-up で生成された token 数が `max_tokens + floor(max_tokens / 8)` を超えると stderr に警告します。実際の `ENC` 処理でも同じ閾値を超えた画像は拒否され、出力先を開かず、標準出力へ `ERR ... (vision.max_tokens)` を返して次の入力を処理します。閾値以下の端数超過は拒否されない場合があります（`tools/vision/strata_vision.cpp:249-279, 316-334`）。

## 適用条件と副作用

上限値は、正数を指定した場合に限り mtmd context に渡されます。ソースには「このモデルでは上限が適用されない」ケースが明記されており、GPU warm-up で超過が判明すると警告し、画像ごとの処理では許容幅を超えた画像を拒否します。CPU 利用時にも画像ごとの拒否判定はありますが、起動時 warm-up 自体が行われないため、その警告はありません（`tools/vision/strata_vision.cpp:225-231, 249-279, 316-319`）。

超過判定を通過した画像は、指定された出力ファイルを `wb` で開いて書き込みます。同名ファイルがあれば切り詰められます。上限超過時はそのファイルを開かないため、このオプションによる拒否経路では既存ファイルは変更されません（`tools/vision/strata_vision.cpp:316-328`）。

この parser は各 build variant で共通です。HIP / SYCL variant など、実行ファイル名や GPU backend の差は `--max-tokens` の解釈を変えません（`tools/vision/CMakeLists.txt:18-31, 96-115`）。

## 出力とエラー

- 値を省略: stderr に `--max-tokens needs a value`、終了コード `2`（`tools/vision/strata_vision.cpp:95-97`）。
- 数値が `0` 以下、または数値に変換できない値: 起動時 parser は拒否せず、上限設定と画像ごとの上限判定を行いません（`tools/vision/strata_vision.cpp:115, 229, 317`）。
- GPU warm-up が許容閾値を超過: stderr に `WARNING ... the limit is not applied for this model` を出して起動を続けます（`tools/vision/strata_vision.cpp:273-279`）。
- 画像が許容閾値を超過: stdout に `ERR ... (vision.max_tokens)` を出し、常駐プロセスは終了せず次の入力へ進みます（`tools/vision/strata_vision.cpp:316-335`）。

## 根拠と調査範囲

- parser、変換、既定値: `tools/vision/strata_vision.cpp:90-97, 113-128`
- context 設定と初期化: `tools/vision/strata_vision.cpp:214-235`
- warm-up 警告: `tools/vision/strata_vision.cpp:249-283`
- 画像ごとの拒否と出力ファイル処理: `tools/vision/strata_vision.cpp:286-335`
- 実行ファイルと variant: `tools/vision/CMakeLists.txt:18-31, 94-115`
- 配置と scope: `docs/cli/README.md` の `strata-vision` 節。調査基準: `docs/cli/001_investigation.md`。

同一 revision の `--help` は実装されていません。ソース内の usage 表示は必須引数の案内のみで、`--max-tokens` を含む一覧表示はありません（`tools/vision/strata_vision.cpp:123-128`）。mtmd ライブラリ内部で各モデルに対して token 上限を適用する詳細はこの Strata 側ソースからは確認できないため、モデルごとの厳密な上限動作は断定していません。
