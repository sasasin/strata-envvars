# `AOT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソースの `sycl/tools/build.sh` と SYCL 用 CMake・実装、および関連文書。外部ライブラリや GPU ドライバーが読む環境変数の動作は対象外。

## 役割

`AOT` は `sycl/tools/build.sh` が初回の CMake configure 時に読み、CMake キャッシュ変数 `STRATA_SYCL_AOT` に渡すビルド時の指定です。SYCL エンジンの GPU コードを SPIR-V から実行時に JIT する構成にするか、指定デバイス向けの ahead-of-time (AOT) コードを含む構成にするかを切り替えます。Strata の通常の実行時コードが `AOT` を読む箇所は確認できません。

## 値と判定

| `AOT` の状態・値 | Strata のビルド設定 |
|---|---|
| 未設定または空文字 | シェルの `${AOT:-}` は空文字になる。`STRATA_SYCL_AOT` も空で、CMake は JIT 用の `-fsycl` 構成を選ぶ。 |
| `bmg...` または `lnl...` で始まる非空文字列 | CMake の大文字小文字を区別する正規表現 `^(bmg|lnl)` に一致し、`STRATA_XMX_SG16=1` を compile definition に追加する。さらに AOT 用の `spir64_gen` flags と、文字列全体を含む `-device <値>` backend option を設定する。 |
| `pvc...` で始まる非空文字列 | `^(pvc)` に一致し、`STRATA_NO_DG2_XMX=1` を追加する。AOT 用の flags も設定する。 |
| 上記以外の値 | CMake の `if(STRATA_SYCL_AOT)` が真になる値なら AOT 用 flags を設定するが、上記の compile definition は追加しない。CMake が偽として扱う値（空、`0`、`OFF`、`NO`、`FALSE`、`N`、`IGNORE`、`*-NOTFOUND` など）は JIT 側の分岐に入る。 |

スクリプトは空でない値を引用符付きで CMake にそのまま渡し、Strata 側でデバイス名の許容リストや大文字小文字の正規化は行いません。したがって、たとえば `BMG-g31` は `bmg` 分岐に一致しませんが、CMake で真の値なので AOT 用 flags の分岐には入ります。実際に利用できるデバイス名かどうかはこの Strata コードでは検証しません。

## 有効になる条件

- この変数を読むのは `sycl/tools/build.sh` を使って SYCL エンジンを構成するときです。CUDA/HIP の実行時設定には関与しません。
- `build.sh` は `$BUILD_DIR/build.ninja` が存在しない場合だけ CMake configure を実行します。既定では `BUILD_DIR` は `$REPO/build-sycl`、`REPO` は未設定なら `git rev-parse --show-toplevel` の結果です。既存 build directory では、環境変数を変えて再実行してもこのスクリプトは再 configure せず、既存 CMake cache の値を使います。設定を切り替えるには新しい build directory を使うか、その build directory で CMake configure をやり直す必要があります。
- `bmg` / `lnl` / `pvc` の接頭辞分岐は、AOT を選んだ値がその接頭辞で始まる場合の compile definition の選択です。その他の真値も AOT flags の分岐自体には入ります。

## 実行時の詳細

CMake は空の `STRATA_SYCL_AOT` では `-fsycl` を設定し、空でない真値では `-fsycl-targets=spir64_gen` と `-device <STRATA_SYCL_AOT> -options -cl-fp32-correctly-rounded-divide-sqrt` を link option に設定します。JIT 側では Strata の CMake が `-Xsycl-target-backend=spir64` に正しい divide/sqrt rounding option を付け、既定 ON の `STRATA_SYCL_JIT_STATELESS` が真なら 4 GiB 超 allocation 用 option も加えます。AOT 側では同じ rounding option を AOT backend option に含めます。

デバイス接頭辞による build macro は、SYCL の grouped XMX 実装で sub-group 幅と利用可能な kernel 形状を変えます。`bmg` / `lnl` は sub-group 16 の Xe2 形状を選び、`pvc` は sub-group 8 の kernel をビルド対象外にします。後者の kernel を呼び出す経路に入ると、実装は stderr に `grouped XMX: the 8x8x16 / sub-group 8 kernel is not built for this device (STRATA_NO_DG2_XMX)` を出して終了します。関連する `STRATA_PF_XMX` 経路では、対応しないビルド形状の場合に stderr に無視理由を出して mode を 0 に戻す分岐もあります。

この値はビルド時に CMake cache と compile/link 設定に反映されるため、エンジン起動後の環境変更では再評価されません。`docs/INTEL.md` は Arc B-series の例として `AOT=bmg-g31`、Arc A-series の例として `AOT` を指定しない JIT build を案内しています。また同文書は B-series で AOT device code を使うこと、A-series では JIT 構成を使うことを説明しており、CMake の分岐と整合します。

## 根拠

- `sycl/tools/build.sh:5-9` — `REPO` / `BUILD_DIR` の既定値、`build.ninja` がない場合だけの configure、`${AOT:-}` の CMake cache への受け渡し。
- `sycl/CMakeLists.txt:31-52` — `STRATA_SYCL_AOT` の cache 定義、接頭辞による compile definition、AOT / JIT の flags。
- `sycl/CMakeLists.txt:53-71` — JIT/AOT それぞれの divide/sqrt rounding option と JIT stateless option。
- `sycl/src/kernels/cuda/iq_kernels.dp.cpp:5243-5249,5268-5269,5355-5359,5362-5368` — grouped XMX kernel の sub-group 幅、`STRATA_NO_DG2_XMX` による除外と呼出時の終了。
- `sycl/src/prefill/xmx_moe.dp.cpp:120-124,128-134,148-168` — grouped XMX の build shape と、`STRATA_PF_XMX` 要求時に不一致を無視する分岐。
- `docs/INTEL.md:96-106,108-110,675-676,691` — Arc B-series の `AOT=bmg-g31` 例、Arc A-series の `AOT` なしの例、文書上の AOT/JIT の使い分け。
