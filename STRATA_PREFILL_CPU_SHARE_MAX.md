# `STRATA_PREFILL_CPU_SHARE_MAX`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

CPU prefill share が有効なとき、ルーティング後に CPU と GPU で expert を分担できる prompt chunk の上限を token 数で指定します。値は「常にこの長さの chunk を使う」という指定ではなく、実際の chunk がこの上限未満なら share 用の staged path を選べる、という上限です。chunk 長そのものは別の prompt chunk 設定や planner が決めます。

この上限は `stream_all_min()` として prefill 実装内で共有され、該当 chunk のリング容量、expert streaming/fused 経路の選択、share 用バッファのサイズ計画にも使われます。上限を大きくすると share 対象になり得る chunk が増えますが、share を有効にする変数ではありません。

## 値と判定

値は `std::atoll` で読み、その結果を `max(1024, 値)` にします。未設定時の値は 3072 です。文字列全体の妥当性確認や上限 clamp はありません。

| 環境変数の状態 | `cpu_share_max()` の値 |
|---|---:|
| 未設定 | 3072。ただし下記の既定 share 条件では実効値 1024 |
| `0`、負値、数値で始まらない文字列、空文字 | 1024 |
| 1024 未満の正値 | 1024 |
| 1024 以上の正値 | 変換された値 |

`atoll` は先頭の空白や符号を含む10進整数を読み、数値の後ろの文字列は値の判定に使いません。たとえば `2048junk` は 2048、`junk2048` は 0 として扱われ、後者は 1024 になります。空文字は unset ではなく設定済みとして扱われます。範囲外整数の変換結果はこの実装で検査されません。

CPU share がデフォルト有効になる経路では、`STRATA_PREFILL_CPU_SHARE` が未設定で、かつこの変数も未設定なら、実測された既定範囲に合わせて実効値を 1024 にします。`STRATA_PREFILL_CPU_SHARE_MAX` を明示設定すると、この特例は使われず、上表の値が実効値です。したがって `STRATA_PREFILL_CPU_SHARE_MAX=3072` はこの経路でも上限を 3072 にします。

## 有効になる条件

- CPU share 自体が有効である必要があります。`STRATA_PREFILL_CPU_SHARE=0` なら share は無効で、この上限は share の効果を生みません。`STRATA_PREFILL_CPU_SHARE=auto` または 0 より大きい数値は share の候補になります。
- 未設定の CPU share を既定で有効にするのは、CUDA 系ビルドの対象経路で、単一 GPU、batch slot なし、CPU pool あり、GPU cache に未常駐 expert があり、既定 share のメモリ判定を通る場合です。メモリ不足等では既定 share は arm されず、理由を stderr に出します。
- layer split、batch slot あり、pool なし、GPU cache に全 expert がある場合は既定 share の対象外です。明示的な CPU share 設定は別途評価されます。HIP/HIP GFX906 のビルドでは既定 share を arm しません。
- 上限値は chunk 長が閾値と等しい場合も share の対象外です。実装は `T < stream_all_min()` を staged/share 側、`T >= stream_all_min()` を全 expert streaming 側として分けます。

## 実行時の詳細

`Prefill::arm_cpu_share()` が share を適用する経路で `cpu_share_max()` を `g_stream_min_share` に設定します。通常の generate 経路と serve 経路では prompt chunk のバッファ／loan を計画する前に arm され、`Prefill::init()` からも pool の有無に応じて arm 判定が呼ばれます。`cpu_share_max()` の数値と「変数が設定済みか」の判定は関数内の `static` に保存されるため、最初に評価された後のプロセス内環境変更は反映されません。

chunk が閾値未満なら `ring_slots()` は通常の大きな streaming ring でなく `STAGE`（8 slot）を返し、実行ループでは `stream_all` が false になります。CPU share が有効で CPU pool を確保できれば、ルーティング後に CPU が担当する expert を選び、CPU が読み出す分以外の expert は GPU 側で処理します。chunk が閾値以上なら通常の全 expert streaming 経路になり、この CPU share は使われません。閾値は fused layout や share 用バッファのサイズ計画にも使われるため、chunk の実サイズや必要な VRAM を直接変更する値ではありません。

既定 share をメモリ不足で arm しない場合は、stderr に `strata: the CPU prefill share is not armed by default: ...` と表示されます。CPU share を明示していてメモリ判定が不足する場合は警告を出しつつ明示設定を保持します。share の実行中に pinned buffer の確保に失敗すると、その run では share を停止し、GPU が全 expert を処理する旨を stderr に出します。

## 根拠

- `src/prefill/prefill.cpp:148-152` — `stream_all_min()` の既定値と share 閾値の参照。
- `src/prefill/prefill.cpp:169-193` — CPU share 設定の有無、`STRATA_PREFILL_CPU_SHARE_MAX` の `atoll`、1024 下限、既定 share 時の1024特例。
- `src/prefill/prefill.cpp:1919-1930` — share を arm する条件と閾値の反映。
- `src/prefill/prefill.cpp:277-299, 1020-1038, 1823-1826, 2302-2312` — 閾値によるリング、layout、streaming/share 実行経路の切替と buffer sizing API。
- `src/program/generate.cpp:6899-6926, 6978-6986, 12556-12561` — 既定 share のメモリ／cache 条件、serve/generate 経路での arm とログ。
- `include/strata/prefill/prefill.hpp:173-187` — API コメントに記された share の適用範囲と staged chunk の上限。
- `docs/DETAILS.md:1564-1580` — 既定 share、上限 1024/3072 の説明、記載された測定条件とメモリ不足時の扱い。資料は CUDA の RTX 3060、Tesla P100、RTX 5070 での既定範囲の測定を記載しています。性能値はその条件の資料記載であり、この調査で再測定したものではありません。
