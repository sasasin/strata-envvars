# `STRATA_METAL_ENGINE_KERNELS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の engine が実行時にコンパイルする専用 Metal ソース（`ple.metal`、`mtp.metal`、`mtp_chain.metal`）の格納ディレクトリを指定します。通常の Metal kernel 群を指定する `STRATA_METAL_KERNELS` とは別のパスです。

この変数は `strata_metal::resource()` が参照し、PLE kernel の Window 初期化時と MTP kernel のロード時に使われます。`mtp_chain.metal` は、MTP 語彙型が対応リストにあり、かつ `STRATA_METAL_MTP_CHAIN` が文字列 `0` でない場合だけロードされます。

## 値と判定

値を数値や真偽値として parse しません。`std::getenv()` が null でなければ、その文字列をディレクトリパスとしてそのまま返します。したがって、空文字も設定済みとして扱われます。大文字小文字、空白、末尾の区切り文字の正規化はありません。

| 状態 | 選ばれる engine kernel の基準ディレクトリ |
|---|---|
| 未設定 | 実行ファイル隣の `metal/engine-msl` が存在すればそこ。なければビルド時に埋め込まれた `metal/src/engine/msl` の絶対パス |
| 空文字 | 空文字をそのまま返す。呼び出し側が `/ple.metal` 等を組み立てるため、ルート直下の絶対パスになる |
| その他の設定値 | 値をそのまま基準ディレクトリとして使い、呼び出し側が `/ple.metal`、`/mtp.metal`、`/mtp_chain.metal` を連結する |

環境変数で指定したパスの存在確認や、既定パスへの fallback はありません。相対パスの場合、呼び出し側でできるファイル名は絶対パスでないため、Metal compiler の `kernel_dir`（既定では通常の `metal/kernels` ディレクトリ）にさらに連結されます。よって相対値は engine kernel の基準ディレクトリとして単独では解決されません。

## 有効になる条件

- Metal backend の Window を初期化する経路で `ple.metal` を読み込みます。
- MTP をロードする経路で `mtp.metal` を読み込みます。
- MTP chain kernel は、token embedding の型が `mtp_load()` 内の `ok_types` に含まれ、かつ `STRATA_METAL_MTP_CHAIN` が未設定または文字列全体が `"0"` 以外の場合にコンパイルされます。
- 環境変数が未設定の場合も、実行ファイル隣の package resource が見つからない場合も、ビルド時の既定パスに進みます。

この環境変数自体に CLI、モデル条件、OS/backend の値判定はありません。参照箇所は Metal engine のコードで、他 backend には適用されません。

## 実行時の詳細

`resource()` は呼び出されるたびに環境を読み、値が設定されていればただちに返します。static cache はありません。Window 初期化時に `ple.metal` のパスを解決し、MTP をロードするときに `mtp.metal`、必要な場合に `mtp_chain.metal` のパスをそれぞれ解決します。そのコンパイル後に環境を変更しても、すでに読み込まれたライブラリは変わりません。後続の読み込みで再び解決されます。

指定パスのファイルを開けない場合は `mtl::read_file()` が stderr に `mtl: cannot read <path>` を出して終了コード 2 で終了します。読み込んだ Metal ソースのコンパイルに失敗した場合は `mtl: compile failed (...)` と compiler の説明を stderr に出し、終了コード 3 で終了します。

## 根拠

- `metal/src/resource_path.h:13-14,43-54` — 優先順位、設定値の無条件採用、既定時の隣接 resource とビルド時パスへの fallback。
- `metal/CMakeLists.txt:115-123` — `STRATA_METAL_ENGINE_KERNELS_DEFAULT` に `metal/src/engine/msl` を埋め込み、Metal engine kernel library に定義。
- `metal/src/engine/window.cpp:491-497,1174-1188` — Window 初期化時の `ple.metal` コンパイルと PLE pipeline の使用。
- `metal/src/engine/window.cpp:1616-1633,1705-1713` — MTP load 時の `mtp.metal` と条件付き `mtp_chain.metal` コンパイル。型条件と `STRATA_METAL_MTP_CHAIN` 判定。
- `metal/src/mtl_rt.mm:20-28,75-105` — ファイル読込失敗時の診断・終了、および Metal compiler の失敗処理。
- `docs/DETAILS.md` にはこの変数の個別説明や測定値は見つかりませんでした。
