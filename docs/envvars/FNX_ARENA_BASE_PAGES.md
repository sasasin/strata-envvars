# `FNX_ARENA_BASE_PAGES`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next split engine で expert arena を有効にしたとき、arena と同じ GPU allocation 内に置く K/V pool の初期ページ数を指定します。未指定なら GPU 空き VRAM から計算した最大ページ数を使います。指定値はページ数であり MiB ではありません。arena の有効化自体は別設定 `FNX_ARENA` が決めます。

## 値と判定

環境変数が設定されているかを `std::getenv` で確認し、設定時に共通 helper `env_int` で base-10 の整数として読みます。helper は符号 `+` / `-` と数字を受け付け、文字列全体が整数であることと `long long` の範囲内であることを要求します（`src/split/src/env.hpp:15-21,33-40`）。

| 状態・値 | 結果 |
|---|---|
| 未設定 | 自動計算した `n_pages` を維持する。 |
| 空文字 | helper の整数 parse に失敗し、`FNX_ARENA_BASE_PAGES: '' is not a whole number` の例外になる。 |
| 整数だが `want <= extra_pages` | 有効範囲外として例外。最小値は `extra_pages + 1`。 |
| 整数だが `want > n_pages` | 有効範囲外として例外。最大値はこの時点で計算済みの `n_pages`。 |
| `extra_pages < want <= n_pages` | `n_pages` を `want` に設定する。 |
| 小数、空白を含む値、数字の後ろに文字がある値、`long long` 範囲外 | helper の parse に失敗して例外。 |

`extra_pages` は `(max(lanes, 1) - 1) * lane_block_pages()` です。上限 `n_pages` は初期 context 用ページ数から始まり、各カードで `free VRAM - expert slots - reserve` に収まるページ数との最小値に絞られます。したがって許容される最大値は GPU 構成・モデル・context・lanes・残り VRAM で変わります。helper は数値の後ろを許容せず、値の clamp や fallback もしません（`src/split/src/engine.cu:70-80,283-329,331-336`）。

## 有効になる条件

- `Model::choose_residency()` が決める `m.arena` が true の場合だけ、engine constructor 内でこの変数を読みます。`FNX_ARENA` 未設定時は arena が有効、`FNX_ARENA=1` でも有効、`FNX_ARENA=0` なら無効です（`src/split/src/model.cpp:1474-1480`; 読み取り箇所 `src/split/src/engine.cu:283,331-337`）。
- `m.arena` が false の経路ではこの変数を読みません。したがって不正値でもこの変数由来の parse/range 例外は起きません。
- `strata_control/split_engine.py` の通常の split-engine 起動設定は `FNX_ARENA=0` と `FNX_EXPERT_RAM_GIB=off` を engine に渡すため、その起動経路では arena がなく、この設定は使われません（`strata_control/split_engine.py:250-264`）。split-engine を直接起動するなど、arena が有効になる実行経路では適用されます。
- ほかの環境変数や CLI 引数で `want` が上書きされる処理はありません。`FNX_ARENA_RESERVE_MIB` は別に VRAM reserve を定め、それにより `n_pages` の上限が変わります（`src/split/src/engine.cu:283-329`）。

## 実行時の詳細

値は `Engine::Engine` の初期化中、expert slots と reserve を考慮して各カードの空き VRAM を調べた後に読みます。arena が有効なら、範囲内の指定値を `n_pages` に代入し、`arena_base_` と `arena_w_` の初期値にします。後続処理は arena allocation においてこのページ数を K/V pool の初期領域として使い、ページを拡張するときは expert slots を貸し出せる上限 `arena_cap_` まで成長できます（`src/split/src/engine.cu:331-345,353-363,397-409`）。

値は Engine ごとに constructor 実行時に読み、static cache はありません。実行中に環境を書き換えた場合も、既に構築済みの Engine の `n_pages` には反映されません。例外は `fnx_run` のトップレベルで `fnx_run: <例外文>` として stderr に出され、終了コード 1 になります（`src/split/tools/fnx_run.cpp:1364-1373`）。範囲外のページ数では要求範囲と lane 用ページ数がエラー文に出ます（`src/split/src/engine.cu:333-335`）。正常時は `fnx: arena: the K/V pool's own ... pages ...` の起動ログで実際に採用したページ数を確認できます（`src/split/src/engine.cu:397-409`）。

## 根拠

- `src/split/src/env.hpp:15-21,33-40` — 整数文字列全体の parse、未設定時 default、無効値の例外。
- `src/split/src/engine.cu:70-80,283-329,331-345` — lane 用追加ページ、VRAM に基づく上限、値の範囲検証と初期ページ数への反映。
- `src/split/src/engine.cu:353-363,397-409` — arena allocation とページ数の実使用・ログ。
- `src/split/src/model.cpp:1474-1488` — `FNX_ARENA` による arena の選択。
- `strata_control/split_engine.py:250-264` — 通常の split-engine 起動時に `FNX_ARENA=0` を設定。
- `src/split/tools/fnx_run.cpp:1364-1373` — 起動時の例外表示と終了コード。
