# `AOT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査時の作業ツリーは `main...origin/main` で変更なし。

## 役割

`AOT` は SYCL GPU エンジンのビルド用シェルスクリプトが参照する環境変数です。`sycl/tools/build.sh` と `packaging/build_sycl_linux.sh` が値を CMake の `STRATA_SYCL_AOT` に渡し、空でなければ SYCL の ahead-of-time device target を指定します。実行時の Strata エンジンが `AOT` を読む箇所は見つかりません。

## 値と判定

| 入口 | 未設定・空文字 | 非空値 | 検証・失敗 |
| --- | --- | --- | --- |
| `sycl/tools/build.sh` | `${AOT:-}` を空として CMake に渡す。JIT 構成になる | 値を文字列として `-DSTRATA_SYCL_AOT=...` に渡す | このスクリプト自体は一般的な値検証をしない。`bmg` または `lnl` で始まる値は別途 `ocloc` 既知不具合ガードの対象 |
| `packaging/build_sycl_linux.sh` | `aot` は空。CMake には AOT 指定を追加せず、成果物メタデータは `JIT from SPIR-V` とする | `bmg-*` またはカンマ区切りの `bmg-*` 形式を許可し、CMake に渡す | 他の形式は `build_sycl_linux.sh: AOT is empty ...` を stderr に出して終了コード 2。非空なら `ocloc` が PATH に必要で、なければ `AOT needs ocloc ...` を出して終了コード 2 |

値の数値変換や真偽値化はありません。`sycl/tools/build.sh` では `bmg` / `lnl` の先頭一致を既知 `ocloc` ガードに使い、CMake に値全体を渡します。パッケージ用スクリプトは空文字を除き `bmg-` で始まる形式に制限します。どちらもデバイス名の完全な妥当性をここでは確認せず、実際のコンパイルを下流に委ねます。

## 有効になる条件

- 対象は SYCL ビルド入口だけです。CUDA/HIP の実行時設定、CLI 引数、モデル状態で `AOT` を有効化する経路はありません。
- CMake は `STRATA_SYCL_AOT` が空でないとき `spir64_gen` target を使い、`-device <値> -options -cl-fp32-correctly-rounded-divide-sqrt` を device compiler 向けの link option に設定します。空の場合は通常の `-fsycl` を使い、JIT build 用の `spir64` backend option を設定します。
- CMake の値が `bmg` / `lnl` で始まる場合は `STRATA_XMX_SG16=1`、`pvc` で始まる場合は `STRATA_NO_DG2_XMX=1` を定義します。また `STRATA_SYCL_I8_ESIMD=AUTO` かつ AOT 値が非空で `bmg` / `lnl` 以外なら fused int8 ESIMD kernels を stub にします。これは同じビルドの別設定との相互作用です。
- `sycl/tools/build.sh` は `AOT` が `bmg` / `lnl` で始まり、`I8_ESIMD` が `OFF` でなく、`ALLOW_BAD_OCLOC` が `1` でない場合に `ocloc --version` を調べます。既知の失敗版 `26.22.38646`（および同じ prefix の suffix 付き版）なら説明を stderr に出して終了コード 2 にします。version を取得できない場合、このガードによる停止はありません。

## 実行時の詳細

`sycl/tools/build.sh` は、`build.ninja` がまだない場合にだけ `AOT` を CMake configure に渡します。既存 build directory ではこのスクリプトのコメントどおり CMake cache が維持されるため、後から `AOT` を変更しても AOT target の切替には反映されません（ただし既知 `ocloc` 版の事前チェックは呼び出しごとに評価されます）。値が空なら新規 configure は空の `STRATA_SYCL_AOT` を設定します。

`packaging/build_sycl_linux.sh` は毎回 CMake を呼び、`AOT` が非空なら `-DSTRATA_SYCL_AOT=<値>` を渡します。空ならその引数を省略するため、既存 build directory の `STRATA_SYCL_AOT` cache を空に戻しません。空の値が JIT を選ぶのは、既存 cache に以前の AOT 値がない場合です。パッケージ処理では非空値をカンマで分割して `--arch` に渡し、`BUILD.json` に `AOT <値>`、空なら `JIT from SPIR-V` と記録します。

観測できる出力・失敗は次のとおりです。

- `sycl/tools/build.sh` の既知版ガードは、該当条件で IGC/`ocloc` の既知クラッシュ説明と回避方法を stderr に出して `exit 2` します。
- `packaging/build_sycl_linux.sh` は無効形式や `ocloc` 不在を stderr に出して `exit 2` します。
- 通常ビルドでは `sycl/tools/build.sh` が `BUILD EXIT <status>` と `errors: <件数>` を出します。AOT 値自体による実際のコンパイル成否は `cmake` / device compiler の結果に依存し、ここでは未検証です。

## 根拠

- `sycl/tools/build.sh:25-35,38-47`: AOT prefix と他変数を使う既知 `ocloc` ガード、configure 時の受け渡し、build status。
- `packaging/build_sycl_linux.sh:19-36,44-46,48-54,65-69`: 値の case 検証、`ocloc` 必須条件、CMake への受け渡し、ビルド識別情報と package architecture の設定。
- `sycl/CMakeLists.txt:31,47-79,86-100`: `STRATA_SYCL_AOT` による target 選択、device 指定、XMX macro および JIT 用 option。
- `docs/envvars/000_envvers.md:59` には候補 `AOT` がある。全参照を検索した結果、環境値を扱う本番箇所は上記2つのビルドスクリプトであり、他のソース・文書にある AOT は説明上の用語やテスト参照だった。
