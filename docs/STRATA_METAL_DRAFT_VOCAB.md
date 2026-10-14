# `STRATA_METAL_DRAFT_VOCAB`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal engine が MTP ドラフト層の語彙部分集合ファイルを選ぶパス指定です。指定したファイルから token ID を読み、MTP draft head をモデルの `output.weight` からその行だけコピーして作ります。`full` を指定するか、読み込んだ有効 ID が0件なら部分集合を使わず全語彙の head を使います。

この読み取りは `Window::mtp_load()` 内にあり、MTP 層をロードする Metal 経路でのみ実行されます。CUDA 側の `--mtp-draft-vocab` とは別の Metal 固有環境変数です。

## 値と判定

値は文字列全体をパスとして扱います。数値変換、trim、大文字小文字変換はありません。唯一の特別値は、大文字小文字を区別する完全一致の `full` です。

| 環境変数 | 選択される語彙ファイル |
|---|---|
| 未設定 | まず MTP GGUF と同じディレクトリーの `rt/draft_vocab.bin`。開けなければ `STRATA_METAL_DATA_DEFAULT/draft_vocab.bin` |
| 空文字を含む設定値 | 空文字自体をパスとして使用。開けなければ full vocabulary にフォールバックし、上記の既定パスは試さない |
| `full` | ファイルを開かず、full vocabulary |
| その他の設定値 | その文字列をファイルパスとして開く。開けない場合は full vocabulary |

選択したファイルは4 byte単位で `int32_t` を読み、`0 <= id < n_vocab_` の値だけを保持します。範囲外の値は捨てられ、重複 ID は除去されません。末尾に4 byte未満のデータがあれば `fread` が完全な要素を返さず、読み込みはそこで終わります。ファイルを開けない場合や、有効 ID が一つもない場合も `dvocab_` は空のままです。

根拠: `metal/src/engine/window.cpp:1552-1565`。

## 有効になる条件

- Metal engine が MTP draft 層をロードするときに適用されます。通常のモデル語彙や target 側の出力 head を差し替える設定ではありません。
- `STRATA_METAL_DRAFT_VOCAB` が設定されていれば、隣接する既定ファイルとリポジトリー内既定ファイルより優先します。値を設定したがファイルが開けない場合も、他の既定ファイルへは fallback しません。
- 未設定時は、MTP GGUF のパスから作る `rt/draft_vocab.bin` を先に確認します。存在確認には `fopen(..., "rb")` を使い、開ければそのパスを採用します。開けなければ `STRATA_METAL_DATA_DEFAULT/draft_vocab.bin` を選びます。
- この処理には OS/backend の追加条件分岐がありませんが、実装箇所は Metal engine です。CUDA/HIP/SYCL 経路がこの変数を読む箇所は HEAD 内の完全一致検索で見つかりませんでした。

## 実行時の詳細

環境変数は `mtp_load()` の呼び出しごとに一度読み取られ、その場でファイルを開きます。MTP draft head をロードした後にプロセス環境を変えても、既に読み込んだ `Window` の語彙選択や head は変わりません。

有効 ID が1件以上ある場合、実装は `output.weight` の該当行を順番どおりに GPU buffer `mhead_` へコピーし、部分 head の tensor shape と byte 数を設定します。draft logits の計算、argmax の候補数、選ばれた部分集合 index から実 token ID への変換にも同じ `dvocab_` を使います。`dvocab_` が空なら full `output.weight` を使います。そのため、明示したパスが不正・空でも MTP 層の語彙選択は full vocabulary に戻ります。

ロード時には stderr に `strata metal: MTP draft layer from ... draft head over all tokens` または `... over <件数> tokens` が出ます。ログに選択ファイルのパス自体は表示されません。

根拠: `metal/src/engine/window.cpp:1566-1578,1618-1621,1841-1843,1881-1889,1943-1949`。

## 文書との照合

`docs/DETAILS.md:128-144` は MTP draft vocabulary の部分集合と setup の `--draft-vocab` 選択を説明しています。同ファイル `:290-292` は CUDA engine の `--mtp-draft-vocab FILE` を記載していますが、Metal の `STRATA_METAL_DRAFT_VOCAB` の優先順位、`full` sentinel、失敗時の full vocabulary fallback は説明していません。ここでは Metal の現在の実装を根拠にしました。性能値は、この環境変数の Metal 固有効果を測定した資料が見つからないため記載していません。

## 根拠

- `metal/src/engine/window.cpp:1489-1490,1552-1578` — MTP load 内の環境変数判定、既定パス選択、語彙 ID 読み込み、部分 head 作成。
- `metal/src/engine/window.cpp:1618-1621` — 読み込んだ語彙件数の起動ログ。
- `metal/src/engine/window.cpp:1841-1843,1881-1889,1943-1953` — full/部分 head の logits、候補選択、token ID 復元。
- `docs/DETAILS.md:128-144,290-292` — 一般的な MTP draft vocabulary と CUDA の CLI 指定に関する説明。
