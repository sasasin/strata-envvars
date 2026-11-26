# `--pool-cores`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数） |
| オプション | `--pool-cores` |
| 別名 | なし |
| 値 | 論理プロセッサ番号のリスト。番号、昇順範囲、任意の正の step を指定できる |

## 役割

CPU expert pool の worker を割り当てる論理プロセッサと順序を指定する、実験的で既定では無効の設定です。指定がなければ従来の配置計画が使われます。worker thread の pinning にだけ作用し、推論結果を変更する設定ではありません。parser は共通エンジンと SYCL エンジンにあり、どちらも pool を作る前に値を設定します（`engine/src/program/generate.cpp:3955,4703-4713`、`engine/sycl/src/program/generate.cpp:1976,2238-2248`）。

## 使い方

```sh
# 論理 CPU 2, 4, 6, 8 の順に pool worker を配置
strata --pack MODEL --pool-cores 2,4,6,8

# 2 から 14 まで 2 つおきの論理 CPU を指定
strata --pack MODEL --pool-cores 2-14:2
```

`--pack` はエンジンのモデル入力例です。実行ファイル名や起動方法は配布形態により異なります。

## 値と既定値

- 値はカンマ区切りの非負整数、`first-last` 範囲、または `first-last:step` 範囲の組み合わせです。例: `0,2,4,6`、`2-14:2`。範囲は昇順で、step は正数である必要があります。前後や区切り周辺の空白は読み飛ばされます（`engine/include/strata/kernels/cpu/pool_plan.hpp:180-224`）。
- 重複番号は最初の出現だけ保持されます。展開後の重複除去済みリストは最大 4096 件で、数値は 100000 を超えると拒否されます（同 `:188-217`）。
- 既定は空リストで、標準の pool 配置を維持します。CLI 値が空の場合に限り `STRATA_POOL_CORES` が代わりに参照されます（`engine/src/program/generate.cpp:4705-4712`、SYCL は `engine/sycl/src/program/generate.cpp:2240-2247`）。
- `--pool-cores` を複数回指定すると parser の文字列代入により最後の値が使われます（`engine/src/program/generate.cpp:3955`、`engine/sycl/src/program/generate.cpp:1976`）。値を省略すると共通 parser の `next` が stderr に不足を出して終了コード 2 で終了します（`engine/src/program/generate.cpp:3842-3847`）。

## 実行時の動作

エンジンは値を `parse_pool_cores` で番号列に変換し、成功時に pool の配置設定へ保存します。形式不正・空の値は stderr に理由を出して無視し、既定配置で続行します（`engine/src/program/generate.cpp:4703-4713`、SYCL は `engine/sycl/src/program/generate.cpp:2238-2248`）。

pool 構築時、実在しプロセスが使用可能な論理 CPU だけが配置候補として残ります。使えない番号は警告付きで除外されます。SMT sibling を同じ core から複数選んだ場合や host thread の CPU（または同じ core）を選んだ場合は警告しますが、指定どおり保持します。順序は NUMA interleave による並べ替えより優先されます（`engine/include/strata/kernels/cpu/pool_plan.hpp:227-275`、`engine/src/kernels/cpu/pool.cpp:823-845`）。

有効な CPU が一つも残らない場合は警告して既定配置へ戻ります。通常は指定リストの長さが worker 数になります。`--pool-workers N` を併用すると件数はそちらが優先され、N がリストより大きい場合、余った worker は pin されず OS の配置に任されます（`engine/src/kernels/cpu/pool.cpp:831-839,865-881,1006-1013`）。`--no-pool` が有効な経路では CPU expert pool 自体の利用が抑止され、この配置指定の実用上の効果もありません（`engine/src/program/generate.cpp:846,10467-10484`）。

## 適用条件と副作用

設定は起動時、pool 構築前に読み取られます。稼働中の pool を動的に再配置する経路は確認できません（`engine/src/program/generate.cpp:4703-4713`、`engine/src/kernels/cpu/pool.cpp:823-839,991-1002`）。副作用は worker thread の論理 CPU pinning と、配置に関する stderr 起動メッセージです。性能向上は保証されず、ソースも性能値を規定していません。

## 出力とエラー

- 値がない場合は parser が `--pool-cores needs a value` を stderr に出し、終了コード 2 で終了します（`engine/src/program/generate.cpp:3844-3846`）。
- リストの構文エラーは stderr に `strata generate: --pool-cores: ...; the pool uses its default placement` と出力して続行します（`engine/src/program/generate.cpp:4708-4712`）。SYCL も同様です（`engine/sycl/src/program/generate.cpp:2243-2247`）。
- 使用不能な CPU、同一 core の複数指定、host thread との競合、および利用可能な CPU がゼロの場合は pool 構築時に stderr へ警告します（`engine/src/kernels/cpu/pool.cpp:825-834`、詳細判定は `engine/include/strata/kernels/cpu/pool_plan.hpp:245-275`）。

## 根拠

- `engine/src/program/generate.cpp:1436-1462` — help の値形式、実験的・既定 off、worker 数、警告と環境変数の説明。
- `engine/src/program/generate.cpp:3842-3847,3955,4703-4713` — 引数値の取得、代入、環境変数 fallback、parse と失敗時の続行。
- `engine/sycl/src/program/generate.cpp:1009-1011,1976,2238-2248` — SYCL 側の help、parser、適用。
- `engine/include/strata/kernels/cpu/pool_plan.hpp:180-224,227-275` — 文法、重複排除、上限、不正値判定、および配置候補と警告の判定。
- `engine/src/kernels/cpu/pool.cpp:823-845,865-881,991-1013` — pool への反映、worker 数の選択、指定順 pinning と余剰 worker の扱い。
- `engine/src/program/generate.cpp:846,10467-10484` — `--no-pool` による pool 利用抑止。
- 索引のスコープ確認: `docs/cli/README.md:1036-1041,1175-1178` — `strata-engine` の `strata`（エンジン引数）節に本オプションが登録されている。
