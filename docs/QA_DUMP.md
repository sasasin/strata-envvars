# `QA_DUMP`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`QA_DUMP` は、QSA prompt-attention parity 診断プログラムに既存の QSA 選択ダンプを渡します。プログラムは指定レイヤーの選択セルを読み、隣り合う複数 query 間でセル集合がどれだけ重なるかを標準出力に表示します。Strata の通常の推論・prefill の挙動は変えません。

この読み取り処理は CUDA 版 `src/kernels/qsa_prompt_attn_parity.cpp` と SYCL 版 `sycl/src/kernels/qsa_prompt_attn_parity.cpp` にあります。CUDA の parity 実行ファイルはテスト有効時、または `STRATA_PARITY_PROMPT_ATTN` 有効時にビルドされます。SYCL 版はテストビルドで作成されます。どちらも診断用の実行ファイルで、通常の `strata` 実行ファイルの設定ではありません。

## 値と判定

| `QA_DUMP` の状態 | 動作 |
|---|---|
| 未設定 | ダンプの読み込みと重なり表示を行わない |
| 設定あり | 値全体をファイルパスとして `rb`（バイナリ読み込み）で開く |
| 空文字 | 設定ありとして扱い、空のパスを開こうとする。失敗時は stderr に `QA_DUMP: cannot open` を出して終了コード 2 で終了する |

`QA_DUMP` 自体は真偽値や数値として parse されません。設定されているかどうかだけを判定します。設定値を最初の呼び出しでキャッシュする処理はなく、parity プログラム内の各 `run()` 呼び出しで確認します。

レイヤー選択には関連変数 `QA_LAYER` を使います。`QA_DUMP` が設定されているとき、`QA_LAYER` 未設定ならレイヤー 3 を選びます。設定時は `atoi` で整数化するため、空文字や数値に変換できない文字列は 0 になり、数値の後ろに続く文字列は変換結果に影響しません。

## 有効になる条件

- `qsa_prompt_attn_parity` を実行し、その実行ファイルが利用できること。
- ダンプファイルに、指定レイヤー・実行時の `nq`・`ctx`・QSA selection width (`cap`) に一致するレコードがあること。`ctx` はレコードの `pos0 + T`、`T` は `nq` と一致する必要があります。
- 入力ダンプはヘッダー `{layer, pos0, T, cap}` と、それに続く `T * cap` 個の int32 セル ID からなる基本形式であること。CUDA 側の `STRATA_QSA_DUMP_STEPS` が追加する steps 部分は、この reader のレコード走査形式に含まれません。

Strata の prefill 側では、別変数 `STRATA_QSA_DUMP` にパスを設定すると QSA レイヤーの選択セルを追記形式で出力します。CUDA 実装ではさらに `STRATA_QSA_DUMP_LAYER` によるレイヤー絞り込みと `STRATA_QSA_DUMP_STEPS` による steps 追加があります。これらは `QA_DUMP` とは別の環境変数で、`QA_DUMP` はその出力ファイルを parity プログラムへ渡す側です。

## 実行時の詳細

各 parity `run()` は引数の `ctx` と `nq`、カーネル形状から算出した `cap` を使って、ダンプを先頭から走査します。ヘッダーとセル配列を順に読み、条件に合うレコードのデータ位置を記録します。同じ条件のレコードが複数ある場合は最後に見つかったものを使います。該当レコードがなければ stderr に `QA_DUMP: no record for layer ...` を出し、終了コード 2 で終了します。セルデータを最後まで読み取れない場合も終了コード 2 です。

読み込んだセル ID をその run の合成 query selection に上書きし、2・4・8・16 query ごとに、16 group 分間隔で取り出した隣接グループのセル集合の和集合を計算します。標準出力には `QA_DUMP overlap: ...` として、単一 query のセル数に対する倍率と、グループ内の query 数に対する割合を表示します。これは診断値で、モデル推論の出力や QSA 選択そのものを変更するものではありません。

parity プログラムの既定引数は `ctx=32768`、`nq=2048`、`reps=5` です。また同プログラムは複数の `ctx` / `nq` 組を順に `run()` するため、指定ファイルに現在処理中の組に合うレコードがなければ、その `run()` でエラー終了します。

## 根拠

- `src/kernels/qsa_prompt_attn_parity.cpp:151-182` — `QA_DUMP` と `QA_LAYER` の判定、ファイル走査、セル ID の置換、重なり率表示。
- `sycl/src/kernels/qsa_prompt_attn_parity.cpp:176-207` — SYCL 版の同じ処理。
- `src/kernels/qsa_prompt_attn_parity.cpp:346-377` — 引数の既定値と複数条件での `run()` 呼び出し。
- `CMakeLists.txt:420-426` — CUDA parity 実行ファイルのビルド条件。
- `sycl/CMakeLists.txt:351-355` — SYCL parity 実行ファイルがテストブロック内で作成されること。
- `src/prefill/prefill.cpp:3231-3255` — CUDA prefill の `STRATA_QSA_DUMP` レコード形式と追加 steps の出力。
- `sycl/src/prefill/prefill.cpp:3129-3152` — SYCL prefill の `STRATA_QSA_DUMP` 出力。
