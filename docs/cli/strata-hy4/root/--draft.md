# `strata-hy4 --draft`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（CUDA/HIP backend） |
| オプション | `--draft` |
| 別名 | なし |
| 値 | `off`、`dfly2`、`auto`（`--serve` 時に検証）。値は次の argv 要素を文字列で受け取る |

## 役割

`--draft` は Hy4-Flash の DFly2 speculative decoding を無効化するか、明示的に要求するか、自動判定に任せるかを選びます。`strata-hy4 --serve` では `auto` が既定で、モデルに DFly2 tensor があり、実行条件を満たす場合に drafter を利用します。オフラインの `--tokens` 実行では既定値が `auto` でも speculative decode は有効にならず、`dfly2` を指定した場合に生成ステップがあると speculative decode 経路へ入ります（parser と既定値: `engine/src/hy4flash/run/hy4_main.hip.cpp:363-406`、serve への設定転送: 同 `:544-570`、実行経路: 同 `:648-653`、`:700-716`）。

## 使い方

```sh
# serve で既定の自動選択を使う（--draft auto と同じ）
strata-hy4 --serve --native model.strata

# serve で DFly2 を明示要求する
strata-hy4 --serve --native model.strata --draft dfly2

# serve で DFly2 を使わない
strata-hy4 --serve --native model.strata --draft off

# オフライン生成で speculative decode を明示的に要求する
strata-hy4 --model model.strata --tokens ids.txt --gen 32 --draft dfly2
```

## 値と既定値

`draft` 文字列は `auto` で初期化されます。コマンドラインで複数回指定した場合は、引数走査中に同じ変数へ代入されるため最後の指定が残ります（`engine/src/hy4flash/run/hy4_main.hip.cpp:363-406`）。値なしの場合は parser の `nxt()` が `ERR --draft needs a value` を stdout に出して終了コード 2 で終了します（同 `:375-383`）。

`--serve` では `off`、`dfly2`、`auto` 以外の値を拒否し、`ERR --draft <値>: expected off, dfly2 or auto` を stdout に出して終了コード 2 で終了します（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-554`）。

オフライン経路では値の検証がありません。`dfly2` との完全一致だけが speculative decode を選択し、`off` 以外の値はメモリ計画上 drafter 有効として扱われますが、`dfly2` と一致しなければ通常の decode になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-653`、`:700-712`）。したがって `auto` はオフラインでは実質的に通常 decode です。無効値や空文字も拒否されず、`off` でも `dfly2` でもない値として処理されます。

## 実行時の動作

serve 経路は値を `ServeOpts::draft` に渡します（`engine/src/hy4flash/run/hy4_main.hip.cpp:555-570`）。`off` 以外ならメモリ計画と `GpuModel::draft_enabled` で drafter 有効として扱います（`engine/src/hy4flash/run/hy4_serve.hip.h:268-292`）。serve の chunk が 8 未満なら drafter を使いません。`dfly2` を明示していた場合に限り、その理由を stderr に `[dfly2] chunk ... < 8; starting without drafter` と出します（同 `:319-326`）。

chunk が 8 以上なら DFly2 初期化を試みます。必要な tensor がモデルにない、または初期化に必要な空き VRAM が足りない場合など `df.init` が失敗すると、`auto` と `dfly2` のどちらでも stderr に利用不可の理由を出し、drafter なしで継続します。初期化成功時は `use_spec` と `r.det_mix` を有効にし、開始時の `INFO` 行では `drafter=dfly2` と報告します（`engine/src/hy4flash/run/hy4_serve.hip.h:319-338`、`:369-371`）。DFly2 初期化側では、モデル manifest に drafter tensor がない場合と空き VRAM が 192 MiB 未満の場合を失敗理由にします（`engine/src/hy4flash/run/hy4_dfly2.hip.h:470-484`）。

オフライン経路では、`--draft dfly2` かつ `--gen` が正数で、`--dfly-alloc-only` が指定されていない場合に speculative decode を実行します。`dfly2` を指定すると `--gen` が 0 の場合でも DFly2 初期化を試みます。モデルに DFly2 tensor がない、または DFly2 初期化が失敗した場合は stderr に `dfly2: <理由>` を出して終了コード 1 になります（`engine/src/hy4flash/run/hy4_main.hip.cpp:700-716`、初期化失敗条件: `engine/src/hy4flash/run/hy4_dfly2.hip.h:470-484`）。`auto` および `off` ではこの初期化・speculative decode 経路に入りません。

## 適用条件と副作用

索引上のこの文書は `strata-hy4` の CUDA/HIP root parser に対するものです。Metal と SYCL には別 parser・別 scope があります（`docs/cli/README.md:1277-1294`、`:1350-1374`、`:1452`）。ここで説明した詳細は CUDA/HIP 実装に限ります。

`--serve` で自動選択が drafter の利用に至る条件は、`off` 以外であること、planned chunk が 8 以上であること、DFly2 初期化が成功することです。`dfly2` という指定自体は serve 起動失敗を強制せず、条件を満たさなければ drafter なしで続行します。オフラインでは、`--draft dfly2` のみが speculative decode 指定となり、さらに `--gen > 0` と `--dfly-alloc-only` 未指定が必要です。

`off` 以外はメモリ計画に drafter 有効のフラグを渡すため、`auto` でも serve とオフラインで計画 chunk に影響し得ます（`engine/src/hy4flash/run/hy4_main.hip.cpp:648-653`、serve 側: `engine/src/hy4flash/run/hy4_serve.hip.h:268-292`）。その他の資源使用量や値ごとの chunk 差は、この調査では実測していません。

## 出力とエラー

- 値がない場合: stdout に `ERR --draft needs a value`、終了コード 2（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-383`）。
- serve の値が不正な場合: stdout に期待値を示す `ERR` 行、終了コード 2（同 `:550-554`）。
- serve の明示 `dfly2` で chunk が 8 未満の場合: stderr に通知し、serve 自体は drafter なしで開始（`engine/src/hy4flash/run/hy4_serve.hip.h:321-326`）。
- serve で DFly2 初期化に失敗した場合: stderr に理由を出し、drafter なしで続行（同 `:327-338`）。
- オフラインで `dfly2` の初期化に失敗した場合: stderr に `dfly2: <理由>`、終了コード 1（`engine/src/hy4flash/run/hy4_main.hip.cpp:712-716`）。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:363-406` — 既定値と parser。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-570` — serve 時の値 validation と `ServeOpts` への転送。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:648-716` — オフラインのメモリ計画、speculative decode 条件、DFly2 初期化と失敗処理。
- `engine/src/hy4flash/run/hy4_serve.hip.h:268-338`、`:369-371` — serve のメモリ計画、DFly2 自動利用・fallback、状態出力。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:470-484` — DFly2 tensor と空き VRAM による初期化失敗。
- `docs/cli/README.md:1277-1294`、`:1350-1374`、`:1452` — `strata-hy4` backend と option scope の区別。
