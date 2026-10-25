# STRATA_TOPK_OLD

調査対象: Strata main の HEAD a0116b2782a5b82622358c04a06496485d12b2d6（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

QSA の block top-k 選択で、現行の最適化カーネル群ではなく元の参照カーネルを選びます。CUDA と HIP の本体、および SYCL 移植の実装に読み取り箇所があります。参照カーネルは query ごとに 256 thread のカーネルを起動し、score を読みながら radix 選択を行います。値を設定しない場合は、デバイス・入力形状などに応じた通常の dispatch（cluster / register / wide 等）が使われます。

この変数が影響するのは qsa_block_topk() が呼ばれる経路です。通常の layer 実装は g_fast_select が有効なら block score と block top-k を呼び、無効なら従来の index と top-k の経路に進みます。--no-fast-select は g_fast_select を無効にするため、その実行では本変数の参照カーネル選択に入りません。

## 値と判定

値の内容は parse されず、std::getenv("STRATA_TOPK_OLD") != nullptr という設定有無だけで判定されます。

| 環境変数の状態 | 判定 | qsa_block_topk() の選択 |
|---|---|---|
| 未設定 | false | 通常の dispatch。条件が合えば CUDA の cluster、register / wide カーネル等を選ぶ |
| 設定あり（空文字を含む） | true | 参照カーネル qsa_block_topk_ref() に進む |

1、0、false、任意の文字列はすべて同じ「設定あり」です。数値変換、大小文字、前後の空白、範囲チェックはありません。値を設定していても、プロセス内で最初に qsa_block_topk() が呼ばれた時点での結果が static const bool に保存され、その後の環境変更は再評価されません。読み取りは nq <= 0 の早期 return より前に行われます。

## 有効になる条件

- qsa_block_topk() に到達することが必要です。通常の layer 経路では g_fast_select が有効な場合に呼ばれ、--no-fast-select を指定すると別経路を使います。
- CUDA では、参照カーネルへの分岐より先に行われる cluster dispatch も !old を条件に含むため、本変数が設定されている場合は cluster kernel を試しません。その後、参照カーネルへ進みます。
- HIP では cluster dispatch 部分がコンパイル条件によりありません。値を設定した場合は参照カーネルへ進み、未設定時は HIP 側の入力条件に応じた register kernel / 参照 kernel の dispatch になります。
- SYCL 移植にも同じ設定有無判定と旧カーネルへの分岐があります。
- qsa_block_topk_ref() は nq <= 0 なら何もせず、対応しない geometry または cap では stderr に qsa_block_topk: unsupported geometry or cap を出して終了します。これは環境変数固有のエラーではなく、参照カーネルの入力検査です。

## 実行時の詳細

値が有効な場合、通常の dispatch を行う前に qsa_block_topk_ref(scores, steps, nq, max_blocks, cap, s, ids, stream) を呼び、関数から戻ります。参照カーネルの実装は 256 thread / query で起動します。未設定時は通常の選択規則が続き、CUDA では条件により cluster、wide、register カーネルなどを使い分けます。HIP も独自の reach 条件で register kernel と参照カーネルを選びます。そのため、未設定時でもすべての呼び出しが最適化カーネルになるわけではありません。

実装コメントと qsa_select.hpp は参照版と最適化版が同じ ID を返すものとして記述していますが、この調査では性能測定や parity 実行はしていません。変数判定やカーネル選択に伴う専用ログ出力は見つかりませんでした。

## 根拠

- src/kernels/cuda/qsa_select.cu:1199-1209 — 参照カーネルの入力検査と 256 thread カーネル起動。
- src/kernels/cuda/qsa_select.cu:1295-1344 — 設定有無の static cache、CUDA cluster の抑止、HIP/CUDA 条件分岐、参照カーネルへの dispatch。
- sycl/src/kernels/cuda/qsa_select.dp.cpp:1786-1805,1953-2000 — SYCL 移植の参照カーネルと同じ dispatch。
- include/strata/kernels/qsa_select.hpp:39-55 — qsa_block_topk と参照実装の API 説明。コメントでは参照版について「同じ ids」と記載。
- src/core/layer.cpp:44,491,1126-1132 — fast select の既定値、setter、block top-k と従来経路の分岐。
- src/program/generate.cpp:510,2180,3083 — --no-fast-select の既定値、引数処理、layer 機能への反映。
- src/core/verify.cpp:1367-1384, src/prefill/prefill.cpp:2774,2821 — verify / prefill からの block top-k 呼び出し。
