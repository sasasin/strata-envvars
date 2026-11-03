# `STRATA_DS4_CPU_LANE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek 4.1 (DS4) の CPU lane が使う CPU 配置を名前で固定します。指定が有効なら `lane_cfgs()` がそのホストで生成した同名の構成を選び、モデル読み込み時の自動 lane 測定を止めます。これは DS4 実装内の明示的な環境変数読み取りです（`src/dsv41/ds4_model.cu:6848-6857,6872-6877`）。

## 値と判定

値は数値に変換せず、生成済み構成名と文字列全体を比較します。大文字小文字も区別されます。

| 環境変数の状態 | `make_pools()` の選択 | 自動測定 |
|---|---|---|
| 未設定 | 先頭の `cores` | 条件を満たせば実施 |
| `cores` | `cores` | 無効 |
| `pcores`、`smt`、`node` | 同名構成がこのホストで生成されていれば選択。なければ `cores` | 無効 |
| 空文字、その他の文字列 | 一致しないため `cores` | 無効 |

`cores` は常に構成候補の先頭です。`pcores` は異なる efficiency class の CPU core がある場合、`smt` は複数の logical CPU を持つ core がある場合に候補になります。`node` は file-backed expert を使い、`NH == 1` なのに複数の CPU node がある場合に限って追加されます。構成の生成条件は `src/dsv41/ds4_model.cu:6772-6818` にあります。

空文字や未知の値をエラーとして報告したり、別の名前に正規化したりする処理はありません。値が設定されているかの判定は `getenv(...) != nullptr` なので、空文字も「明示設定」として自動測定を抑止します（同 `:6853-6857,6875-6877`）。

## 有効になる条件

DS4 model の CPU pool を作る経路で読み取られます。通常の pack では expert placement の前に、GGUF では expert 読み込み後に `make_pools()` が呼ばれます（`src/dsv41/ds4_model.cu:3612-3629`）。このファイルは DS4 CUDA/HIP model 実装です。

`--cpu-threads N` が正数なら、選択した構成の worker 数を上限 `N` に制限します。これは環境変数の lane 名の選択を置き換えません。また、正数の `--cpu-threads` は自動測定も止めます。引数は `atoi` で読み取られ、既定値は 0 です（`src/dsv41/ds4_main.cpp:2526`, `src/dsv41/ds4_model.hpp:33-35`, `src/dsv41/ds4_model.cu:6843,6875-6877`）。

手動指定時は、値が有効な名前かどうかにかかわらず `tune_lane()` が直ちに戻ります。そのため、たとえばホストに `pcores` 候補がないのに `STRATA_DS4_CPU_LANE=pcores` としても `cores` が使われ、自動測定で別構成へ切り替わることもありません。

## 実行時の詳細

`make_pools()` は `lane_cfgs()` を作り、既定の選択 index 0 (`cores`) から始めて、環境変数と完全一致する候補が見つかればその index に変えます。続いて `pools_for()` が各 CPU node の pool を作ります。構成は `cores`（各 physical core の先頭 CPU）、`pcores`（最も高い efficiency class の core）、`smt`（各 core の logical CPU、最大 4 個を構成リストに追加）、および条件付きの `node`（単一 pool にまとめた core）です（`src/dsv41/ds4_model.cu:6772-6818,6820-6845,6850-6857`）。

名前の読み取りは pool 作成時、すなわちモデル load 中です。選択結果は `lane_name` と `pools` に保持され、リクエストごとの環境再読込はありません。自動測定の判定では `tune_lane()` が設定有無をもう一度調べますが、これも load 中です（同 `:6850-6857,6875-6877`; 呼び出し `:3789-3791`）。

未設定時の自動測定は、`--cpu-threads` が正数でないこと、環境変数が未設定であること、pool が空でないことをまず要求します。さらに測定対象候補が 2 個以上あり、どこかの layer に CPU lane 側の expert が 8 個以上ある必要があります。測定対象から `measured == false` の `smt` は除外されます。候補ごとの測定で 5% を超えて速くならない限り現在の構成を維持し、切り替えの有無にかかわらず測定結果を stderr に `ds4: CPU lane: ... (measured, ...)` と出します（`src/dsv41/ds4_model.cu:6875-6887,6920-6957`）。

verbose 時は初期 pool の thread 数と MXFP4 row 情報を `ds4: CPU lane: ...` と stderr に出します（同 `:6858-6864`）。明示指定値が不正でも、それ自体を示す警告や終了経路は見当たりません。値に応じて選ばれた CPU 配置は速度に関する設定で、実装コメントは出力を変えないとしています（同 `:6866-6873`）。

## 根拠

- 候補構成と host 条件: `src/dsv41/ds4_model.cu:6772-6818`
- pool の作成、`STRATA_DS4_CPU_LANE` の完全一致判定: `src/dsv41/ds4_model.cu:6820-6857`
- `--cpu-threads` による worker 数制限、自動測定の除外、測定とログ: `src/dsv41/ds4_model.cu:6843,6872-6877,6880-6887,6920-6957`
- pool 作成の呼び出しと load 時期: `src/dsv41/ds4_model.cu:3612-3629,3789-3791`
- CLI 引数と既定値: `src/dsv41/ds4_main.cpp:2526`, `src/dsv41/ds4_model.hpp:33-35`
