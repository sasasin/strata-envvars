# `--layers`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal` |
| オプション | `--layers` |
| 別名 | なし |
| 値 | 整数（`atoi` で変換。範囲検証なし） |

## 役割

Metal backend の offline 実行で、各 forward pass が先頭から処理するモデル層の数を制限します。ソースコメントでは部分実行を bisect（切り分け）する用途とされています。全層を使う通常実行では、モデル層数を超える指定は実モデルの層数までに制限されます。

## 使い方

```sh
# Apple Silicon 上でモデルと token ID ファイルを使い、先頭 20 層だけで offline 実行
strata-hy4-metal --model SQ64.strata --tokens ids.txt --layers 20
```

## 値と既定値

- 省略時の値は `42` です。
- 値は `atoi` で整数化されます。数値として解釈できない文字列は `atoi` の結果として 0 になり、部分文字列だけが数値として読める場合もその数値が使われます。厳密な整数構文・範囲の検証はありません。
- 同じ引数を複数回指定すると parser のループで後の値が先の値を上書きします。
- Runner への設定時に `min(指定値, モデルの層数)` が使われます。したがって大きすぎる正の値は全層数相当になります。一方、0 や負値を下限で補正する処理はありません。
- 値を伴わない `--layers` に対する個別の引数不足検査は parser にありません。安全な呼び出しでは整数値を必ず続けてください。

## 実行時の動作

parser は `--layers N` を `n_layers_run` に格納し、offline Runner の `n_run` にモデル層数との小さい方を設定します。各 `forward_chunk` は層番号 0 から `n_run - 1` まで attention と MLP を実行し、その後の head 処理は通常どおり呼ばれます。そのため、層数をモデル全体より少なくすると中間層までの表現に対して出力 head が実行され、モデルの通常の全層推論結果とは異なります。0 または負値では層ループが実行されません。

この値は `--serve` 経路には適用されません。server 分岐は `Runner` の生成と `n_run` の設定より前に `hy4_serve_main` を呼び出します。また `--load-only` はモデル読込後、offline Runner の生成より前に終了します。

## 適用条件と副作用

- 対象は `strata-hy4-metal` の Metal 実装です。`--serve` を指定した実行では `--layers` が Runner に転送されず、この制限は適用されません。
- 値は offline 推論の各 prefill/decode forward に共通して使われます。部分層数は切り分け向けであり、通常の全層モデル推論を意味しません。
- このオプション自体に固有のファイル書き込みやモデル変更はありません。実行時の一般的な出力動作は他の引数（例: dump/save logits）に依存します。

## 出力とエラー

`--layers` の値に対する専用の警告・エラー・終了コード処理は見当たりません。未知のフラグは `ERR unknown flag ...` を stdout に出し、`unknown arg ...` を stderr に出して終了コード 2 となりますが、これは `--layers` の通常の値検証ではなく parser 全体の未知引数処理です。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1491` — `--layers` の既定値が 42。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1526` — 値を `atoi` で読み込み。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1604-1609` — 未知引数の出力と終了コード 2。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1635-1636` — `--load-only` の早期終了と、その後の serve 分岐。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1674-1676` — serve 分岐が offline 実行経路より前に戻る。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:323` — Runner の `n_run` と部分実行用途のコメント。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1300-1328` — forward pass の層ループ。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1332-1349` — 層ループ後の出力 head。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1753` — 指定値をモデル層数で上限 clamp して Runner に設定。

調査範囲は上記 revision の Strata 所有ソースに限ります。値の整数変換は標準 C ライブラリの `atoi` に委ねられているため、その細部以上の入力検査は Strata 側で確認できません。CLI `--help` は実行せず、parser と使用箇所を根拠にしました。
