# `REPO`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`REPO` は通常の Strata エンジンの実行設定ではなく、SYCL 開発用ビルドスクリプト `sycl/tools/build.sh` が Strata checkout のルートを指定するために読みます。指定したルートの `sycl/` を CMake のソースディレクトリにし、既定の build directory もそのルート内の `build-sycl` に置きます。Docker を使う Intel SYCL ビルド手順では、コンテナ内の checkout 位置を `REPO` に渡しています（`docs/INTEL.md:69-79`、`docs/INTEL_ARC.md:73-79`）。

## 値と判定

シェルの `${REPO:-$(git rev-parse --show-toplevel)}` で読みます。値をパース・検証・正規化しません。

| 状態 | `repo` の値 |
| --- | --- |
| `REPO` 未設定 | スクリプトを起動した現在のディレクトリに対する `git rev-parse --show-toplevel` の出力 |
| `REPO` が空文字 | 同じ git checkout ルートへのフォールバック |
| `REPO` が非空 | その文字列をそのまま使用 |

非空値が実在する checkout か、絶対パスか、`sycl/` を含むかは確認しません。後続のコマンドでは `$repo` が引用符なしで展開されるため、空白を含むパスは一つのパスとして渡されません。`REPO` 未設定・空文字時の fallback は、スクリプトを git checkout 内から起動することを前提にしています。

## 有効になる条件

この変数を読むのは `sycl/tools/build.sh` の SYCL 開発ビルド経路です。エンジン起動時や通常の CLI / サーバー処理からは読みません。スクリプトは `REPO` を明示指定した場合にその値を優先し、未設定または空文字の場合に git ルートを使います。

`BUILD_DIR` は build directory を別途指定でき、未設定・空文字なら `$repo/build-sycl` です。これは `REPO` のソースルート指定を置き換えません。ビルドターゲット引数も CMake の `--target` に渡されるだけで、ソースルートを変更しません（`sycl/tools/build.sh:38-44`）。

## 実行時の詳細

スクリプト実行時に `repo` を一度決め、その後 `cmake -S $repo/sycl` として構成し、構成済み directory に対してビルドします。プロセス内の再読み込みや cache はありません。`build.ninja` が既にある場合、通常の構成コマンドはスキップされます。そのため、同じ `BUILD_DIR` を再利用して `REPO` だけ変えても、既存の CMake 構成が自動で作り直されるとは限りません。`I8_ESIMD` が非空なら別の CMake 構成コマンドも実行されますが、そこでも `-S $repo/sycl` が使われます（`sycl/tools/build.sh:38-43`）。

`REPO` 自体に対応するログや警告はありません。指定パスが不正で CMake 構成に失敗しても、スクリプトは `set -e` を使っていないため、その場で終了せず後続の build を試みます。ビルド段階では `BUILD EXIT <終了コード>` を表示し、`cmake --build` の終了コードをスクリプトの終了コードにします。詳細ログは `$b/build.log` への記録を試みます（`sycl/tools/build.sh:40-52`）。

## 根拠

- `sycl/tools/build.sh:38-44` — `REPO` と git ルートの選択、`BUILD_DIR` の既定値、CMake 構成・ビルドでの使用。
- `sycl/tools/build.sh:7,40-52` — `set -e` がないこと、構成失敗後の継続、ビルド終了コードと表示。
- `docs/INTEL.md:69-79`、`docs/INTEL_ARC.md:73-79` — Docker 内から SYCL ビルドを行う手順と `REPO` の指定例。挙動の根拠は実装 `sycl/tools/build.sh` によります。

