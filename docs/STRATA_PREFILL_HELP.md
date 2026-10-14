# `STRATA_PREFILL_HELP`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

multi-GPU の layer split で、prompt の各 stage が自分の層を処理している間、次の stage（最後の stage では最初の stage）の GPU に、その層の非 resident expert の一部をストリーミングして MMQ で計算させます。prompt stage は処理を順番に実行するため、その間アイドルになる GPU を使います。expert の行は mapped pinned host memory 経由で返します。この動作は opt-in で、helper GPU 側の MMQ grouping により結果は既定経路と bit-identical ではありません（`include/strata/prefill/prefill.hpp:165-172`, `docs/MULTI_GPU.md:85-97`）。

## 値と判定

値全体の厳密比較ではなく、`std::atoi()` の結果が 0 でないかで判定します。未設定と空文字は無効です。`atoi` は先頭の空白と符号を許し、数値の後ろに文字が続いても数値部分を変換します。数字として読めない文字列は 0 になります。

| 値の例 | 判定 |
|---|---|
| 未設定、空文字、`0`、`00`、`true`、`0abc` | 無効 |
| `1`、`2`、`-1`、`1abc`、`  +2tail` | 有効 |

値を設定しただけで helper 計算が必ず走るわけではありません。share の既定値は prompt chunk 長 `T` に応じて別途決まり、share が 0 なら helper は使われません（次節参照）。

根拠: CUDA/HIP 実装 `src/prefill/prefill.cpp:1557-1563`、SYCL 実装 `sycl/src/prefill/prefill.cpp:1508-1514`。

## 有効になる条件

`Prefill::set_stage_helper()` が helper を設定でき、prompt 実行時に `bind_stage_helper()` がすべての条件を満たす必要があります。

- 複数 GPU の layer split であり、helper が null でも同一 stage でもない。両 GPU の device ID が有効で異なり、MMQ plan が存在する。
- prompt 全体が1 chunkである。先頭 stage では `n <= m.T`、後続 stage ではその chunk 状態を引き継ぐ。
- 対象 chunk が `stream_all_min()` 以上。既定は1024 tokenで、`STRATA_PREFILL_STREAM_MIN` による変更を受ける。
- expert source があり、ring が8 slotより大きく、fused ring ではない。
- stage の全 layer が MMQ 対応である。native expert layout の場合、いずれかの層が fused native kernel に対応すると helper 経路を使わない。
- helper stage に必要な chunk 用 prompt buffer、MMQ context、ring などがある。
- 既存の peer prefill（`m.pp`）が設定されていない。したがって `--peer-device` を使う経路では helper は bind されない。

既定 share は `min(0.45, 0.5 - T / 16384)` で、結果が0.3以上のときだけ使い、それ未満は0です。そのため既定では約3.3K tokenを超える chunk は helper の対象外になります。`STRATA_PREFILL_HELP_FRAC` が設定されている場合は `atof` で読み、0〜1に clamp した値をすべての `T` に使います（空文字や数値変換不能値は0となり helper は無効、負値も0、1超は1）。この別変数で share を0にすれば `STRATA_PREFILL_HELP` が有効でも処理されません。

根拠: `src/prefill/prefill.cpp:1564-1579,1582-1588,1622-1639`; SYCL 対応箇所 `sycl/src/prefill/prefill.cpp:1515-1531,1533-1539,1604-1621`; stream 閾値 `src/prefill/prefill.cpp:158-168`; stage/helper の接続と実行 `src/program/generate.cpp:7700-7711`, `src/prefill/prefill.cpp:2122-2139,4172`。

## 実行時の詳細

各 stage の `set_stage_helper()` が `split_help_env()` を呼び、そこで `STRATA_PREFILL_HELP` を読む結果を function-local `static const bool` に保存します。プロセス内でこの初回判定が済んだ後の環境変更は再評価されません。起動時に環境を設定して使う想定です。CUDA/HIP 系の `src/prefill/prefill.cpp` と SYCL 系の `sycl/src/prefill/prefill.cpp` に同じ判定と同等の gate があります。

chunk の開始時に helper 条件を満たすと、stage は helper 用の `PeerPrefill` を一時的に active peer として使います。非 resident expert のうち source が pinned であるものから share 相当分を選び、helper GPU に送り、行を戻して本来の MoE 結果に加えます。全層の計算後に helper の copy/compute/output stream を同期して、通常の peer 状態に戻します。helper 用 mapped pinned host buffer は必要な chunk サイズまで確保されます（`src/prefill/prefill.cpp:1662-1684,2341-2427,3294-3306,4046-4053,2126-2139`）。

この環境変数専用の有効化ログはありません。タイミング計測が有効なら helper GPU の処理時間や peer-streamed expert 数を `strata prefill timing` として stderr に出すコードがあります（`src/prefill/prefill.cpp:4284-4297`）。

## 文書記載の測定

`docs/MULTI_GPU.md:85-97` は2x RTX 3090、UD-Q4_K_XL、P2Pなしの測定として、1.1K token prompt が496→723 tok/s、1.5Kが674→833、2Kが878→1,128、2.5Kが1,017→1,296、3Kが1,260→1,440と記載しています。同資料では4K/8K prompt と decode は不変とし、約3.3K tokenから既定 share を止める理由を「stage が重なり、share が得にならないため」と説明しています。これらは資料に記載された特定の機材・モデル・経路での測定値であり、他環境の性能を示すものではありません。
