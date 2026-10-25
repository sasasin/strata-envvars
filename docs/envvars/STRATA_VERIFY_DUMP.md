# `STRATA_VERIFY_DUMP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

SYCL 版 `strata generate` の expert cache 検証で、GGUF と GPU cache slot の内容が食い違ったとき、最初に見つかった不一致 slot の両方のバイト列をファイルに保存します。診断用です。cache の読み書きや生成結果を変更する値ではありません。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_VERIFY_DUMP") != nullptr` だけで有効になります。未設定なら dump せず、空文字を含め何らかの値が設定されていれば dump を試みます。設定値を出力先ディレクトリ文字列として使い、`<値>/slot<slot番号>.got` と `<値>/slot<slot番号>.want` を作ります。たとえば `STRATA_VERIFY_DUMP=/tmp/check` なら `/tmp/check/slot0.got` と `/tmp/check/slot0.want` です。

ディレクトリの作成やパス検証は行いません。`fopen` が失敗してもエラーを記録せず、書き込み失敗も確認しません。空文字の場合は `/slot<slot番号>...` というパスを試します。

## 有効になる条件

この読み取りは SYCL 版 `sycl/src/program/generate.cpp` にのみあります。さらに、expert cache が有効で、profile と GGUF source があり、pipelined profile fill が選ばれた経路で `STRATA_VERIFY_ALL_SLOTS` も設定されている必要があります。pipelined fill は `srcp == &gguf_src && !per_layer && STRATA_FILL_SERIAL` が未設定の場合です。`STRATA_VERIFY_ALL_SLOTS` の判定も値の内容ではなく設定有無です。

検証は fill 完了時と session setup 完了時に実行されます。各検証実行中に不一致が初めて見つかったときだけ dump を試みます。GGUF の読み込み失敗は不一致数を増やして次の slot へ進むため、その前に読み込み失敗があると後続の不一致は `bad == 1` にならず dump されません。2回の検証で不一致が続くと、同じ slot 名のファイルが後の検証で上書きされ得ます。

## 実行時の詳細

検証 callback は各 fill 済み slot について GGUF の expert blob を読み、device slot を host buffer にコピーして `memcmp` します。不一致があれば異なるバイト数、最初と最後の不一致位置などを stderr に出します。`STRATA_VERIFY_DUMP` が設定され、かつその callback 内の不一致数が初めて 1 になった時点で、device から読み戻した内容を `.got`、GGUF から読んだ期待内容を `.want` に binary mode で書きます。ファイル出力に成功したかどうかのログはありません。

## 根拠

- `sycl/src/program/generate.cpp:4721-4736`: verifier callback の宣言と、profile fill および pipelined 経路の条件。
- `sycl/src/program/generate.cpp:4791-4835`: `STRATA_VERIFY_ALL_SLOTS` の設定有無判定、各 slot の readback/比較、`STRATA_VERIFY_DUMP` の設定有無・ファイル名・書き込み処理。
- `sycl/src/program/generate.cpp:5423-5425`: session setup 後の2回目の全 slot 検証。
- `docs/INTEL.md:762-767`: Intel SYCL 環境の調査記録で、`STRATA_VERIFY_ALL_SLOTS` と `STRATA_VERIFY_DUMP` が cache 内容の照合に使われた旨を記載。動作の詳細は上記ソースに基づく。
