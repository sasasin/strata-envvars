# `TQ_OUT`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更は表示されなかった。

## 役割

同梱 trellis エンコーダーのビルドスクリプト `tools/trellis/build.sh` が、生成物を置くディレクトリを指定します。Strata の通常実行ファイルやサーバーが読む環境変数ではなく、このスタンドアロンツールのビルド時だけ使われます。

## 値と判定

スクリプトは `OUT=${TQ_OUT:-build-tqenc}` と代入し、値を文字列としてパスに使います。シェルの `${parameter:-word}` 展開により、環境変数が未設定または空文字なら `build-tqenc` が選ばれます。空白だけの値を含むその他の非空文字列はそのまま `OUT` になります。数値・真偽値としての parse、範囲確認、正規化はありません。

| `TQ_OUT` | 出力先 |
|---|---|
| unset または空文字 | `build-tqenc` |
| 非空文字列 | その文字列 |

相対パスはスクリプトを起動したときの作業ディレクトリ基準です。値は `mkdir -p "$OUT"` と各コンパイラの `-o "$OUT/..."` に引用符付きで渡されるため、空白を含むパスも一つのパス引数になります。絶対パスも指定できます。

## 有効になる条件

`sh tools/trellis/build.sh [test|lib|hip]` を実行したときに有効です。引数（`test` / `lib` / `hip`）は作る対象を選び、`TQ_OUT` はいずれの対象でも出力先を選びます。両者に優先順位はなく、CLI 引数が出力先を上書きする処理もありません。コンパイラは別環境変数 `CXX` が設定されていればそれを使い、未設定または空なら `g++` です（`hip` 分岐は `g++` / `hipcc` を直接呼びます）。

この変数は `tools/tqenc.py` のライブラリ探索先を変更しません。Python wrapper は `TQENC_LIB` と固定の `build-tqenc/libtqenc.so` を探索し、HIP wrapper も `TQENC_HIP_LIB` と固定の `build-tqenc/libtqenc_hip.so` を探索します。したがってカスタム `TQ_OUT` に `lib` または `hip` の生成物を置いた場合、wrapper からその場所を使うには別途対応する `TQENC_LIB` または `TQENC_HIP_LIB` を指定する必要があります。

## 実行時の詳細

`TQ_OUT` はスクリプト開始時に `OUT` へ一度展開され、以降の生成物の出力先に使われます。実行中の環境変更を再読込する処理や cache はありません。対象は Linux x86-64 向けの standalone build script であり、CUDA/HIP/SYCL backend、Strata サーバーモード、モデルのロード状態による条件分岐はありません。`hip` はビルド対象を選ぶスクリプト分岐ですが、TQ_OUT 自体はその分岐に関係なく出力ディレクトリを指定します。

スクリプトは `set -e` のため、`mkdir` または選択されたコンパイルコマンドが失敗するとそこで終了し、通常の最後の `built "$OUT"` 表示には到達しません。失敗時の stderr と終了コードは失敗したコマンドに由来します。正常に分岐を終えると標準出力へ `built <出力先>` を表示します。なおスクリプトの `case` に列挙される実装分岐は `lib`、`hip`、`test` です。未知の引数では分岐内のビルドをせず、`built "$OUT"` を表示して終了します。

## 根拠

- `tools/trellis/build.sh:1-9` — standalone build 用途、既定ディレクトリ、値の展開、ディレクトリ作成、`CXX` の既定値。
- `tools/trellis/build.sh:10-29` — CLI target ごとの出力先利用、`set -e` 下のコンパイル、完了表示。
- `tools/tqenc.py:38-54` — CPU encoder wrapper の `TQENC_LIB` と固定既定候補、および見つからない場合の例外。
- `tools/tqenc.py:113-123` — HIP wrapper が `TQENC_HIP_LIB` と固定既定候補を使うこと。
- `tools/trellis/README.md:21-28` — Linux x86-64 のビルド例と、生成物の既定ディレクトリを使う後続コマンド。
