# `STRATA_RAM_ADAPT2`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の常駐 RAM expert copy に対し、会話中に利用頻度が変わった expert を RAM copy 内で入れ替える staged promotion を有効にする。候補 expert のファイル読み込みを I/O thread に先行させ、後続 decode window の境界で RAM copy に反映する。変数だけでは動かず、`STRATA_RAM_ADAPT` も正数である必要がある。GPU tier の選択規則や routing 自体はこの変数では変更しない（`engine/src/program/generate.cpp:22836-22857`）。

## 値と判定

serve 初期化時に `std::getenv` で取得し、`std::atoi(v) != 0` を `on` とする（`engine/src/program/generate.cpp:12333-12349`）。文字列全体の検証はなく、`atoi` が読む先頭の整数部分で判定する。したがって空文字・数字で始まらない文字列・`0anything` は 0 となり無効、`1`、`-1`、`2tail` は非 0 となり有効。先頭空白や符号も `atoi` の変換対象で、大文字小文字の規則はない。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| 全ビルド（serve 初期化で読み取り） | `on=false` | `atoi` の結果が非 0（例: `1`, `-1`, `2tail`） | `atoi` の結果が 0（例: 空文字, `0`, `0anything`, `true`, `false`, `x1`） |

対象変数に CLI 引数による上書きはない。`on=true` でも、`STRATA_RAM_ADAPT` の値が `atoi` で正数にならなければ staged promotion は実行されない（同 `generate.cpp:22843-22849`）。

## 有効になる条件

- `--serve` の初期化と decode window loop を通ること。この設定を読むコードは serve の初期化経路にある（`engine/src/program/generate.cpp:12302-12344`）。
- `STRATA_RAM_ADAPT` が正数であること。これが 1 window あたりに stage する promotion 数の上限にもなる（`engine/src/program/generate.cpp:22843-22849`, `22913-22918`）。
- 初回でない window で、decode usage があり、前回の adaptive swap が未完了でなく、resident RAM copy が ready であること。
- single GPU で peer tier がなく、multi-GPU でなく、remote expert optimization がなく、`--batch 0` であること。条件外ではこの staged 経路を通らない（同 `generate.cpp:22847-22849`）。
- RAM copy に入れる・出す候補 expert が存在し、評価上の gain が 1 以上であること。GPU tier に入った expert は後の install 時に除外される（同 `generate.cpp:22868-22909`; `engine/src/core/expert_source.cpp:5083-5092`）。

## 実行時の詳細

`STRATA_RAM_ADAPT2` は serve の初期化時に `RamAdapt2` へ一度読み込まれ、実行中に環境を変更しても同じ serve 実行の `on` には反映されない。関数内 static cache ではない。一方、併用必須の `STRATA_RAM_ADAPT` は decode loop 内の static local で初回評価時に cache される（`engine/src/program/generate.cpp:12333-12349`, `22843-22849`）。

`STRATA_RAM_ADAPT_PROMPT_W` が未設定なら 0.25。`on` かつこの重みが正なら prompt の routing ID を受け取る callback を設定し、各 expert に `prompt_w * 20 * n_expert_used / n` を加算した seed を記録する。prompt 経路が routing ID を host にダウンロードしない場合 callback は呼ばれない（`engine/src/program/generate.cpp:16056-16067`; `engine/src/prefill/prefill.cpp:5938-5940`; `engine/include/strata/prefill/prefill.hpp:265-267`）。

各 decode window 境界では、読み込み済み job を先に install し、prompt seed を 0.95 倍に減衰させる。その後、GPU 外の expert の `decode usage + seed` を候補順位に使い、resident RAM expert を入れ替え先に選ぶ。既定では各 layer 最大 2 組まで stage する。`STRATA_RAM_ADAPT_PER_LAYER` と `STRATA_RAM_ADAPT_SKIP_TOP` が候補数を、`STRATA_RAM_ADAPT_CACHED_W` が OS page cache にある候補の miss cost を調整する（`engine/src/program/generate.cpp:22850-22917`）。先行読み込みは `FileExpertSource::ram_stage` から I/O thread に queue され、既定 queue 上限は 64、`STRATA_RAM_ADAPT_QUEUE` で変更できる。queue が満杯・対象が重複・source が利用不可なら stage は追加されない（`engine/src/core/expert_source.cpp:5007-5031`）。次の window 境界で読み込み済みデータを install し、読み込み失敗、RAM copy 側の install 不可、または候補のどちらかを GPU tier が取得済みなら install を skip する（同 `expert_source.cpp:5041-5093`）。

## ログと測定値

serve の request 終了時、`on=true` なら stderr に累積値を出す。実装上の文言は `strata serve: resident RAM (STRATA_RAM_ADAPT2): %lld promotions read on the I/O thread, %lld installed, %lld skipped at the install (%lld of them: the GPU tier took one of the pair)`。この行は有効値だけで出て、条件不足や実際の promotion 数が 0 でも表示される（`engine/src/program/generate.cpp:23801-23805`）。個々の queue 拒否・読み込み失敗をこの機能専用に通知するログは確認できない。

## 根拠

- `engine/src/program/generate.cpp:12333-12349` — 対象変数の唯一の読み取りと parse、関連重みの初期値。
- `engine/src/program/generate.cpp:16056-16067` — prompt routing seed の記録。
- `engine/src/program/generate.cpp:22836-22919` — `STRATA_RAM_ADAPT` との依存、実行条件、候補選択と stage。
- `engine/src/core/expert_source.cpp:5007-5093` — I/O thread queue、読み込み、install と skip。
- `engine/src/program/generate.cpp:23801-23805` — serve の累積ログ。
