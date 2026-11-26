# `STRATA_SPLIT_HEADROOM`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

SYCL エンジンの `--layer-split auto` が複数 GPU のレイヤー境界 `K` を選ぶとき、推定 decode 時間が最速候補に近い配置の中から、各 GPU の担当レイヤーの全 expert 分を差し引いた後に最も余裕が残る配置を選ぶ機能を有効・無効にする。unset では有効、`0` 相当では無効。無効時は従来どおり推定時間が最小となる最初の候補を使う。分割後の `K` を選ぶだけで、モデルや token の選択を直接変更する処理ではない（`engine/sycl/src/program/generate.cpp:4025-4060, 4152-4178`; 選択規則は `engine/include/strata/program/split_rules.hpp:118-138, 187-199`）。

この読み取りは SYCL 実装だけにあり、通常の単一 GPU 実行、手動 `--layer-split K,...`、および自動分割を実行しない経路では参照されない。layer split の受付自体に `--serve` が必要で、少なくとも異なる複数 GPU への `--layer-split auto` が成立した場合に検索が行われる（`engine/sycl/src/program/generate.cpp:2266-2288, 2302-2329, 2333, 3921`）。

## 値と判定

`std::getenv` が返す文字列を `std::atoi` に渡し、その結果が 0 以外なら有効とする。文字列全体の妥当性検査や `true` / `false` の解釈はない。`atoi` の数値変換に従い、先頭空白と符号を許し、数値の後ろの文字は判定に使わない。unset のみ既定で有効。空文字や数値に変換できない先頭文字は `atoi` が 0 を返すため無効となる（`engine/sycl/src/program/generate.cpp:4032-4035`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| SYCL の複数 GPU `--layer-split auto` 検索 | 有効 | `1`, `-1`, `1abc`, ` 1` | `0`, `-0`, `0anything`, `true`, ``, `abc` |
| その他の実行経路 | 読み取られず、適用なし | 適用なし | 適用なし |

整数変換の範囲外入力について、Strata 側に明示的な検査やエラー処理はない。CLI 引数でこの環境変数を上書きする処理はない。近傍候補の時間幅は別変数 `STRATA_SPLIT_HEADROOM_TOL` が決め、未設定時 `0.002`（0.2%）である。`STRATA_SPLIT_HEADROOM=0` はその幅にかかわらず headroom による選び直しを止める（`engine/sycl/src/program/generate.cpp:4032-4037, 4047-4052`）。

## 有効になる条件

- SYCL エンジンを含む実行ファイルで、Strata が layer split を受け付ける `--serve` 経路に入ること（`engine/sycl/src/program/generate.cpp:2266-2288`）。
- `--layer-split auto` が複数 GPU の分割として成立すること。自動分割に使う stage GPU は primary GPU と同じ SYCL backend の GPU に限られる。自動分割先がなく単一 GPU なら `--layer-split auto` を解除する（`engine/sycl/src/program/generate.cpp:2294-2305, 2313-2316`）。
- `--split-skip-if-fits` が全 profiled pair を1枚目の GPU に載せられると判定した場合は分割状態を解除するため、後段の headroom 検索も実行されない（`engine/sycl/src/program/generate.cpp:3526-3569, 3921`）。
- 有効値でも選び直しが起きるのは、候補が複数あり、`STRATA_SPLIT_HEADROOM_TOL` の範囲内で最速候補と異なる候補の方が最小 spare を大きくする場合だけ。余裕量も同じなら推定時間が速い候補が優先される（`engine/include/strata/program/split_rules.hpp:126-138`）。

## 実行時の詳細

変数は自動分割の検索ブロック内にある関数ローカル `static const bool` の初期化ラムダで読み取られる。したがって、そのプロセスがこのブロックに初めて到達した時に一度判定され、同一プロセスで後から環境を変更しても再評価されない。ブロックに到達しない経路では読み取り自体がない（`engine/sycl/src/program/generate.cpp:3921, 4032-4035`）。

有効時は各配置を推定時間と最小 spare で記録する。spare は各 stage の空き容量から、その担当レイヤー範囲の session と全 expert の必要量を引いた値のうち、最小のもの。最速推定時間に対して `tol > 0` なら最大 `tol` の相対幅まで、`tol <= 0` なら同率最速だけを候補として、最小 spare が最大の配置を選ぶ。同率 spare では推定時間が速い方を選ぶ（`engine/sycl/src/program/generate.cpp:4044-4052`; `engine/include/strata/program/split_rules.hpp:126-138, 187-199`）。

`STRATA_SPLIT_HEADROOM` が無効なら配置の記録を省き、最小推定時間として見つかった最初の `best` を保持する。有効時も選び直しがなければ同じ `best` を使う。最終的な境界を `split_at` に設定し、その後の stage 構成・レイヤー範囲に使う（`engine/sycl/src/program/generate.cpp:4047-4060, 4152-4178`）。

## ログと測定値

headroom による選び直しが起きる場合、stderr に次の形式で変更前後の `K`、推定時間、expert 分を超える最小余裕量が出る。

`strata generate: layer split auto: K=%s instead of K=%s (predicted %.1f vs %.1f ms): its tightest card keeps %.2f GiB beyond all its layers' experts, against %.2f GiB (#1440: a full card can page to system memory); STRATA_SPLIT_HEADROOM=0 keeps K=%s`

選び直しがない場合、この変更ログは出ない。自動分割検索の終わりには、選択された `K` と推定値などを示す通常ログが stderr に出る。`STRATA_SPLIT_HEADROOM` 固有の失敗・終了経路はない（`engine/sycl/src/program/generate.cpp:4152-4178`）。

## 根拠

- `engine/sycl/src/program/generate.cpp:2266-2329` — `--serve`、`--layer-split auto` の受付と SYCL stage GPU 条件。
- `engine/sycl/src/program/generate.cpp:3526-3569, 3921-3935` — `--split-skip-if-fits` による分割解除、および自動分割検索の条件と環境変数読み取り。
- `engine/sycl/src/program/generate.cpp:4025-4060, 4152-4178` — 候補の記録、切替、`split_at` 設定とログ。
- `engine/include/strata/program/split_rules.hpp:118-138, 187-199` — 最速候補、許容幅内の headroom 選択、spare の算出。
