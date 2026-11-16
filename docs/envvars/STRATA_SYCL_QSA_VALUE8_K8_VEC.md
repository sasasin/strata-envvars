# `STRATA_SYCL_QSA_VALUE8_K8_VEC`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

SYCL の QSA decode で、Battlemage 向け int8 K/V の chunk-down 処理を `launch_normal_qsa_vector` に切り替えるかを制御する。未設定または値の先頭文字が `1` のとき vector 経路を許可し、それ以外では `QsaChunkDown` kernel と merge kernel に進む。これは decode attention の実装選択であり、環境変数自体を読むのは SYCL 実装だけである。読み取りは `launch_qsa_chunk_down` と MTP 専用の `qsa_decode_attn_batch_try_two_stage` にある。後者が成功した場合も `launch_normal_qsa_vector` を呼ぶ（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2560-2589, 2592-2625`）。

## 値と判定

両方の読み取り箇所で `std::getenv` が返すポインタを確認し、未設定なら `true`、設定済みなら `v[0] == '1'` の場合だけ `true` にする。文字列全体の解析や数値変換は行わない。空文字は設定済みで先頭文字が `'\0'` のため無効。`1` で始まれば後続文字を問わず有効で、`10`、`1anything` も有効になる。先頭が `1` でない値（`0`、`true`、` 1`、`2`、空文字）は無効。大文字小文字は関係しない。境界値・負値の数値検査もない。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `launch_qsa_chunk_down` 経由 | 有効 | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `-1` |
| `qsa_decode_attn_batch_try_two_stage` 経由 | 有効 | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `-1` |

それぞれの関数に独立した関数内 `static const bool` があるため、各経路で初めて判定された値がプロセス内で保持される。その後に環境を変更しても、すでに評価済みの経路の判定には反映されない。読み取り行は `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2568-2571, 2604-2607`。

## 有効になる条件

- SYCL バックエンドであること。この名前の読み取りは `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp` にのみある。
- `qsa_decode_attn_batch` / `qsa_decode_attn_step` から chunk-down dispatch に入るには、`STRATA_SYCL_QSA_CHUNK_DOWN` が有効で、形状が `cap == 2051` かつ query 数が 1〜6 または 32、または `cap == 32768` かつ query 数が 1〜6、`n_head == 24`、`n_head_kv == 2`、`page_size == 4`、実行デバイスが Battlemage であることが必要。`STRATA_SYCL_QSA_CHUNK_DOWN` も未設定または先頭文字 `1` で許可される（同ファイル `:961-969`）。
- `launch_qsa_chunk_down` 内で K/V が int8（`pools.k_q` と `pools.v_q` が非 null、`k_q4` と `v_q4` が null）であることが必要。条件を満たさない場合は通常の `qsa_decode_attn_batch` に戻る（同ファイル `:2563-2566`）。
- `launch_qsa_chunk_down` の vector 分岐は、この環境変数に加え、`cap == 2051` で query 数が 1、2、3、4、32 のいずれか、または `cap == 32768` で query 数が 1 であることが必要。上記の chunk-down 対応形状のうち、`cap == 2051` の 5、6 query はこの vector 分岐の形状条件に含まれない（同ファイル `:2572-2574`）。
- MTP 専用の two-stage 経路はさらに `cap == 32768`、query 数 1、head 数 24、KV head 数 2、head dimension 256、page size 4、必要なポインタと int8 K/V scale が揃うこと、q4 pool がないことを要求する。加えて chunk-down 対応条件、in-order queue、十分な secondary scratch、secondary scratch が scratch・出力・query の各領域と重ならないことが必要。いずれかを満たさなければ `false` を返し、呼び出し元の通常の `qsa_decode_attn_batch` にフォールバックする（同ファイル `:2592-2625`; 呼び出し元 `sycl/src/core/mtp.cpp:1053-1060`）。

## 実行時の詳細

通常の batch 経路では `qsa_decode_attn_batch` が対応形状・Battlemage・int8 KV のとき `launch_qsa_chunk_down` を呼ぶ。step 経路も同じ対応条件と int8 KV の場合に呼ぶ（`sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1015, 1307-1324`）。`launch_qsa_chunk_down` は、変数が有効で vector shape に一致すれば `launch_normal_qsa_vector` を呼び、そうでなければ `QsaChunkDown` kernel と `attn_merge_kernel` を起動する（同ファイル `:2560-2589`）。vector launch 内部では別の B60 条件による kernel 選択もあり、それ以外は `QsaVectorCodes` kernel を使う（同ファイル `:2515-2559`）。

MTP の batch query 数 1、`cap == 32768` の適合ケースでは、呼び出し元が先に two-stage 経路を試す。この関数でも同じ環境変数を独立にキャッシュして判定する。無効なら `false` を返し、呼び出し元は通常の batch 経路に進む。有効でも queue が in-order でない、workspace 不足、領域重複などの場合は同じ fallback になる。有効かつ残りの条件を満たせば vector launch に進む（`sycl/src/core/mtp.cpp:1053-1060`; `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2592-2625`）。

この変数について、Strata は起動時の警告や専用ログを出さない。通常経路のサポート外 geometry / buffer 不足は `qsa_decode_attn_batch: unsupported geometry or missing buffers` を stderr に出して `exit(1)` するが、変数単独の無効値がその終了を起こすものではない（同ファイル `:1001-1008`）。

## ログと測定値

対象変数の値や選択した vector / chunk-down kernel を報告するログはない。`docs/DETAILS.md` にこの変数固有の測定値は記載されていない。`docs/SETTINGS.md:373` は Intel Arc 向けの `on / off` 候補として掲載するが、実際の値判定と適用条件は上記ソースのとおりである。

## 根拠

- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:961-969` — chunk-down 機能の別環境変数、形状、Battlemage 条件。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:1001-1015, 1307-1324` — batch / step からの dispatch。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2515-2559` — vector launch 内の kernel 選択。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2560-2589` — 対象変数の読み取りと chunk-down fallback。
- `sycl/src/kernels/cuda/qsa_decode_attn.dp.cpp:2592-2625`; `sycl/src/core/mtp.cpp:1053-1060` — MTP two-stage 経路と呼び出し側 fallback。
- `docs/SETTINGS.md:373`; `docs/DETAILS.md:1-7` — 設定一覧と技術資料の範囲。
