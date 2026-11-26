# `TQ_OUT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

`TQ_OUT` は、Trellis encoder の単体ビルドスクリプト `terminal/tools/trellis/build.sh` が生成物を置く出力ディレクトリを指定する。通常はスクリプトの作業ディレクトリ（README の手順では Strata リポジトリのルート）に `build-tqenc` を作る。非空の値を指定するとそのパスを使う。これは単体 encoder のビルド用であり、Strata engine の実行時設定として読む箇所は確認できない（`terminal/tools/trellis/build.sh:2-6,12-26`）。

## 値と判定

スクリプト開始時に POSIX shell の `${TQ_OUT:-build-tqenc}` で一度展開する。パースや値域検査はなく、未設定または空文字なら `build-tqenc`、それ以外は与えられた文字列を出力パスとして使う。相対パスはスクリプトを起動したカレントディレクトリ基準、絶対パスはそのまま使われる。出力先の作成に失敗すると `set -e` により後続処理を止める（`terminal/tools/trellis/build.sh:4-6`）。

| 条件 | unset | 有効になる値（例） | 空文字・その他の値 |
|---|---|---|---|
| `terminal/tools/trellis/build.sh` を実行 | `build-tqenc` | `build-tqenc`、`/tmp/tq-out` など非空のパス文字列 | 空文字は `build-tqenc` に fallback。`0`、`false`、空白を含む文字列なども真偽値として判定せず、そのままパスとして扱う。 |

値の大小文字・数値形式・境界値を検証しない。環境変数値を CLI 引数で上書きする仕組みはなく、位置引数 `$1` はビルドモードの選択に使われる。`CXX` はコンパイラ選択用で、`TQ_OUT` と優先順位を競わない（`terminal/tools/trellis/build.sh:5-10`）。

## 有効になる条件

- `terminal/tools/trellis/build.sh` を起動した場合にだけ評価される。Strata の通常の engine / server / CLI 実行での読み取り箇所は見つからない（`terminal/tools/trellis/build.sh:1-6`）。
- 出力先は起動時のカレントディレクトリに対する相対パスとして解決される。スクリプトのコメントと README はリポジトリ root からの実行を案内している（`terminal/tools/trellis/build.sh:2-3`; `terminal/tools/trellis/README.md:21-25`）。
- スクリプトの位置引数は生成物の種類を選ぶ。`lib`、`hip`、`test`（引数省略時の既定）分岐で `TQ_OUT` 以下に共有ライブラリ、HIP encoder/test、または CPU encoder/test の生成物を置く。GPU 実行やモデル状態による `TQ_OUT` 自体の判定はない（`terminal/tools/trellis/build.sh:10-27`）。
- `TQ_OUT` を別の環境変数や CLI 引数が上書きする処理、ビルド成果物を後でこの値から自動探索する処理は、この読み取り箇所にはない。Python wrapper のライブラリ探索は `TQENC_LIB` と固定の `build-tqenc/libtqenc.so` を参照する（`terminal/tools/tqenc.py:38-54`）。

## 実行時の詳細

スクリプトの最初に値を `OUT` に代入し、`mkdir -p "$OUT"` で出力先を作る。その後、選択された分岐の compiler `-o` 引数や linker 入力で同じ `$OUT` を使う。したがって指定値が変えるのはビルド生成物の保存場所で、encoder の値計算や Strata の推論処理ではない（`terminal/tools/trellis/build.sh:4-6,10-26`）。

読み取りはスクリプト起動時に一度で、値をキャッシュする常駐プロセスやリクエスト単位の再読込はない。起動後の環境変更を再評価するコードもない。別プロセス起動時には、そのプロセスに渡された環境値がスクリプトで評価される。`OUT` はスクリプト内で後続コマンドのパス引数に使われる。

## ログと測定値

スクリプトは最後に `built "$OUT"` を標準出力へ出す。ディレクトリ作成やコンパイルに失敗した場合は `set -e` により途中終了するため、この成功メッセージには到達しない。Strata 独自の警告・エラー文言はこの変数の処理にはない。測定値は該当しない（`terminal/tools/trellis/build.sh:4-6,28-29`）。

## 根拠

- `terminal/tools/trellis/build.sh:2-6` — 用途コメント、値の展開、ディレクトリ作成。
- `terminal/tools/trellis/build.sh:7-29` — compiler / モード分岐、各生成物の出力先、完了メッセージ。
- `terminal/tools/trellis/README.md:21-25` — 単体 build/test の起動例。
- `terminal/tools/tqenc.py:38-54` — Python wrapper のライブラリ探索先は `TQENC_LIB` と固定パスで、`TQ_OUT` を参照しない。
