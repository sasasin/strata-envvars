# `strata-vision --flash-attn`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-vision` |
| コマンド | `strata-vision`（トップレベル） |
| オプション | `--flash-attn` |
| 別名 | なし |
| 値 | 値を1つ取る。値の内容は検査も保存もされない |

## 役割

`--flash-attn` は旧呼び出し元との互換性のため受理される引数です。現行の Strata vision reader では値を読み捨てるだけで、attention の方式や GPU 使用を切り替えません。索引上の適用範囲は `strata-vision`、`strata-vision-hip`、`strata-vision-sycl` で共有される root parser です（`docs/cli/README.md` の `strata-vision` 節、`docs/cli/000_cli_tools.md` の tool-id 表）。

## 使い方

```sh
# 既存呼び出しとの互換性のため値を渡せますが、現行 reader の動作は変わりません。
strata-vision --mmproj ./vision-mmproj.gguf --flash-attn on
```

## 値と既定値

- オプションを指定すると、直後の argv を1つ消費します。`on` / `off` など値の内容による検証はなく、その値は保存されません（`terminal/tools/vision/strata_vision.cpp:61-66,90`）。
- 値の省略時に設定される既定値はありません。次の引数がない場合は `--flash-attn needs a value` を標準エラーに出して終了コード `2` で終了します（同 `:63-65`）。
- 複数回指定しても、各指定で次の引数を1つずつ消費するだけです。重複回数による設定変更はありません（同 `:61-91`）。

## 実行時の動作

parser は `--flash-attn` の分岐で `next()` を呼び、その戻り値を破棄します。reader の設定構造体 `OwnReaderOptions` に flash attention 用の項目はなく、`own_reader_run(o)` に渡る設定にも反映されません（`terminal/tools/vision/strata_vision.cpp:56,90,140`、`terminal/tools/vision/own/own_reader.h:14-20`）。したがって、オプション単独で encoder の attention 実装を変えたり、出力・ログを追加したりする効果はありません。

`next()` は次の argv が `--gpu` など別オプションに見えるかを判定しません。そのため `--flash-attn --gpu` と書くと `--gpu` が値として消費され、GPU 指定としては処理されません（`terminal/tools/vision/strata_vision.cpp:63-70,90`）。互換引数を付ける場合は、値を伴う実際のオプションより後ろに置くか、別オプションに見えない値を渡してください。

## 適用条件と副作用

この引数は CPU reader と GPU reader、ならびに共有 parser を使うビルドで同じく読み捨てられます。GPU を有効にするのは別の `--gpu` 分岐です（`terminal/tools/vision/strata_vision.cpp:67-70,90`）。受理された flash-attn 値は reader に渡らず、ファイル・ネットワーク・プロセス・GPU に追加の副作用を起こしません。後続の `own_reader_run` は通常どおり mmproj の読込と stdin/stdout の reader protocol を実行します（`terminal/tools/vision/own/own_reader.cpp:42-59,120-158`）。

## 出力とエラー

正しく値が続く `--flash-attn` 自体は出力しません。値が欠ける場合の標準エラーと終了コードは前節のとおりです。未知の引数は `unknown argument <引数>` を標準エラーに出して終了コード `2` になります（`terminal/tools/vision/strata_vision.cpp:63-65,91`）。`--mmproj` 未指定時は usage を標準エラーに出し終了コード `2` です（同 `:93-95`）。

起動後の reader は `READY ...` を標準出力に出し、入力コマンドに応じて `OK ...` / `ERR ...` を返します。mmproj の読込失敗など起動前の reader エラーは標準出力の `ERR ...` と非ゼロ終了コードです（`terminal/tools/vision/own/own_reader.cpp:45-59,120-158`）。これらは `--flash-attn` の値による分岐ではありません。

## 根拠

- `terminal/tools/vision/strata_vision.cpp:56-66,67-95` — 設定の初期化、値の消費、別オプションの処理、missing-value / unknown-argument / mmproj の失敗経路。
- `terminal/tools/vision/strata_vision.cpp:90,140` — `--flash-attn` 値の破棄と reader 呼び出し。
- `terminal/tools/vision/own/own_reader.h:14-20` — reader に渡す設定項目。flash attention の設定項目はない。
- `terminal/tools/vision/own/own_reader.cpp:42-59,120-158` — reader の起動時エラー、READY と入出力 protocol。
