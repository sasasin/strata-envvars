# `STRATA_SPLIT_MISS_MS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--layer-split auto` の GPU 層分割探索で、キャッシュに収まらない profiled expert の routed mass を予測 decode 時間へ換算する係数（ms / mass unit）を指定する。値を変えると配置探索で評価するスコアと選ばれる層境界が変わり得る。キャッシュ容量や実際の expert 実行を直接変更する設定ではない。CUDA/HIP 実装と SYCL 実装の両方に読み取り箇所がある（`engine/src/program/generate.cpp:6959-6961,7015,7099-7108`、`engine/sycl/src/program/generate.cpp:3921-3924,3947,3993-4023`）。

## 値と判定

各実装とも `getenv` が null なら `190.0`、設定されていれば `std::atof` の戻り値を使う。文字列全体の妥当性確認、clamp、エラー処理はない。空文字や先頭から数値に変換できない文字列（例 `""`、`abc`）は通常 `0` になり、数値の後ろの文字は無視される（例 `12ms` は `12`）。したがって `0` はミスコストを 0 にし、負数も拒否されずそのまま計算に入る。`1` や `190` はそれぞれその係数として使われる。空白は `atof` の数値変換規則に従う。大文字小文字による判定はない。

| ビルド / 経路 | unset | 設定時に使われる値 | 検証・境界 |
|---|---:|---|---|
| CUDA/HIP `engine/src/program/generate.cpp` | `190.0` | `atof` が変換した double。例 `1` → 1、`12ms` → 12、空文字・`abc` → 0 | 範囲検証・clamp なし。負数もそのまま使う |
| SYCL `engine/sycl/src/program/generate.cpp` | `190.0` | 同上 | 同上 |

根拠: `engine/src/program/generate.cpp:7015`、`engine/sycl/src/program/generate.cpp:3947`。

## 有効になる条件

- `strata generate` / `strata serve` のうちサーバーモードで `--layer-split auto` を指定し、複数 GPU にまたがる自動配置探索まで進む必要がある。`--layer-split` は `o.serve` が真でなければ受理されず、`split_auto` は値が文字列 `auto` の場合に設定される（`engine/src/program/generate.cpp:4785-4807,4848-4853`）。探索部の条件は `multi_gpu && split_auto`（`engine/src/program/generate.cpp:6959`、`engine/sycl/src/program/generate.cpp:3921`）。
- `--layer-split K...` のような明示境界ではこの探索を通らず、この変数は読まれない。`--split-skip-if-fits` が有効で CUDA0 にプロファイル全体が収まると自動分割が解除され、同じく探索・読み取りをしない（CUDA/HIP: `engine/src/program/generate.cpp:6450-6483`、SYCL: `engine/sycl/src/program/generate.cpp:3522-3573`）。可視 GPU が 1 台の場合も auto は解除される（CUDA/HIP: `engine/src/program/generate.cpp:4836-4839`、SYCL: `engine/sycl/src/program/generate.cpp:2308-2318`）。
- 探索スコアはモデルの層数・expert profile、各 stage の空き VRAMと session carve による held mass から計算される。miss 係数はその「保持できなかった mass」に掛かるため、モデル状態や配置の空き容量が結果に関わる。expert profile が空なら miss 項は全候補に共通（CUDA/HIP は 0、SYCL は `miss_ms`）となるため、係数は候補の相対順位を変えない（`engine/src/program/generate.cpp:7069-7108`、SYCL: `engine/sycl/src/program/generate.cpp:3993-4023`）。
- CUDA/HIP では `STRATA_SPLIT_LINK_ABS`、`STRATA_SPLIT_UNIFORM`、`STRATA_SPLIT_LINK_MIN` による stage ごとの `link_scale` がこの係数に掛かる。`STRATA_SPLIT_COVER_B` は mass 曲線を選び、`STRATA_SPLIT_SPEED_SCALE` は CUDA/HIP の層時間側を調整する。SYCL の式は link scale を適用せず、総未保持 mass に係数を掛ける（`engine/src/program/generate.cpp:6990-7007,7040-7047,7099-7108`、`engine/sycl/src/program/generate.cpp:3970-3982,4017-4023`）。
- CUDA/HIP で 2〜4 GPU の候補が複数ある場合は、係数が候補の順位に影響する。5 台以上ではコード上 proportional 配置だけを評価するため、値は予測値に入るが選択境界の候補比較には使われない（`engine/src/program/generate.cpp:7295-7385`）。SYCL も 2〜4 GPU で配置候補を列挙し、5 台以上は proportional 配置へ進む（`engine/sycl/src/program/generate.cpp:4076-4150`）。

## 実行時の詳細

環境変数は自動分割探索の開始後、stage の layer/link 情報を準備した後に読み取られ、探索候補を採点する間はそのローカル値を使う。関数内 static cache ではなく、各探索呼び出しで評価されるため、プロセス起動前に設定した値がその探索に使われる。通常の実行中に環境を変更して再探索する経路は確認できない（`engine/src/program/generate.cpp:6959-7015,7100-7108`、`engine/sycl/src/program/generate.cpp:3921-3947,3993-4023`）。

CUDA/HIP は stage ごとに、未保持 routed mass を `miss_ms * link_scale[i]` で予測値へ加算する。SYCL は `miss_ms * (1 - held_mass)` を加算する。両方とも各 stage の層時間を加えた予測値で候補を選ぶ。この変数によって変わるのは探索コストモデルと auto が決める層境界であり、実行時に expert の読み込みを増減させたり、その時点の実測遅延を制御したりはしない（`engine/src/program/generate.cpp:7099-7108`、`engine/sycl/src/program/generate.cpp:4017-4023`）。

## ログと測定値

成功した auto 探索は stderr に `strata generate: layer split auto: K=... - predicted ... ms per decode window; the caches hold ...` の形式で予測値・held profile 数・routed mass・配置候補数を出す（`engine/src/program/generate.cpp:7510-7515`、SYCL: `engine/sycl/src/program/generate.cpp:4173-4178`）。この変数専用の警告や無効値エラーはなく、変換できない値も `atof` の結果として探索に入る。ソースにある既定値 190 ms は予測モデルの係数であり、この調査では性能測定を実行していない。

## 根拠

- `engine/src/program/generate.cpp:4785-4807,4836-4853` — CLI から `split_auto` を設定し、serve 要件・GPU 数を判定。
- `engine/src/program/generate.cpp:6450-6483` — `--split-skip-if-fits` による auto 分割解除。
- `engine/src/program/generate.cpp:6959-7015,7040-7047,7069-7108` — CUDA/HIP 探索条件、値の読み取り、mass 曲線、予測式。
- `engine/src/program/generate.cpp:7295-7385,7510-7515` — 配置候補探索と結果ログ。
- `engine/sycl/src/program/generate.cpp:3921-3947,3970-3982,3993-4023,4076-4150,4173-4178` — SYCL 探索条件、値の読み取り、予測式、候補探索とログ。
