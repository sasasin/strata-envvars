# `HY4_VCACHE_DECAY`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4 の GPU 動的 expert cache が使う、routing score の減衰率を指定する。`Runner::vcache_init()` が `vcache_decay` に読み込み、後続の `vcache_decay_step()` が短い推論 chunk ごとの減衰量を計算する。値を小さくすると古い score がより速く減り、大きくすると長く残る。初期 slot の選択は別途 `expert_rank` 順で行われ、この変数は初期選択を変えない（`engine/src/hy4flash/run/hy4_graph.hip.h:717-779,1009-1018`）。

## 値と判定

`getenv()` が null でなければ `atof()` の結果を `[0.80, 0.999]` に clamp する。数値文字列全体の検証はなく、`atof()` が数値として読める先頭部分を変換する。空文字、数値に変換できない文字列は `0` となり、下限の `0.80` になる。小数値の通常範囲外も下限・上限に丸める（`engine/src/hy4flash/run/hy4_graph.hip.h:730`）。

| 条件 | unset | 設定時に有効になる値 | 例と判定 |
|---|---:|---|---|
| `hyb` かつ `vcache_nslots > 0`、`vcache_slot_bytes > 0` | 通常 `0.965`。`g.n_vram_experts + vcache_nslots < 3148` の場合は `0.985` | `atof(value)` を `0.80`〜`0.999` に clamp | `0.95` → `0.95`、`0.5` / `-1` / `true` / 空文字 → `0.80`、`1` / `2` → `0.999`、`0.97junk` → `0.97` |
| cache 初期化条件を満たさない | `vcache_init()` が環境変数を読む前に戻る | なし | この実行経路では未評価 |

大文字小文字の規則や空白除去は Strata 側で実装していない。変換は C `atof()` に委ねられ、値が存在するだけで空文字も設定値として扱われる。境界は両端を含み、`0.80` 未満は `0.80`、`0.999` 超は `0.999` になる。小規模 VRAM 判定による既定値 `0.985` も、環境変数が存在すればその値で置き換わる（同 `:724-731`）。

## 有効になる条件

- `strata-hy4` の CUDA または HIP ビルドで、HY4 `Runner` を初期化する経路であること。CMake では `STRATA_BUILD_HY4` が CUDA または HIP を要求し、同じ `hy4_main.hip.cpp` をその backend の言語としてビルドする（`engine/CMakeLists.txt:846-851,884-891`）。
- `Runner::init()` の時点で `g.cpu_mask` が空でなく、CPU expert の初期化が成功して `hyb = true` になること（`engine/src/hy4flash/run/hy4_graph.hip.h:1552-1583`）。通常実行と `--serve` はそれぞれ `Runner` を作成して `init()` を呼ぶ（`engine/src/hy4flash/run/hy4_main.hip.cpp:692-705`, `engine/src/hy4flash/run/hy4_serve.hip.h:307-317`）。
- GPU model 側で動的 cache slot が実際に確保され、`vcache_nslots > 0` かつ slot サイズが正であること。slot 数は model setup 時に決まり、`HY4_VCACHE_FRAC`、CPU mode、VRAM 予算、確保成功数などが関係する（`engine/src/hy4flash/run/hy4_gpu_model.hip.h:850-870,1113-1143`）。slot がない場合は `vcache_init()` が環境変数を読む前に戻る（`engine/src/hy4flash/run/hy4_graph.hip.h:721-723`）。
- `--parity-m` と `--ab` の比較経路では cache を flush してから `vcache_frozen` を設定する。また speculative verification の `--spec-check`（`cfg.check && !prob_mode`）中も一時的に freeze する。freeze 中は decay step と routing score 更新が行われない（`engine/src/hy4flash/run/hy4_main.hip.cpp:427,431,443,821-825,914-916`; `engine/src/hy4flash/run/hy4_spec.hip.h:361-371`; `engine/src/hy4flash/run/hy4_graph.hip.h:882-884,1009-1011`）。

この環境変数を上書きする CLI 引数は当該実装にない。`HY4_VCACHE_FRAC` は動的 slot 数の決定に影響する別変数であり、decay 値を指定しない。`docs/DETAILS.md:147` にある `--adapt-decay` は別の CLI オプション名で、この環境変数の読み取り箇所ではない。

## 実行時の詳細

`Runner::init()` 内で hybrid mode が有効な場合に `vcache_init()` を呼ぶ。環境変数はそこで一度読み、Runner の `vcache_decay` メンバーに保存する。したがって同じ Runner の処理中に環境変数を変更しても反映されず、新しい Runner の初期化時には再評価される（`engine/src/hy4flash/run/hy4_graph.hip.h:717-732,1704-1707`）。

初期 cache slot は rank 順の tier-2 CPU resident expert で埋める。その後、`forward_chunk()` は `T <= 8` かつ slot があるとき `vcache_decay_step(T)` を呼び、`step = pow(vcache_decay, clamp(T, 1, 4))` として inverse scale を更新する。decode 側は routing hit に重み付き score を加え、候補と slot victim の score を比較して expert を非同期に昇格させる。したがって decay は cache の適応的な入れ替え傾向を変えるが、token 選択や routing 自体を変更する設定ではない（同 `:747-779,865-898,928-987,1009-1018,3384-3389`）。

`vcache_frozen` でない場合、prefill chunk 終了時の rebalance でも蓄積 score を使う。これは同じ decay 値で更新された score に基づき、より高い score の CPU resident expert を slot に移す（同 `:803-830,3444`）。

## ログと測定値

cache 初期化が続行されると stderr に `[vcache] pre-populated %d/%d adaptive VRAM slots (%.2f GB, decay=%.3f, max_swaps=%d) in %.2f s` を出し、採用された decay 値を小数 3 桁で表示する（`engine/src/hy4flash/run/hy4_graph.hip.h:776-779`）。cache 初期化条件を満たさず早期 return した場合、このログは出ない（同 `:721-723`）。無効な文字列を理由とする専用警告や parse error はない。ソース資料にこの変数による性能測定値はない。

## 根拠

- `engine/CMakeLists.txt:846-851,884-891` — HY4 の CUDA / HIP build 条件。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:850-870,1113-1143` — 動的 cache slot の条件と確保。
- `engine/src/hy4flash/run/hy4_graph.hip.h:717-779` — hybrid 条件、既定値、環境変数の変換、初期配置とログ。
- `engine/src/hy4flash/run/hy4_graph.hip.h:803-830,865-987,1009-1018,3384-3389,3444`、`engine/src/hy4flash/run/hy4_main.hip.cpp:821-825,914-916`、`engine/src/hy4flash/run/hy4_spec.hip.h:361-371` — score 更新、昇格・victim 選択、decay の適用時期と freeze 条件。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:692-705`、`engine/src/hy4flash/run/hy4_serve.hip.h:307-317` — offline / serve からの Runner 初期化。
