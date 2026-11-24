# `FNX_ARENA`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-24 時点）。

## 役割

CUDA の all-cards split engine（`engine/src/split/src/`）で、MoE expert cache の最大 pool の slot を K/V pool が必要に応じて借りる arena を有効にする。未設定時は arena が有効で、`0` は無効、`1` は有効。arena 有効時は coldest-first に並べた expert slot を K/V page 用に貸し、使われなくなった page の slot を expert に戻す。`0` の場合はこの貸し借りを行わず、通常の K/V page pool を確保する。split launcher は専用実行設定へ `FNX_ARENA=0` を明示しているため、その経路では既定の arena は使わない（`engine/src/split/src/model.cpp:1517-1525`、`engine/src/split/src/engine.cu:319-327,390-413`、`terminal/strata_control/split_engine.py:267-284`）。

## 値と判定

`Model::choose_residency()` が `std::getenv` で値を読み、文字列全体を `strcmp` で `0` または `1` と比較する。空文字も含め、それ以外はエラー。数値変換や空白除去、大文字小文字変換はしない（`engine/src/split/src/model.cpp:1514-1525`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `FNX_27B` 以外の PLAIN load で `choose_residency()` を呼ぶ split engine | arena ON | `1`（完全一致） | `0`（完全一致）。空文字、`true`、`false`、`01`、`0anything`、前後空白付きの値は無効値として例外 |
| `FNX_27B` build、または `Model` の `PLAIN` 以外の load | 値をこの変数で判定しない | 該当なし | 該当なし |

無効値の例外は `fnx: FNX_ARENA: 0 or 1, not '<値>'`。この設定は `FNX_EXPERT_RAM_GIB` と組み合わせて検査され、arena を有効にしたまま `FNX_EXPERT_RAM_GIB=off` にすると `fnx: FNX_EXPERT_RAM_GIB=off needs FNX_ARENA=0 (the arena lends the cache's slots)` で失敗する（`engine/src/split/src/model.cpp:1520-1533`）。

## 有効になる条件

- `FNX_27B` ではないビルドで、モデルを `Load::PLAIN` として読み込む経路が値を評価する。コンストラクタはこの条件で `choose_residency()` を呼ぶ。`FNX_27B` build ではこの呼び出しがコンパイル対象外（`engine/src/split/src/model.cpp:1485-1488`）。
- `Load::ATTACH` は holder の image を復元して expert を再配置し、`choose_residency()` を呼ばずに戻る。この経路ではこの変数を読み直さない（`engine/src/split/src/model.cpp:1478-1488`）。`place_experts()` 自体は設定を再評価する（`engine/src/split/src/model.cpp:1587-1589`）。
- arena の確保・貸し出しは `m.arena` が真のときだけ行われる。利用できる GPU メモリが不足すると coldest experts を RAM に移して再配置し、8 回の再配置後も不足する場合や arena pool がない場合は例外。lane の page が収まらない場合も例外となる（`engine/src/split/src/engine.cu:326-357,360-379`）。
- `FNX_ARENA=1` でも `FNX_EXPERT_RAM_GIB=off` との組み合わせは拒否される。通常の `FNX_EXPERT_RAM_GIB` の cache 設定では expert profile を読んで coldest expert を選び、arena の slot 順にもその score が使われる（`engine/src/split/src/model.cpp:1525-1544`、`engine/src/split/src/model.cpp:333-355`）。
- split engine launcher は通常実行設定を元に専用設定を作る際、既存 `base.env` の同名値を `FNX_ARENA=0` で上書きする。fallback 用 config には元の `base.env` を保持する（`terminal/strata_control/split_engine.py:267-284`）。

## 実行時の詳細

評価は環境変数から呼び出しごとに行い、`choose_residency()` 内に static cache はない。コンストラクタの PLAIN load 時に一度読み、後続の `place_experts()` でも再度読む。したがって、これらの呼び出しより前のプロセス環境が使われる。arena の有効値は Engine 構築時に K/V pool の初期 page 数と expert pool 配置へ反映され、実行時には page 不足時に arena の上端を拡張し、不要な page の slot を返す（`engine/src/split/src/model.cpp:1485-1488,1514-1525,1587-1589`、`engine/src/split/src/engine.cu:319-327,381-413,638-668`）。

`strata_control` の split config は `base.env` を複製したうえで `FNX_ARENA` を `0` に設定して engine に渡す。分割 engine の通常 config では arena は無効となるが、保持された fallback config の環境値は元の設定である（`terminal/strata_control/split_engine.py:267-284`）。

## ログと測定値

arena 有効時は初期化時に `fnx: arena: card %d: %zu MiB free after its arena` と、全カードの pool 初期化後に `fnx: arena: the K/V pool's own %d pages (%d positions), up to %d (%d positions) by lending the slots of %s` を stderr に出す（`engine/src/split/src/engine.cu:398-410,441-452`）。実際に貸出量が変わると `fnx: arena: K/V pool %d -> %d pages (own %d, at most %d); slots lent %s (up to %.2f GiB of a card's experts in RAM), in %.1f ms` を出す（`engine/src/split/src/engine.cu:625-635`）。`FNX_ARENA=0` の場合、これら arena 固有ログは出ない。

arena pool がない、VRAM 不足を解消できない、または lane page が収まらない場合の例外文言は `engine/src/split/src/engine.cu:338-371` にある。設定値の検証エラーは上記「値と判定」の文言となる（`engine/src/split/src/model.cpp:1521-1533`）。この調査では build・実行を行っておらず、ログの実出力や性能値は測定していない。

## 根拠

- 値の取得・厳密判定・既定値および RAM cache との整合: `engine/src/split/src/model.cpp:1514-1533`
- 呼び出し条件、`FNX_27B` と load mode: `engine/src/split/src/model.cpp:1478-1488`
- expert pool 配置と profile score: `engine/src/split/src/model.cpp:333-364,1534-1551`
- arena の VRAM 判定、fallback 配置、page 設定と失敗: `engine/src/split/src/engine.cu:319-389`
- pool 確保、ログ、貸出・返却: `engine/src/split/src/engine.cu:390-452,625-668`
- launcher による値の上書きと fallback config: `terminal/strata_control/split_engine.py:267-284`
