# `STRATA_DF_QB_Q4`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

QSA の検証窓で、Q4_0 KV を使用している場合にも複数行をまとめる batched-QSA 経路を許可するかを制御する。未設定または `atoi` で非ゼロになる値なら許可し、ゼロになる値なら Q4_0 KV のときだけ従来の行ごとの処理へ戻す。KV の保存形式そのものは変更しない。切替は `Verifier::record_window` の QSA 層処理内で `qb` に反映される（`engine/src/core/verify.cpp:1468-1477, 2046-2059`）。

## 値と判定

QSA 層の処理で初めて評価される関数内 `static const bool` が `std::getenv` で読み、未設定なら `true`、設定済みなら `std::atoi(e) != 0` を保存する。空文字、数字に変換できない文字列、先頭が `0` の文字列（例 `0anything`）は `atoi` の結果が 0 となり無効。`1`、`-1`、`2tail` は非ゼロとなり有効。先頭の空白と符号は `atoi` の規則で扱われ、先頭の数字列以降は判定に使われない（例 `  +1tail` は有効）。大文字小文字を使った真偽値文字列を認識する処理や、全体文字列の妥当性検査はない。`atoi` が表現できない範囲の数値はコードに安全な境界処理がないため、挙動を規定しない（`engine/src/core/verify.cpp:2055-2058`）。

| 条件 | unset | 設定時に許可される値 | 設定時に許可されない値 |
|---|---|---|---|
| CUDA / HIP の GPU engine で Q4_0 KV の QSA 層を処理 | 許可 | `1`, `-1`, `2tail`, `  +1tail` など `atoi` が非ゼロを返す値 | 空文字、`0`, `0anything`, `true`, `false`, `  -0tail` など `atoi` が 0 を返す値 |
| Q4_0 KV 以外 | 変数の値にかかわらずこの変数による制限なし | ― | ― |

## 有効になる条件

- `--kv q4_0`（または別名 `--kv q4`）で Q4_0 KV が選ばれ、その QSA state の `st.kv_q4` が真であること。`--kv` の値は `generate.cpp` で検証され、`qsa_set_kv_q4` に反映される（`engine/src/program/generate.cpp:5014-5020`）。
- 環境変数が有効でも、`qb` は `STRATA_DEC_BATCH` が許可し、検証窓の行数 `n` が 1 より大きく、native QSA と native RoPE が有効な場合に限り真になる。`STRATA_DEC_BATCH` は別の関数内 static として unset または `atoi` 非ゼロで有効（`engine/src/core/verify.cpp:1489, 2059`）。
- このソースは CUDA / HIP GPU engine に含まれる（`engine/cmake/strata_gpu_engine.cmake:1-8, 310-316`）。CMake 上 Metal / SYCL の engine はこの CUDA / HIP 共通のファイル群とは別であり、この変数による挙動は確認できない。
- Q4_0 以外の KV state では `!st.kv_q4` が条件を満たすため、この変数は `qb` を止めない。Q4_0 を選ぶ `--kv` とこの環境変数に優先順位はなく、前者が KV 形式を選び、後者は Q4_0 時の batched 経路だけを追加で許可・抑止する。

## 実行時の詳細

読み取りはプロセス起動時ではなく、`Verifier::record_window` が QSA 層の処理へ到達して static 初期化が行われた時点の一度だけ。初回評価後に環境を変更しても同じプロセス内の値は更新されない。QSA 層を処理しない場合、この static 初期化には到達しない（`engine/src/core/verify.cpp:1468-1477, 2019-2023, 2055-2059`）。

`qb` が真なら、QSA indexer key/query の行列演算、query の正規化・RoPE、K の正規化・RoPE、および attention gate の一部が窓の複数行をまとめる形で呼ばれる。偽なら該当箇所は行ごとのループへ進む（`engine/src/core/verify.cpp:2091-2095, 2128-2138, 2283-2315, 2338-2341, 2594-2603`）。Q4_0 の KV append 自体は `qb` の真偽とは別に実行される（`engine/src/core/verify.cpp:2366-2368, 2400-2402`）。

`record_window` は単一窓と batch capture の双方から呼ばれる（`engine/src/core/verify.cpp:3278-3285, 4684-4697`）。変数専用の警告・有効ログ・終了経路はない。検証窓の capture 中に別の処理が失敗した場合は `record_window` のエラー文字列が呼び出し元へ返り、通常窓ではそのエラーを返し、batch capture では同様にエラーを返す（同 `verify.cpp:3278-3289, 4687-4697`）。

## ログと測定値

この変数を直接知らせる実行時ログはない。`docs/DETAILS.md` に本変数の説明・測定表は見つからなかった。コードコメントには、6-token verify graph のノード数が 2610 から 1950 になったこと、記載された gfx1201 / sm_86 / sm_60 の環境と短・長 prompt で生成 ID が同一だったことが記されている。一方、同じコメントは RX 6900 XT で `--kv q4_0`、KV streaming、MTP を併用した最初の graph launch fault について、graph サイズが原因かは未確認としている。測定条件の詳細や独立した再測定は本調査では確認していないため、これらを一般的な性能・正確性の保証とは扱わない（`engine/src/core/verify.cpp:2049-2054`）。

## 根拠

- 読み取り、値の変換、Q4_0 条件との結合: `engine/src/core/verify.cpp:2055-2059`
- `STRATA_DEC_BATCH` の既定と評価: `engine/src/core/verify.cpp:1489`
- KV 形式の CLI 選択: `engine/src/program/generate.cpp:5014-5020`
- batched と行単位の QSA 処理: `engine/src/core/verify.cpp:2091-2095, 2128-2138, 2283-2315, 2338-2341, 2594-2603`
- Q4_0 KV の append とエラー伝播: `engine/src/core/verify.cpp:2366-2368, 2400-2402, 3278-3289, 4687-4697`
- CUDA / HIP GPU engine への収録: `engine/cmake/strata_gpu_engine.cmake:1-8, 310-316`
