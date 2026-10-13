# `STRATA_SPLIT_OWN_PLACE`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。CUDA と SYCL の Strata 所有実装を確認した。

## 役割

複数 GPU の `--layer-split auto` が各 stage の配置を探索するとき、プロンプト用バッファを独立して確保する構成の見積もりにも、そのバッファ分の VRAM 予約を含めるかを選ぶ。正確な値 `reserve` を指定すると探索時の stage 空き容量から予約を差し引く。ほかの値では、独立バッファ構成でも探索時にはその予約を差し引かない。

## 値と判定

値は `std::string(v) == "reserve"` で文字列全体を比較する。数値変換、空白除去、大文字小文字の変換はしない。

| 環境変数の値 | `place_with_reserve` |
|---|---:|
| 未設定 | `false` |
| 空文字 | `false` |
| `reserve`（完全一致） | `true` |
| `Reserve`、` reserve`、`reserve `、その他すべて | `false` |

値の取得結果は関数内 `static const bool` に保存される。初回評価以降、同一プロセスで環境を書き換えても再評価されない。

## 有効になる条件

動作差が生じるには、複数 GPU の layer split で `--layer-split auto` の配置探索を行い、かつプロンプト用バッファを各 stage が独立して持つ状態である必要がある。独立バッファ状態は、この経路では主に `STRATA_SPLIT_OWN` が有効になって `split_own_auto` が立つことで作られる。

`STRATA_SPLIT_OWN` が有効でない場合、または明示的な `--layer-split K[,K2...]` で自動配置探索をしない場合、この変数による探索容量の差はない。単一 GPU で自動 split が解除された場合も対象外。CUDA 実装と SYCL 実装に同じ判定と容量計算がある。

## 実行時の詳細

自動配置の探索では各 stage の `stage_room(..., search=true)` が空き VRAM から予約額を引き、候補配置の容量として使う。`split_own_auto` が真で `STRATA_SPLIT_OWN_PLACE` が `reserve` 以外なら、探索に限ってプロンプトバッファ見積もり `split_pf_mib` を 0 にする。`reserve` なら `split_pf_mib` を含めるため、探索上の各 stage の空き容量がその分小さくなり、自動配置結果に影響し得る。

`split_pf_mib` は、プロンプト chunk が正で、バッファを cache から借りない場合に `160 + (prefill_chunk * 680) / 1024` MiB として計算される。複数 GPU で chunk が 1024 以上なら、条件に応じて 96 個の expert blob ring 分も加算される。これは探索用の予約見積もりである。探索後に stage を準備する `stage_room` 呼び出しは `search=false` の既定値を使うため、この環境変数にかかわらず通常の `split_pf_mib` を予約計算に含める。

変数を `reserve` にしたこと自体を知らせる専用ログは見当たらない。配置探索や stage 容量のログは出るが、変数名・判定値を直接表示する実装はない。`docs/DETAILS.md` にこの変数の説明は見当たらない。ソースコメントには、9070 XT + R9700 の測定で reserve を探索に含めると境界が K=28 から K=32 に動き、decode が 58.4 から 54.8 tok/s になったとの記載がある。測定手順や反復数はその箇所にないため、この記載を一般的な性能結果とは扱えない。

## 根拠

- `src/program/generate.cpp:3639-3643` — own prompt buffers の探索方針と `reserve` の説明。
- `src/program/generate.cpp:3675-3690` — 環境値の完全一致判定、予約額を探索時に 0 にする条件、stage 空き容量の計算。
- `src/program/generate.cpp:2348-2426` — `multi_gpu`、`split_own_auto`、独立 prompt buffers を有効にする条件と `STRATA_SPLIT_OWN` の判定。
- `src/program/generate.cpp:5310` — 探索後の stage 準備で `stage_room` を `search=false` のまま使う呼び出し。
- `sycl/src/program/generate.cpp:3496-3536` — SYCL の同じ判定と容量計算。
- `sycl/src/program/generate.cpp:2084-2170` — SYCL の `split_own_auto` 設定条件。
- `sycl/src/program/generate.cpp:4896` — 探索後の stage 準備での `stage_room` 呼び出し。
