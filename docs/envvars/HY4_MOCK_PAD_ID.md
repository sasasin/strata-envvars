# `HY4_MOCK_PAD_ID`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

この変数は `terminal/tools/hy4_mock_engine.py` が画像 placeholder として数える token ID を指定する。対象は `strata-hy4 --serve` の代わりに serve / Control / app の protocol を試す mock engine であり、通常の Strata engine のモデル計算を設定する変数ではない。同スクリプトは module-level で値を `IMAGE_PAD_ID` に読み込み、受信した `GEN` 行の token ID 列にその ID が何個あるかを数える。画像ファイルが指定されている場合、その個数とファイル数が異なると mock はエラー応答を返す（`terminal/tools/hy4_mock_engine.py:1-7,49-50,113-130`）。

## 値と判定

Python の `os.environ.get()` で読み、取得値が falsy（未設定または空文字）なら `120120` を使い、それ以外は `int()` で変換する（`terminal/tools/hy4_mock_engine.py:49`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| mock engine の起動 | `IMAGE_PAD_ID` は `120120` | 整数に変換できる文字列。`120120`、`0`、`-1`、`+42` など。範囲制限はない | 空白だけの文字列や `abc` など、`int()` が変換できない値は import 時に `ValueError` となり、engine の処理開始前に失敗する |

空文字は未設定と同じ fallback になる。空白は strip されず、空白だけなら変換エラーになる。変換は Python の `int()` によるため、小数表記や `true` / `false` は受理されない。`0` や負数も整数として受理されるが、受信 ID 列に一致する値がなければ placeholder 数には寄与しない。大文字小文字の比較規則はなく、文字列から数値への変換で判定される（`terminal/tools/hy4_mock_engine.py:49,113-118,127`）。

## 有効になる条件

- この値を読むのは `terminal/tools/hy4_mock_engine.py` を起動した場合だけである。スクリプトの説明は、serve / Control / app の protocol を試すための `strata-hy4 --serve` stand-in としている（`terminal/tools/hy4_mock_engine.py:1-7`）。
- 画像 placeholder の不一致チェックがエラーになるのは、`GEN` 行に画像ファイルが含まれる場合だけである。画像指定がない場合は token 列中の一致数を数えるが、その数を使った不一致判定は行わない（`terminal/tools/hy4_mock_engine.py:117-129`）。
- `HY4_MOCK_CAPS` に `images=1` がなければ mock は `image` key を unsupported として先に `ERR` を返すため、画像 placeholder 数の照合まで進まない。`images=1` の場合は `image` key を受け付け、続いてこの変数で数えた placeholder 数を照合する（`terminal/tools/hy4_mock_engine.py:53-55,75-77,123-129`）。
- OS、GPU backend、build macro、実モデルの状態による分岐は、この読み取り箇所にはない。通常の Strata engine がこの変数を読む根拠は見つからなかった。

## 実行時の詳細

値は module-level の `IMAGE_PAD_ID` 初期化時、すなわち mock の `main()` に入る前に一度読み込まれる。したがって `--info` 分岐でも import 時に整数変換され、同じプロセスの実行中に環境を変更しても再読み込みされない（`terminal/tools/hy4_mock_engine.py:49,58-63`）。

`GEN` 行を処理すると、末尾の ID リストを整数列へ変換し、`ids.count(IMAGE_PAD_ID)` で一致数を求める。画像パスの数と一致数が異なる場合は `ERR image: {画像ファイル数} files for {placeholder数} image placeholders` を stdout に出し、そのリクエストを続行せず次の行を待つ。一致すれば画像ファイルの読み取り可能性を確認し、prompt token 数などの後続処理へ進む（`terminal/tools/hy4_mock_engine.py:113-145`）。

## ログと測定値

変数の設定値や placeholder 数を個別に表示するログはない。不一致時の stdout 応答は `ERR image: {len(images)} files for {pads} image placeholders`。ID 列や画像数の整数変換に失敗した `GEN` 行は `ERR bad GEN line` となる（`terminal/tools/hy4_mock_engine.py:115-129`）。

値自体の `int()` 変換失敗を処理する例外ハンドラーは module-level の読み取り箇所にないため、mock の起動前に例外で失敗する。独自の警告文や fallback は実装されていない（`terminal/tools/hy4_mock_engine.py:49`）。性能測定値は該当しない。

## 根拠

- `terminal/tools/hy4_mock_engine.py:1-7` — mock engine の用途と起動例。
- `terminal/tools/hy4_mock_engine.py:49-50` — 環境値の読み取り、fallback、整数変換。
- `terminal/tools/hy4_mock_engine.py:58-78` — import 後の `--info` / serve 処理と mock capability。
- `terminal/tools/hy4_mock_engine.py:113-145` — `GEN` 行の解析、placeholder 数照合、観測可能な応答。
