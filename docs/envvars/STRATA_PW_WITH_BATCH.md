# `STRATA_PW_WITH_BATCH`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--batch` の request slot と `--pipeline-windows` の併用時に、パイプラインを無効化する既定の制約を解除する opt-in 変数。これ自体は `--pipeline-windows` を有効化せず、値が有効でも batch slot の window をパイプライン化しない。solo path の window はパイプラインを使えるようになり、batch windows は使わない。読み取りと判定は `engine/src/program/generate.cpp` の起動時セットアップにある（6547-6559 行）。

## 値と判定

`std::getenv` の結果が null でなく、かつ先頭 byte が文字 `'1'` なら真。それ以外は偽。文字列全体の parse・比較はせず、空白除去、大文字小文字変換、数値妥当性検査もない（`engine/src/program/generate.cpp:6555-6559`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 全 build | 偽（batch が pipeline を塞ぐ） | `1`, `10`, `1anything` | 空文字, `0`, `true`, ` 1`, `01` |

## 有効になる条件

- `--batch N`（または同義の `--slots N`）が指定され、`N != 0` であること。この場合に限り、この変数の真偽が `batch_blocks_pw` に反映される。`--batch` がない場合、値を読み取っても pipeline の可否には影響しない（`engine/src/program/generate.cpp:4041-4042,6555-6559`）。
- `--pipeline-windows` が実際に有効になること。この変数だけでは有効化されない。`--pipeline-windows 0` は無効のまま。明示値が正なら、`--serve`、GPU ごとに stage を分けた layer split、MTP drafter と `--spec >= 2` が必要で、その他の非対応条件でも無効化される（`engine/src/program/generate.cpp:4119,6584-6601`）。
- `--pipeline-windows` の自動選択（未指定時）では、HIP build でのみ自動候補になり、`--serve`、multi-GPU layer split、stage 数の条件を満たし、`STRATA_PIPELINE_AUTO=0` で止められず、さらに MTP、`--spec >= 2`、`--peer-device` なし、helper cache なし、`--adapt-async` なし等が必要。CUDA build ではこの自動経路をコードが明示的に off にする。この変数が batch による除外を外しても、他の条件は変えない（`engine/src/program/generate.cpp:6560-6579`）。
- 明示的な正の `--pipeline-windows` では、`--batch` があるとき `STRATA_PW_WITH_BATCH` が未設定または無効なら pipeline は off にされる。有効なら batch による拒否条件を通過するが、上記の他の検査は残る（`engine/src/program/generate.cpp:6584-6604`）。
- 変数の読み取り箇所自体には OS / GPU backend の条件付きコンパイルはない。自動選択の HIP 限定は別途 `STRATA_USE_HIP` の compile-time 分岐による（`engine/src/program/generate.cpp:6567-6572`）。

## 実行時の詳細

`generate.cpp` のセットアップ時に即時 lambda で一度読み、`pw_with_batch` と `batch_blocks_pw` の bool に保持する。リクエストごとの再読込や、この値の static cache はないため、プロセス開始後に環境を変更してもこの判定は変わらない（`engine/src/program/generate.cpp:6555-6560`）。

優先関係は、`--batch` の有無が変数を意味のあるものにし、`--pipeline-windows` が pipeline の要求または自動選択を決める形。変数を `1` にしても pipeline は強制されず、`--pipeline-windows 0` や非対応条件を覆さない。通過した場合、コードは `--pipeline-windows` 用の二つの verifier / window 処理を残し、batch windows はその second verifier を使用しない。solo request が batch slot ではなく solo path を使う場面でもパイプラインを使える、という設計上の経路がコメントに記されている（`engine/src/program/generate.cpp:6547-6554,6602-6604,13756-13764`）。

## ログと測定値

- 明示した正の `--pipeline-windows` が batch 条件で止められた場合、stderr に `strata generate: --pipeline-windows %d is off: not with --batch slots (STRATA_PW_WITH_BATCH=1 keeps it for the solo path)` が出る（`engine/src/program/generate.cpp:6595-6601`）。
- batch 条件を通過した場合、stderr に `strata generate: --pipeline-windows %d stays on for the solo path beside %d batch slots (STRATA_PW_WITH_BATCH=1); batch windows run without it` が出る（`engine/src/program/generate.cpp:6602-6604`）。実際に pipeline が構成された経路では、後段で `strata serve: --pipeline-windows %d: two verifiers per stage, %d stages overlap across windows...` も出る（`engine/src/program/generate.cpp:13756-13760`）。
- 自動選択が条件不足で off になる場合、この変数固有の警告はない。変数の無効値によるエラー終了も実装されていない。
- `docs/DETAILS.md:1279` は「2x RTX A6000 IQ3_S」で、solo request の測定値を code +14%、file rewrite +9%、long decode +3%、同時二 request は遅くならず、second verifier が first card の約270 MiBを使うと報告している。これは資料の記載であり、本調査で再測定していない。同資料は他条件（量子化以外のモデル・OS、試行数など）を当該行に示していない。ソースコメントには別の旧測定として 2x RX 6900 XT / IQ3_S / 0.1.45 / 32K / `parallel: 2` の 75 → 66.5 tok/s があるが、これはこの opt-in がない場合の単独 request に関する比較である（`engine/src/program/generate.cpp:6553-6554`）。

## 根拠

- `engine/src/program/generate.cpp:4041-4042` — `--batch` / `--slots` の値設定。
- `engine/src/program/generate.cpp:4119` — `--pipeline-windows` の CLI 値処理。
- `engine/src/program/generate.cpp:6547-6559` — batch と solo path の関係、環境変数の読み取り、値判定。
- `engine/src/program/generate.cpp:6560-6604` — 自動選択、適用条件、fallback とログ。
- `engine/src/program/generate.cpp:13756-13764` — pipeline の実行準備ログと verifier 構成。
- `docs/DETAILS.md:1279` — 資料にある測定値。
