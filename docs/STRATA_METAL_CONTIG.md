# `STRATA_METAL_CONTIG`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal の expert streaming が、モデルファイルの隣にある連結 expert ファイル `<GGUF path>.experts` を使うかどうかを制御します。連結ファイルが使えると、expert ごとの gate/up/down のデータを1つの読み込み元から取得します。この変数は streaming 自体を有効化するものではなく、streaming 中の読み込み元の選択だけに関係します。

## 値と判定

`metal/src/engine/stream.cpp` の `env_int("STRATA_METAL_CONTIG", 1)` が値を読みます。共通 helper は、未設定または空文字なら既定値を返し、それ以外は `std::atoi` の結果を返します。したがって文字列全体の数値検証はせず、`atoi` が先頭から変換できる整数を使います（例: `2x` は 2、`x2` は 0）。

| 値 | 連結ファイルを探すか |
|---|---|
| 未設定、空文字 | 探す（既定値 1） |
| `atoi` の結果が 0 | 探さない（例: `0`, `false`, `x2`） |
| `atoi` の結果が 0 以外 | 探す（例: `1`, `-1`, `2x`） |

## 有効になる条件

- Metal engine が選ばれ、モデル geometry が Qwen3.8-Flash-Next 用の条件（48 layers、512 experts/layer など）に合う必要があります。
- `STRATA_METAL_STREAM` とメモリ判定により `ExpertStream::wanted()` が true になり、`Window::init()` が `ExpertStream::open()` を呼ぶ場合にのみ、この設定が評価されます。モデルが resident 経路なら連結ファイルの探索は行われません。
- `.experts` が存在しても、ヘッダーの magic/version、layer/expert 数、元 GGUF のサイズ、各 layer の expert サイズ、先頭・末尾 expert の内容が検証に通らなければ利用されません。その場合は `.experts` を閉じて元の GGUF から読みます。

## 実行時の詳細

値は `ExpertStream::open()` の実行時に毎回評価され、結果は `cfd_` に保持されます。プロセス起動後に環境値を変更する機構や、子プロセスへの転送はこの実装にはありません。

設定値が 0 以外なら `<GGUF path>.experts` を読み取り専用で開き、ヘッダーとサイズ情報を照合します。さらに layer 0 の先頭 expert と layer 47 の末尾 expert について、gate/up/down の各 slice を元 GGUF と比較します。検証に成功すると `.experts` を読み込み元に採用し、stderr に `strata metal stream: experts read from <path> (one request per expert)` を出します。sidecar を開けない場合はログを出さずに GGUF を使います。開いた sidecar の形式やサイズが合わない、または spot check が異なる場合は採用せず、sidecar を閉じて `strata metal stream: <path> is not this GGUF's (sizes or bytes differ): the GGUF is read` と出します。

`cfd_` が有効な場合、各 expert の gate/up/down を連結した領域から読み、`STRATA_METAL_READ_SPLIT` に基づく分割数だけ I/O job を作ります。無効または検証失敗時は GGUF の3 slice を個別に読み、job 数はその3倍です。どちらの読み込み元でも失敗すると expert/layer を stderr に出して終了コード 6 で終了します。

## 文書との照合

`docs/MAC.md` は `STRATA_METAL_CONTIG=0` の効果を「Streaming: read the model file even when the experts' copy is there」と説明しています。実装上は、0 が sidecar の探索自体を止めること、非ゼロでも sidecar の検証に失敗すれば GGUF に戻ることが確認できます。ここでいう experts copy は、実装が探す `<GGUF path>.experts` を指します。

## 根拠

- `metal/src/engine/stream.cpp:27-30`: 未設定・空文字の既定処理と `atoi`。
- `metal/src/engine/stream.cpp:60-76`: stream 初期化と連結ファイル探索の条件。
- `metal/src/engine/stream.cpp:77-120`: sidecar 検証、採用・fallback とログ。
- `metal/src/engine/stream.cpp:272-302,332-343`: 連結ファイルと GGUF の読み込み、I/O job 数。
- `metal/src/engine/window.cpp:409-435`: geometry 条件と stream / resident の選択。
- `docs/MAC.md:183-196`: 利用者向け説明。
