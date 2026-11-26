# `STRATA_VERIFY_DUMP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL engine のプロファイル済み GPU expert cache 検証で GGUF と slot の内容に不一致が見つかったとき、最初の不一致について比較対象のバイト列をファイルへ書き出す診断用の出力先ディレクトリを指定する。`STRATA_VERIFY_DUMP` 自体は検証を有効にせず、生成 token や cache の配置も制御しない。全 slot 検証を有効にする `STRATA_VERIFY_ALL_SLOTS` が設定されて検証 callback が作られた経路でのみ参照される。実装は `engine/sycl/src/program/generate.cpp` の `generate` 内、SYCL backend 専用である（同ファイル 5255-5271, 5326-5329, 5357-5363）。

## 値と判定

差分が見つかった箇所で `std::getenv("STRATA_VERIFY_DUMP") != nullptr` を判定し、得た文字列を `base = 値 + "/slot" + slot番号` として使う。値の真偽や内容の parse はない。出力名は `<値>/slot<番号>.got` と `<値>/slot<番号>.want` で、`.got` は GPU slot から読み戻したデータ、`.want` は GGUF から読み直したデータである。どちらもその layer の blob byte 数 `nb` を `wb` で書く（5357-5360）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_VERIFY_ALL_SLOTS` による検証 callback 内で不一致を処理するとき | ダンプしない | `STRATA_VERIFY_DUMP=/tmp/verify` は `/tmp/verify/slotN.got` と `.want` を試みる | 有効値・無効値の parse 分類はない。`0`、`1`、`true`、`false` も各文字列をディレクトリ名として使う |
| 空文字 | 該当なし | 設定済みなので有効。基底が空文字となり `/slotN.got` と `/slotN.want` を試みる | 空文字を無効扱いする判定はない |

文字列全体・先頭文字・大文字小文字・空白・数値としての妥当性は検査しない。`0anything` もそのままディレクトリ名として結合される。ディレクトリの作成は行わず、`fopen` が失敗した場合もこの環境変数に関する警告やエラーを出さない。`fwrite` の戻り値も確認しない（5357-5361）。

## 有効になる条件

- SYCL engine の実行経路であること。通常の CUDA/HIP engine ではこの参照箇所はなく、SYCL は独立した実験的 backend として構成される（`engine/CMakeLists.txt:23-32`）。SYCL の CMake は Linux x86_64 向けと記載している（`engine/sycl/CMakeLists.txt:253-258`）。
- プロファイルが空でなく、expert source があり、source が `gguf_src`、cache admission が per-layer でなく、`STRATA_FILL_SERIAL` が未設定であること。これらの条件で pipelined fill に入り、さらに `STRATA_VERIFY_ALL_SLOTS` が設定済み（空文字を含む）で callback が作られる（`engine/sycl/src/program/generate.cpp:5256-5271`, `5325-5329`）。
- callback 内の比較で GGUF blob の読み直しに成功し、slot から読み戻した `nb` バイトと異なること。読み直しに失敗した場合は `bad` を増やしてその fill を飛ばし、ダンプ箇所には進まない（同 `generate.cpp:5333-5338`）。
- callback 呼び出しごとに `bad` が 1 である不一致だけを書き出す。読み直し失敗も先に `bad` を増やすため、先行する失敗があれば不一致が最初でもダンプされない。最初の差分後は以降の不一致をダンプしない。その callback が「after the fill」と「session up」の 2 回実行される場合、それぞれで `bad` は初期化されるため同じファイルを再度開いて上書きし得る（同 `generate.cpp:5331-5338`, `5369`, `6002-6005`）。

## 実行時の詳細

`STRATA_VERIFY_ALL_SLOTS` は fill 中に一度だけ存在判定され、検証 callback の生成を決める。callback は fill 直後に全 slot を GGUF と比較し、作られていれば session 起動後にも再度全 slot を比較する。`STRATA_VERIFY_DUMP` は callback の各不一致処理で `getenv` されるため、値を cache する static はない（`engine/sycl/src/program/generate.cpp:5326-5329`, `5331-5338`, `5357-5361`, `5369`, `6002-6005`）。

ダンプされるのは `bad == 1` となった不一致 slot 一つの `.got` と `.want` で、ファイルは `wb` で開かれるため同名ファイルがあれば切り詰める。出力ディレクトリがない、または書き込みできない場合は出力されないが、処理を止めたり比較結果を変えたりはしない。CLI 引数や他の設定からこの値を上書きする実装は確認できない。`STRATA_VERIFY_FIND` は不一致データの出所調査を別途行う条件であり、このダンプ先の選択には使われない（同 `generate.cpp:5344-5360`）。

## ログと測定値

この変数専用の成功・失敗ログはない。`STRATA_VERIFY_ALL_SLOTS` の検証処理は不一致ごとに `strata generate: STRATA_VERIFY_ALL_SLOTS (%s): fill ... bytes differ ...`、各 callback の最後に `strata generate: STRATA_VERIFY_ALL_SLOTS (%s): ... slots differ ...` を stderr に出す（`engine/sycl/src/program/generate.cpp:5362-5367`）。これらのログはダンプファイルの作成成功を示さない。測定値は該当しない。

## 根拠

- `engine/sycl/src/program/generate.cpp:5255-5271` — 検証対象となる pipelined fill の条件。
- `engine/sycl/src/program/generate.cpp:5325-5369` — 全 slot 検証 callback、比較、最初の差分のファイル出力。
- `engine/sycl/src/program/generate.cpp:6002-6005` — session 起動後の二度目の検証呼び出し。
- `engine/CMakeLists.txt:23-32`、`engine/sycl/CMakeLists.txt:253-258` — backend の分離と SYCL build 対象。
- `docs/INTEL.md:162-165` — `STRATA_VERIFY_ALL_SLOTS` による全 slot 比較の説明。`STRATA_VERIFY_DUMP` 自体の説明はない。
