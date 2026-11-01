# `--min-tokens`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象 checkout は `main` = `origin/main` で working tree clean。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision` / `strata-vision-hip` / `strata-vision-sycl` |
| オプション | `--min-tokens` |
| 別名 | なし |
| 値 | `N`。`std::atoi` で整数に変換され、正の値のみ encoder 設定に反映される |

## 役割

画像 encoder に、画像を少なくとも指定 token 数になるよう扱うための最小値を渡します。Strata の vision 設定資料は、小さい画像を `N` token 以上に拡大する設定として説明しています。実際の画像処理は mtmd が行い、Strata は値を `image_min_tokens` に設定します（`tools/vision/strata_vision.cpp:116,214-231`、`docs/DETAILS.md:954-960`）。

## 使い方

ビルド済み reader を起動する例です。`--mmproj` と `--model` は必須で、起動後は reader の標準入力プロトコルで画像要求を受け付けます。

```sh
./strata-vision --mmproj ./mmproj.gguf --model ./model.gguf --min-tokens 1024
```

HIP/SYCL build の場合も同じ parser を使い、実行ファイル名はそれぞれ `strata-vision-hip` / `strata-vision-sycl` になります（`tools/vision/CMakeLists.txt:96-116`、索引 [`README.md`](../../../README.md#strata-vision)）。

## 値と既定値

- 値は必須です。値が続かない場合は標準エラーに `--min-tokens needs a value` を出して終了コード 2 で終了します（`tools/vision/strata_vision.cpp:93-98,116`）。
- 既定値は 0 です。未指定時、または変換結果が 0 以下のときは `image_min_tokens` を上書きせず、mtmd の既定設定が残ります（`tools/vision/strata_vision.cpp:90,214-231`）。
- 変換は `std::atoi` で、Strata 側に数値形式・範囲の validation はありません。したがって、数値に変換できない文字列は 0 となって無視され、負数も同様に反映されません。数値の後ろに非数値文字が続く値も、`atoi` が変換した整数が正ならその値が使われます（`tools/vision/strata_vision.cpp:114-116,229-230`）。
- 同じ option を複数回指定すると parser のループで後の値が前の値を上書きします（`tools/vision/strata_vision.cpp:93-98,116`）。

## 実行時の動作

parser は `--min-tokens` の次の argv を整数に変換して `min_tokens` に保存します。起動時に `min_tokens > 0` なら `mtmd_context_params` の `image_min_tokens` に設定し、その設定で mtmd context を初期化します（`tools/vision/strata_vision.cpp:90-91,93-98,116,214-231`）。同じ context を GPU の起動時 warm-up と通常の画像 tokenization / encode の両方で使うため、値は双方に適用されます（`tools/vision/strata_vision.cpp:249-274,286-309`）。

`--max-tokens` も正の値なら同じ context の `image_max_tokens` に設定されますが、Strata は min/max の大小関係を事前検証しません。max の制限を超えて画像が token 化された場合は、最大値の 1/8 の許容幅を超えると画像を拒否します。これは `--max-tokens` 側の拒否経路であり、`--min-tokens` 固有の validation ではありません（`tools/vision/strata_vision.cpp:115-116,229-230,316-319`）。min が max より大きい場合の mtmd 内部の処理順や結果は、Strata のソースだけでは確認できません。

Strata server は vision 設定の `min_tokens` が truthy のときだけ、この option と値を reader の起動 argv に追加します。ソースコメント上、このキーは手編集する設定です（`serve/server.py:2808-2820`）。設定ファイル側の validation や負値の扱いはこの CLI parser とは別の経路です。

## 適用条件と副作用

CPU/GPU のいずれでも、正の値は同じ `image_min_tokens` に設定されます。GPU は `--gpu` により `cp.use_gpu` が有効な場合で、HIP/SYCL build の GPU reader は実 GPU の検出にも依存します（`tools/vision/strata_vision.cpp:101,150-160,214-230`）。build variant は CMake option で変わりますが、この option の parser は共通です（`tools/vision/CMakeLists.txt:18-31,96-116`）。

最小 token 数を上げると画像 token 数が増え得ます。Strata の利用者向け資料は、より大きな最小値は画像回答を変え、encode 時間を増やすと説明しています（`docs/DETAILS.md:954-960`）。起動例では GPU reader の場合に warm-up も行われますが、CPU reader は warm-up しません（`tools/vision/strata_vision.cpp:249-255`）。具体的な拡大アルゴリズム、全モデルでの実際の token 数、および最小値と最大値が衝突する場合の mtmd 内部の挙動は、この Strata checkout では確定できません。

## 出力とエラー

`--min-tokens` 自体に専用の警告・エラー経路はありません。画像 encode が成功すれば embedding 出力ファイルに token 数などを書き込み、標準出力に `OK ...` を返します。画像の前処理・encode・出力書き込み失敗時は標準出力に `ERR ...` を返してその要求を続行します（`tools/vision/strata_vision.cpp:302-334`）。min/max の相互作用によりこの要求経路がどうなるかは mtmd の実装依存のため確認範囲外です。

## 根拠

- parser、値変換、既定値、引数不足・未知 option の扱い: `tools/vision/strata_vision.cpp:90-128`
- `image_min_tokens` / `image_max_tokens` の設定: `tools/vision/strata_vision.cpp:214-231`
- GPU warm-up と token 数の観測: `tools/vision/strata_vision.cpp:249-280`
- 通常の画像要求、encode、max token 超過拒否、embedding 出力: `tools/vision/strata_vision.cpp:286-338`
- server 設定から reader argv への転送: `serve/server.py:2808-2820`
- 利用者向け vision 設定の説明: `docs/DETAILS.md:954-960`
- tool scope と build variant: `docs/cli/README.md:14,1511-1526`、`tools/vision/CMakeLists.txt:18-31,96-116`

調査は上記 revision の Strata ソースと同 checkout の資料に限定しました。CLI `--help` の実行、build、テスト、GPU 実行は行っていません。mtmd 内部の値の validation・tokenization 規則、および Release artifact ごとの同梱状態はこの文書では独立に検証していません。
