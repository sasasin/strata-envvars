# `REPO`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`REPO` は `engine/sycl/tools/build.sh` が SYCL 開発ビルドの Strata checkout のルートを指定するために読む環境変数である。値が使われる場合、スクリプトは `$repo/engine/sycl` を CMake のソースディレクトリとして渡す。未設定または空文字なら、スクリプトを実行したカレントディレクトリから `git rev-parse --show-toplevel` で求めたルートを使う。これは開発・ビルド用スクリプト内の設定であり、Strata の通常実行時の動作を変える環境変数ではない（`engine/sycl/tools/build.sh:38-44`）。

## 値と判定

| 条件 | unset | 有効になる値（例） | 空文字・無効値の扱い |
| --- | --- | --- | --- |
| `engine/sycl/tools/build.sh` の実行時 | `git rev-parse --show-toplevel` の出力を使う | 空でない値（例: `/work/Strata`）を `repo` に代入する | `:-` の Bash 展開なので未設定と同様に Git ルートへフォールバックする。値の存在確認、パス検証、正規化は行わない（`engine/sycl/tools/build.sh:38`）。 |

シェル文字列を数値や真偽値に変換せず、空でない文字列をそのまま代入する。したがって `0`、`false`、空白を含む文字列も設定値として扱われ、`REPO=0` や `REPO=false` は無効値として拒否されない。ただし値が実在する checkout のパスであることは検査されない。代入後の `$repo/engine/sycl` は引用符なしで展開されるため、空白を含む値は単一のパス引数として扱われない（`engine/sycl/tools/build.sh:38,40-43`）。

## 有効になる条件

- この変数を読むのは SYCL 開発用 `engine/sycl/tools/build.sh` を実行した場合だけである。同スクリプトは `/opt/intel/oneapi/setvars.sh` を試行した後、`repo` を設定する（`engine/sycl/tools/build.sh:1-8,38`）。
- `$BUILD_DIR/build.ninja` が存在しない場合、`REPO` のパスを `cmake -S` に渡してビルドツリーを構成する。`BUILD_DIR` が未設定または空ならビルド先は `$repo/build-sycl`（`engine/sycl/tools/build.sh:39-41`）。
- `build.ninja` が既にある場合、初回の CMake 構成は飛ばされる。そのとき `REPO` を変更しても既存の CMake キャッシュのソース位置は切り替わらない。`I8_ESIMD` が空でない場合の再構成も同じ `$repo/engine/sycl` を指定し、変更する設定は `STRATA_SYCL_I8_ESIMD` のみ（`engine/sycl/tools/build.sh:40-43`）。
- `build.sh` の位置引数は `cmake --build` の `--target` に使われ、`REPO` の値を上書きしない（`engine/sycl/tools/build.sh:44`）。

## 実行時の詳細

スクリプト実行中の 1 回、`repo=${REPO:-$(git rev-parse --show-toplevel)}` でシェル変数 `repo` に値を保存する。したがって実行中に親プロセス側の環境値を変えて再読込する仕組みはない。フォールバックの Git コマンドはスクリプトのカレントディレクトリで実行される。フォールバック結果を検査する分岐はなく、CMake のソース指定と既定ビルド先の組み立てに使われる（`engine/sycl/tools/build.sh:38-41`）。

`docs/INTEL.md` は Docker 実行時に `-e REPO=/work/$H` を指定して同スクリプトを呼ぶ例を示しており、SYCL 開発ビルドでの checkout 指定という用途と一致する（`docs/INTEL.md:53-83`）。

## ログと測定値

`REPO` 自体の値や、空値から Git ルートへフォールバックしたことを出力するログはない。CMake 構成の出力は末尾 15 行に絞られ、ビルド時には `BUILD EXIT <終了コード>` と `errors: <件数>`、失敗ターゲット名が表示される。最後の終了コードは CMake build のパイプライン先頭のステータスである。無効なパスに対する `REPO` 固有の診断文はなく、失敗は CMake/Ninja のエラーとこの一般的な終了表示を通じて観測される（`engine/sycl/tools/build.sh:40-50`）。

## 根拠

- `engine/sycl/tools/build.sh:38-44` — `REPO` の読み取り、空値時の既定値、CMake のソース指定、既存 build.ninja 時の分岐、ビルド呼び出し。
- `engine/sycl/tools/build.sh:45-50` — ビルド結果・エラー件数・失敗ターゲット・コンパイラ失敗のログと終了コード。
- `docs/INTEL.md:53-83` — SYCL 開発ビルドの Docker 実行例と `REPO` の指定方法。
