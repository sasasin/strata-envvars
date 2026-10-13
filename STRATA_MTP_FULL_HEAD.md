# `STRATA_MTP_FULL_HEAD`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

MTP ドラフターの候補語彙を、通常の `draft_vocab.bin` による部分集合から、メインモデルの出力ヘッド全語彙へ切り替える診断用フックです。ソースコメントは、部分集合による受理率への影響を全語彙ヘッドと比較する用途を示しています。通常設定では部分集合の行をメインヘッドから gather して専用の draft head として使います。この変数が有効なら gather を行わず、MTP のドラフト計算でメインヘッド全体を直接使います。

## 値と判定

`getenv()` の値が存在し、先頭文字が `1` の場合だけ有効です。文字列全体の比較や数値変換はしません。

| 環境変数の値 | 判定 |
|---|---|
| 未設定 | 無効。通常の部分集合を読み込む |
| 空文字 | 無効。通常の部分集合を読み込む |
| `1`、`10`、`1anything` | 有効 |
| `true`、`01`、` 1`、`0` など | 無効 |

判定結果は `full_head_env()` 内の関数ローカル `static const bool` にキャッシュされます。最初にこの関数が呼ばれた後にプロセス環境を変更しても反映されません。読み取り箇所は CUDA/HIP 用 `src/core/mtp.cpp` と SYCL 用 `sycl/src/core/mtp.cpp` の各1箇所で、判定内容は同じです。

## 有効になる条件

- `--mtp` で MTP ドラフト層を使い、`--spec T`（`T >= 2`）の実行経路に入る必要があります。`--mtp` は省略可能で、`--spec` が2未満なら generate は `--mtp` を無視します。
- MTP の `bind()` がメインの native output head を必要とします。ヘッドがない、または未ロードなら bind はエラーになります。
- 対象は Strata の MTP 実装内の分岐です。CUDA/HIP 系と SYCL 系で同じ分岐があります。
- `--mtp-draft-vocab FILE` で別の部分集合ファイルを指定していても、この変数が有効な場合は部分集合の読み込み分岐自体を通らず、ファイルを使いません。
- `--expert-cache auto` の VRAM 見積もりにも同じ判定が使われ、部分集合 head 用の追加容量を予約しません。`--expert-cache` を明示して自動見積もりを通らない場合でも、bind 時の分岐は適用されます。

## 実行時の詳細

通常は `bind()` が `vocab_file()`（既定は `<mtp>/rt/draft_vocab.bin`。CLI で別ファイルを指定可能）を読み、4バイト整数列として妥当なサイズなら token ID 一覧を保持し、その語彙数分の head 行を `gather_rows()` でメイン native head からコピーします。ファイルがない、またはサイズが不正なら、この箇所では部分集合 head を作らず、全語彙 head の経路になります。

`STRATA_MTP_FULL_HEAD` が有効なら `bind()` の部分集合ロード条件が偽になり、`dhead_` は null のままです。ドラフト計算は `dhead_` が null の場合にメイン native head の重みと `n_vocab_` を使い、全語彙の logits から候補を選びます。部分集合 ID への変換も行いません。`bind_bytes()` も部分集合ファイルの容量を加算しません。ドラフト logits 用バッファの見積もりは引き続き必要です。

batch 用など共有ドラフターを bind する場合、共有先は共有元の `dhead_`、語彙数、token map を引き継ぎます。したがって、共有構成では環境変数の判定が共有元で選ばれた head に反映されます。

この変数自体の専用ログ出力は見当たりません。MTP 層が draft 候補を提案し、その候補を検証 window が確認する構成です。全語彙にすると提案候補や計算量、head のメモリ要件が変わり得ます。ソースおよび `docs/DETAILS.md` から、この環境変数を使った性能値や受理率の実測値は確認できません。ドキュメントは通常時の部分集合を説明していますが、この診断変数は記載していません。

## 根拠

- `src/core/mtp.cpp:456-463`, `sycl/src/core/mtp.cpp:549-556`: 環境変数の読み取り、先頭文字判定、診断用途のコメント。
- `src/core/mtp.cpp:490-499`, `sycl/src/core/mtp.cpp:591-600`: `bind_bytes()` で部分集合 head の容量を見積もる条件。
- `src/core/mtp.cpp:610-665`, `sycl/src/core/mtp.cpp:730-780`: native head の必須条件、部分集合ファイルの読み込み、行の gather。
- `src/core/mtp.cpp:977-1003`, `sycl/src/core/mtp.cpp:1125-1146`: `dhead_` の有無に応じて部分集合または全語彙の head を使い、必要時だけ ID を map する処理。
- `src/program/generate.cpp:4436-4453`: `--mtp` と `--spec` の適用条件、MTP 初期化。
- `src/program/generate.cpp:4830-4846`, `sycl/src/program/generate.cpp:4297-4312`: 自動 expert-cache 容量計算での MTP bind 用 VRAM 予約。
- `include/strata/core/mtp.hpp:65-67,78-83,207`: `--mtp-draft-vocab` の設定と既定ファイル名、bind 用容量 API。
- `docs/DETAILS.md:128-144`: 通常の MTP 部分語彙とその説明。ここには `STRATA_MTP_FULL_HEAD` の説明や同変数を用いた測定値はありません。
