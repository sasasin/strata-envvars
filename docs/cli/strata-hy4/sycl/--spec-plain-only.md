# `--spec-plain-only`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL） |
| オプション | `--spec-plain-only` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

DFly2 speculative decoding の経路を有効にしたまま、各生成反復で speculative draft・verify を使わず通常の1トークン `plain_step` を選びます。speculative 経路を使わない実行では、この設定は生成動作に影響しません。設定は `SpecCfg` の `plain_only` に保存され、デフォルトは `false` です（`engine/src/hy4flash/sycl/sy_main.cpp:96,185`、`engine/src/hy4flash/sycl/sy_spec.h:21-30`）。

## 使い方

```sh
# SYCL エンジンの通常実行で、DFly2 を使う生成経路を plain step に固定する
strata-hy4-sycl --model model.strata --engram engram.strata \
  --tokens prompt.ids --gen 64 --draft dfly2 --spec-plain-only

# engine line protocol の serve 起動で指定する
strata-hy4-sycl --serve --native model.strata --engram engram.strata \
  --draft dfly2 --spec-plain-only
```

単独実行では `--draft dfly2` かつ `--gen` が正の場合に `Spec::run` が呼ばれます。`--serve` では `--draft` の既定が `auto` で、モデルに DFly2 drafter があり、chunk が8以上なら speculative 経路が候補になります（`engine/src/hy4flash/sycl/sy_main.cpp:250,279,379-386`、`engine/src/hy4flash/sycl/sy_serve.h:248-255,271-307,468-479`）。

## 値と既定値

値を取らない真偽フラグです。指定すると `scfg.plain_only = true` になります。指定しない場合は `SpecCfg::plain_only` の初期値 `false` です。値の形式・範囲検証、重複指定時の特別な処理はなく、同じフラグを複数回指定しても `true` のままです（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,185`、`engine/src/hy4flash/sycl/sy_spec.h:21-30`）。

## 実行時の動作

`Spec::run` の各反復で、文脈長による draft 長の調整後に `use_plain` を判定します。`cfg.plain_only` が真なら他の判定結果にかかわらず通常経路を選び、`plain_step` を1回実行して次のトークンを出力します。draft・verify の分岐には入りません（`engine/src/hy4flash/sycl/sy_spec.h:177-200`）。

これは DFly2 の初期化自体を無効にする設定ではありません。単独実行では `--draft dfly2` のとき、生成数が0でも DFly2 を初期化します。serve でも speculative が有効なら `Spec` を作成してからリクエストを処理します（`engine/src/hy4flash/sycl/sy_main.cpp:310-317,379-386`、`engine/src/hy4flash/sycl/sy_serve.h:271-307`）。

serve では `use_spec` が真でも、生成上限が0または画像入力があるリクエストは `spec_path` を使わず通常の生成ループに進みます。このため、そのリクエストでは本フラグの効果はありません（`engine/src/hy4flash/sycl/sy_serve.h:464-479`）。serve の `--draft auto` は drafter がない場合や chunk が8未満の場合に speculative 経路を選ばず、本フラグによる plain step の指定も働きません。一方、明示的な `--draft dfly2` では drafter 不在または chunk が8未満なら serve 起動時にエラーになります（`engine/src/hy4flash/sycl/sy_serve.h:248-256`）。

## 適用条件と副作用

- フラグは DFly2 speculative decode の `SpecCfg` に渡されます。通常の単独生成など、`Spec::run` に入らないモードの挙動は変えません（`engine/src/hy4flash/sycl/sy_main.cpp:279,379-386`）。
- 単独実行で speculative 経路を使うには `--draft dfly2` と正の `--gen` が必要です。デフォルトの `draft` は `off` です（`engine/src/hy4flash/sycl/sy_main.cpp:93-104,250,279`）。
- `plain_step` の失敗は `Spec::run` の `finish == "error"` となり、単独実行では `spec: ...` を標準エラーに出して終了コード1、serve ではプロトコル出力 `ERR spec: ...` と終了コード1になります（`engine/src/hy4flash/sycl/sy_spec.h:190-192`、`engine/src/hy4flash/sycl/sy_main.cpp:388-391`、`engine/src/hy4flash/sycl/sy_serve.h:470-476`）。
- 単独実行の speculative 経路では、通常の生成結果に加えて統計を標準エラーへ報告し、`--out` で指定したディレクトリ（既定 `.`）の `gen_ids.txt` に生成 ID を書きます。これらは speculative 経路全体の処理であり、本フラグ固有の副作用ではありません（`engine/src/hy4flash/sycl/sy_main.cpp:93,392-407`、`engine/src/hy4flash/sycl/sy_spec.h:414-432`）。

## 出力とエラー

このフラグ固有の出力や検証エラーはありません。Spec 経路の plain step が失敗した場合の標準エラー・終了コード、および serve のプロトコルエラーは上記のとおりです。値を取らないため、値の不足による parser エラーもありません（`engine/src/hy4flash/sycl/sy_main.cpp:105-115,185`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:96,105-115,185` — `SpecCfg` の生成、値を消費しないフラグ parser。
- `engine/src/hy4flash/sycl/sy_spec.h:21-30,65-72` — `plain_only` の既定値と `Spec` 初期化。
- `engine/src/hy4flash/sycl/sy_spec.h:177-200` — 反復ごとの分岐と `plain_step` の実行。
- `engine/src/hy4flash/sycl/sy_main.cpp:250-253,279,310-317,379-407` — 単独実行での適用条件、初期化、エラー・出力。
- `engine/src/hy4flash/sycl/sy_serve.h:248-256,271-307,464-479` — serve の drafter 条件、Spec 作成、リクエストごとの適用条件。
