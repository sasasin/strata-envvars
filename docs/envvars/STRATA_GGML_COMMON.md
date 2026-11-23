# `STRATA_GGML_COMMON`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

macOS Metal runtime が Metal shader source に追加する共通量子化ヘッダーのパスを指定する。`mtl::Context` の構築時にパスを一度決定し、通常の shader compile ではそのファイル内容を source に埋め込む。環境変数はファイルの存在・内容を検証せず、空でないパスを選んだ場合に compile 時の読み込み対象となる。Metal 以外の backend の処理には参照がない。`engine/metal/src/mtl_rt.mm:139-150,183-192`、`engine/metal/src/resource_path.h:56-70`。

## 値と判定

`resource2` は引数名 `STRATA_GGML_COMMON` を `std::getenv` に渡し、返り値が null かどうかだけを見る。値の parse、trim、空白除去、大小文字変換はしない。未設定なら実行ファイル横のパッケージ内ファイル、次にビルド時に埋め込んだ既定パスを選ぶ。設定されている場合は値をそのままパスとして返すため、空文字も既定値への fallback ではなく空パスになる。`engine/metal/src/resource_path.h:56-70`。

| build / 状態 | unset | 有効になる値（例） | 無効・特別な値（例） |
|---|---|---|---|
| 通常の Metal engine build | 実行ファイル横の `metal/strata-quant-common.h`、次に `metal/ggml-common.h` が存在すればそちら、どちらもなければビルド時の `include/strata/quant/strata-quant-common.h` | 読み込み可能なヘッダーファイルのパス。例: `/opt/strata/quant.h` | 空文字は共通ヘッダーの取り込みを無効にする。存在しないパスや読めないファイルは compile 時にエラー終了する。 |
| Inkling-2 / HY4 の同梱 Metal runtime build | それらの build は `STRATA_GGML_COMMON_DEFAULT` を空文字で定義するため、実行ファイル横の候補がなければ空パス | 読み込み可能なヘッダーファイルのパス | unset は空パスとなり、共通ヘッダーを使わない。設定値が空でも同じく無効。 |

任意の非空文字列は path として採用されるため、`1`、`true`、`0`、`0anything` も boolean 値ではなくファイル名（相対パスならそのままの相対パス）として扱われる。値自体の境界・数値形式の検査はない。空白だけの値も trim されず、そのまま path になる。`engine/metal/src/resource_path.h:58-69`。

## 有効になる条件

- Metal runtime を含む macOS の実行経路で `mtl::Context` が作られること。通常の Metal engine ではモデルを開く処理から Context を生成する（`engine/metal/src/engine/window.cpp:736-738`）。
- 共通ヘッダーの内容が実際に追加されるには、選ばれたパスが空でなく、かつ当該 compile の prelude に `NO_GGML_COMMON` という部分文字列が含まれないこと。空パスまたはこの marker がある場合はヘッダーを読まない（`engine/metal/src/mtl_rt.mm:183-189`）。
- 通常の Metal engine build は既定パスとして `include/strata/quant/strata-quant-common.h` を埋め込む。Inkling-2 / HY4 では既定値が空だが、環境変数が設定されれば `resource2` がその値を優先する（`engine/metal/CMakeLists.txt:31-40,168-174`; `engine/src/inkling2/metal/CMakeLists.txt:27-45`; `engine/src/hy4flash/metal/build_mac.sh:11-13`）。

## 実行時の詳細

値を読むのは `mtl::Context` の constructor 内の `resource2` 呼び出し一回で、選択した文字列は `ggml_common_path` に保存される。compile ごとには環境を読み直さないため、同じ Context の構築後にプロセス環境を変えても、その Context のパスには反映されない。新しい Context は構築時点の環境を参照する。`engine/metal/src/mtl_rt.mm:139-150`; `engine/metal/src/mtl_rt.h:138-145`。

パス選択順は、設定された環境値、実行ファイル横の新名称 `metal/strata-quant-common.h`、旧名称 `metal/ggml-common.h`、ビルド時既定値。横の候補は `stat` で存在を確認するが、環境値およびコンパイル時既定値はこの時点で存在確認しない（`engine/metal/src/resource_path.h:38-70`）。compile 時にパスが非空で `NO_GGML_COMMON` がなければ `read_file` で内容を読み、Metal source に追加する。ファイルを開けない場合は stderr に `mtl: cannot read <path>` を出し、プロセスを status 2 で終了する。これは `compile_try` から呼ばれても同じで、fallback 用の戻り値にはならない（`engine/metal/src/mtl_rt.mm:26-34,183-192`）。

Metal source のコンパイル自体が失敗した場合は `compile_try` が `-1` と compiler message を返す。通常の `compile` 経路は `mtl: compile failed (...)` を stderr に出して status 3 で終了する。この失敗経路は環境変数の値を検証するものではなく、選ばれたヘッダーを含む source の compile 結果である（`engine/metal/src/mtl_rt.mm:170-179,183-189`）。

## ログと測定値

環境変数を設定したこと自体を知らせるログはない。選択パスを読み込めない場合の stderr と終了 status 2、および後続の Metal compile 失敗時の stderr と status 3 は上記のとおり（`engine/metal/src/mtl_rt.mm:26-30,170-177`）。この変数に関する測定値は確認できなかった。

## 根拠

- `engine/metal/src/resource_path.h:38-70` — 実行ファイル横の候補・既定パスとの優先順位、`getenv` の設定有無判定。
- `engine/metal/src/mtl_rt.mm:26-34,139-150,170-192` — Context 構築時の読み取り、ヘッダー埋め込み、ファイル読み込み失敗と compile の観測経路。
- `engine/metal/src/mtl_rt.h:138-145` — Context に保存する `ggml_common_path`。
- `engine/metal/CMakeLists.txt:31-40,168-174`, `engine/src/inkling2/metal/CMakeLists.txt:27-45`, `engine/src/hy4flash/metal/build_mac.sh:11-13` — build ごとの既定パス。
- `engine/metal/src/engine/window.cpp:736-738` — 通常の Metal window 初期化時の Context 生成。
