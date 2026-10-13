# `STRATA_KV_MAIN_OFF`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

`--kv-resident N` で有効にした K/V ストリーミングのうち、通常のセッションが使うメイン層の QSA 状態をストリーミングせず、全コンテキスト分の K/V を GPU 側に保持する A/B 用スイッチ。MTP ドラフター用の ring 状態を切り替える変数ではない。

## 値と判定

| 状態 | 判定・結果 |
|---|---|
| 未設定 | `std::getenv` が `nullptr`。メイン層は通常どおりストリーミング判定へ進む。 |
| 空文字を含む任意の値で設定 | `std::getenv(...) != nullptr` なので有効。値の内容、数値変換、大文字小文字の判定はない。 |
| `--kv-resident` が未指定または `0` | `g_kv_resident <= 0` の早期 return により、この環境変数は参照されず、K/V は全て GPU 側に置かれる。 |
| `ring_cells < 0` | 「常に全て GPU 側」の早期 return により、この環境変数は参照されない。 |
| `ring_cells > 0` | ドラフター用状態として扱われ、判定には `STRATA_KV_RING_OFF` が使われる。この変数は選択されない。 |
| `ring_cells == 0`、`--kv-resident > 0`、本変数が設定済み | ストリーミング計画をやめ、全ページを GPU 側に確保する。 |
| 同上、本変数が未設定 | 常駐ページ数を `max(--kv-resident, 20480)` から算出し、コンテキスト全体より少なければストリーミングする。全ページ以下なら全て GPU 側になる。 |

`--kv-resident` の値自体は CLI から `std::atoll` で読み取られ、負値は引数検証で拒否される。本変数はその数値を上書きせず、メイン状態に対するストリーミング計画を抑止する。

## 有効になる条件

- QSA 状態の計画時に `g_kv_resident > 0` であること。通常は `--kv-resident N` に正数を指定した場合に該当する。
- 状態の `ring_cells` が `0` であること。通常セッションの状態はこの既定値を使う。正数の ring は MTP ドラフター用で、本変数でなく `STRATA_KV_RING_OFF` の判定対象になる。
- `--kv-resident` が正でも、コンテキストのページ数が算出された常駐ページ数以下なら、環境変数の有無によらずストリーミング計画にならない。
- CUDA/HIP 共通の `src` 実装と SYCL 実装に同じ判定がある。GPU 世代による追加条件はこの判定箇所にはない。

## 実行時の詳細

`kv_plan` はまず全コンテキスト分を使う計画（`mode == 0`、`slots == pages`）を作る。`g_kv_resident <= 0` または `ring_cells < 0` ならそのまま返る。その他の場合に、ローカル static として `STRATA_KV_RING_OFF` と `STRATA_KV_MAIN_OFF` の設定有無を一度だけ読み、`ring_cells == 0` なら本変数が設定されていないときだけメイン層のストリーミング計画（`mode == 1`）へ進む。

通常セッションの `session_bytes` / `session_init` は同じ計画から領域サイズと QSA 状態を作る。全ページを使う場合、ページテーブルは恒等写像になり、ホスト K/V コピーと streaming map は作られない。ストリーミングする場合は全 K/V の pinned host copy と常駐ページ用の map を作り、割当てに失敗すると初期化が失敗し、CUDA/HIP 経路では pinned RAM 不足の診断を stderr に出す。したがって本変数を有効にしたメイン状態は、K/V の GPU メモリ使用量がコンテキスト全体分に戻る。

環境変数の設定値は直接はログに出ない。ローカル static にキャッシュされるため、プロセス起動時から値を変えず、最初に条件を満たして `kv_plan` が呼ばれる時点の設定が使われる。それ以降の環境変更は反映されない。`g_kv_resident <= 0` の間に呼ばれた場合は読み取り自体が起きず、後で正数へ変更されてから最初に条件を満たした呼び出しで読み取られる。

MTP のドラフターは `ring_cells` を正数で初期化し、pinned RAM 確保に失敗すると `-1` で全常駐へ再試行する。どちらも本変数によるメイン層の切替とは独立している。

## 根拠

- `src/core/layer.cpp:634-651` — `kv_plan` の初期計画、早期 return、環境変数の設定有無判定、常駐ページ数。
- `sycl/src/core/layer.cpp:724-741` — SYCL 側の同等実装。
- `src/core/session.cpp:55-73, 76-119` — セッション領域の計算と QSA 状態初期化。状態計画は `qsa_state_bytes` と `qsa_state_init` で使われる。
- `src/core/layer.cpp:670-683, 689-705, 768-813, 848-860` — 計画が領域サイズ、stream map / host copy の有無、ページテーブルの設定に反映される箇所。
- `src/program/generate.cpp:394, 708-710, 1855-1857, 2462-2466` — `--kv-resident` の既定値・説明・CLI parse・負値検証・グローバル設定。
- `src/core/mtp.cpp:325-349` — ドラフター ring の計算と、pinned RAM 確保失敗時の `ring = -1` 再試行。
- `docs/DETAILS.md:80-84, 91-95` — `--kv-resident` による K/V ストリーミングの一般説明。`STRATA_KV_MAIN_OFF` 固有の説明はなく、環境変数の細部は上記実装に基づく。

