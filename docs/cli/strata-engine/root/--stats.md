# `--stats`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジンの引数） |
| オプション | `--stats` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

通常の `strata` 生成実行が完了したとき、標準出力に token あたりの時間内訳や CPU expert pool、PLE、expert cache などの実行統計を追加します。help の説明は「per-stage breakdown」ですが、実際の出力はステージ別時間だけでなく複数の計数・条件付き統計も含みます。`--stats` 自体が生成方式や設定値を切り替える処理は確認できず、出力ブロックを有効にするフラグです。

## 使い方

```sh
strata generate --pack ./pack --tokens "1,2,3" --stats
```

`--pack` と `--tokens` は例示用の入力です。usage はこの形式を示し、`--tokens` がない場合は tokenizer がない旨を出して status 2 で終了します（`engine/src/program/generate.cpp:1210-1214, 5002-5006`）。

## 値と既定値

- 値・別名はありません。`Options::stats` の初期値は `false` で、parser は引数が正確に `--stats` のとき `true` にします（`engine/src/program/generate.cpp:951, 4259`）。SYCL 版も同じ既定値・解析です（`engine/sycl/src/program/generate.cpp:617, 2205`）。
- `--stats` を省略すると、終端の追加統計ブロックを出力しません。複数回指定した場合も bool を `true` にするだけで、追加の効果はありません。
- 数値などを後置する構文はありません。`--stats=1` など別表記はこの分岐に一致せず、unknown argument として usage を伴って拒否されます（`engine/src/program/generate.cpp:4259, 4268-4275`）。

## 実行時の動作

通常生成の最終レポートで `o.stats` が真の場合、`printf` により標準出力へ統計を追加します。wall-clock の decode ms/token、PLE・embedding・各 layer・head・readback・sampling の時間内訳、PLE I/O 報告（存在時）、CPU expert pool とその phase、読み込んだ expert blob 数などを出します。remote expert cache、expert-cache hit、elastic K/V、token graph、captured graph などの項目は、それぞれの機能が有効または計数が存在するときだけ追加されます（`engine/src/program/generate.cpp:25462-25528`）。

phase 時間は生成ループ内で各区間を計測し、処理した位置数で割って表示します。位置数が正の場合に限り phase 内訳が出ます（`engine/src/program/generate.cpp:11088-11093, 13465-13489, 13539-13543, 13620-13629, 13680-13690, 25468-25475`）。したがって、最初の wall-clock decode 値は生成 token の平均である一方、各 phase の平均には prompt 処理位置も含みます。コメントでも prefill 分を含めて位置数を分母にする設計を説明しています（同 `generate.cpp:25477-25485`）。

標準 CUDA/HIP 系の parser と SYCL 系 parser の双方に同じフラグと出力ブロックがあります。SYCL 版の登録は `engine/sycl/src/program/generate.cpp:617, 952, 2205`、出力は `14446-14469` にあります。索引が示す主 parser（`engine/src/program/generate.cpp`）の実装と比べ、確認した統計項目と分岐は一致しています。

## 適用条件と副作用

- 値の validation、backend・model 条件による `--stats` 自体の拒否、設定ファイルや環境変数との優先順位はありません。フラグが使われる箇所は終了時の `if (o.stats)` 出力ブロックです（`engine/src/program/generate.cpp:25462`）。
- この文書の確認範囲では追加のファイル書き込みや外部プロセス起動はありません。出力先は標準出力です。計測用 accumulator は生成ループで更新され、フラグによって抑止される処理ではありません（`engine/src/program/generate.cpp:11092-11093, 13465-13489, 13539-13543, 13620-13629, 13680-13690`）。
- serve の各 request ごとにこの表を出す動作は確認できません。`o.stats` の利用箇所は通常生成の終端レポートに限られ、serve 用の request protocol の出力とは別です（同 `generate.cpp:25462-25528`）。

## 出力とエラー

統計本体は `printf` による標準出力です。`--stats` 専用のエラー経路は見つかりませんでした。未知の引数として拒否される場合は、`unknown argument: ...` を標準エラーに出し、usage を表示して status 2 を返します（`engine/src/program/generate.cpp:4268-4275`）。

## 根拠

- `engine/src/program/generate.cpp:951, 1395, 4259` — 標準 parser 系の bool 初期値、help 表示、フラグ登録。
- `engine/src/program/generate.cpp:4268-4275` — 未知引数のエラー、usage、status 2。
- `engine/src/program/generate.cpp:11088-11093, 13465-13489, 13539-13543, 13620-13629, 13680-13690` — phase timer の定義・更新。
- `engine/src/program/generate.cpp:25462-25528` — 標準出力の統計と条件付き項目。
- `engine/sycl/src/program/generate.cpp:617, 952, 2205, 14446-14469` — SYCL parser/help と対応する統計出力。
- `engine/src/program/generate.cpp:1210-1214, 5002-5006` — usage の入力形式と `--tokens` 必須条件。
