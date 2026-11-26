# `STRATA_ADAPT_EVICT_SYNC`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

adaptive tier が swap した expert の residency table を、コピー完了を待たずに次の verify window の前に GPU 側へ反映する経路を制御する。既定では有効で、`0` にするとこの早期反映を止める。適用経路は `strata serve` と `strata generate` の GPU decode で、expert cache の residency table と適応 swap がある場合に限られる。フラグ自体は swap 選択やコピーの実行を有効化せず、adaptive tier の設定は別途必要である（`engine/src/program/generate.cpp:2350-2354,15249-15257,24615-24619`）。

## 値と判定

`adapt_evict_sync()` は `std::getenv` の結果を関数内 `static const bool` に一度だけ保存する。未設定なら `true`、設定済みなら `std::atoi(e) != 0` が判定となる。文字列全体の妥当性検査や範囲制限はない。したがって空文字、`0`、`0anything`、`false`、`true`、数値に変換できない文字列は `atoi` が 0 を返すため無効。`1`、`-1`、`2tail` のように先頭の数値部分が非 0 なら有効。先頭空白は `atoi` が読み飛ばし、`+0` は無効、`+1` は有効となる。数値範囲外の文字列については `atoi` の変換結果をコードが検査していない（`engine/src/program/generate.cpp:2351-2354`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 全呼び出し経路 | 有効（`true`） | `1`, `-1`, `2tail` | 空文字, `0`, `0anything`, `true`, `false`, `abc` |

## 有効になる条件

- `strata serve`: adaptive tier の usage 情報があり、`STRATA_ADAPT_NOWAIT=1` または `STRATA_ADAPT_LAG` の変換値が 1 より大きく、かつ通常の serial-window 経路（`!pipe && !piped_groups`）であること。`piped_groups` 経路では `evict_sync` による table patch は設定せず、この変数が有効なら verifier に全 activation を publish させる（`engine/src/program/generate.cpp:15249-15257`）。
- `strata generate`: GPU residency table `d_res` があり、adaptive tier の usage 情報があり、同じ `NOWAIT` / `LAG` 条件を満たすこと（`engine/src/program/generate.cpp:24615-24619`）。
- どちらの経路も `STRATA_ADAPT_FETCH` による admission が有効なら、`fetch_admit > 0` が `adapt_evict_sync()` の false を補い、`evict_sync` を有効にする。つまり `STRATA_ADAPT_EVICT_SYNC=0` でもこの場合は admission に必要な table 更新処理が残る（serve: `engine/src/program/generate.cpp:15252`; generate: `engine/src/program/generate.cpp:24615-24616`）。
- `NOWAIT` / `LAG` が遅延を作らない、adaptive tier がない、または residency table がない場合、この変数単独では同期処理を発生させない。`STRATA_ADAPT_NOWAIT` と `STRATA_ADAPT_LAG` は関数内 static cache で読み、既定はそれぞれ false と 1（`engine/src/program/generate.cpp:2237-2250`）。
- この変数を読む箇所に OS 分岐はない。実処理は `generate.cpp` の GPU verifier/residency table 経路で行われる。

## 実行時の詳細

最初に `adapt_evict_sync()` が呼ばれた時点で環境値を読み、その後は同一プロセス内で値を再読しない。serve/generate は `drive.d.evict_sync` を上記条件で決める。adaptive round で swap が始まると、evicted expert を host table で non-resident にし、`evict_sync` が有効なら変更 index を dirty として記録する。serial-window の verifier pre-launch hook は次の window の前に dirty entry を device residency table に patch し、件数が patch 上限を超える場合は table 全体を upload する。こうしてコピーが完了するまでの間も、device table が evicted expert を resident と扱わない。コピー完了後は incoming expert の residency も反映し、dirty 状態を解消する（serve: `engine/src/program/generate.cpp:15217-15234,15272-15295,15468-15488`; generate: `engine/src/program/generate.cpp:24630-24647,24670-24699,24784-24791`）。

この経路はコピー完了待ちを追加する設定ではない。`evict_sync` が無効で fetch admission もなければ、swap の copies が完了して `apply_pending` が table を upload した後に residency table が更新される（serve: `engine/src/program/generate.cpp:15217-15234`; generate: `engine/src/program/generate.cpp:24670-24699`）。serve の `--pipeline-windows` 等では別の publish/fence 経路が使われ、serial-window 用 patch hook の適用外となる（`engine/src/program/generate.cpp:15236-15257`）。

## ログと測定値

serve の serial-window 経路で `drive.d.evict_sync` と変数の判定がともに有効なとき、stderr に次の行を出す。`STRATA_ADAPT_FETCH` が false を補う場合や、generate 経路ではこの行は出ない（`engine/src/program/generate.cpp:15330-15335`）。

```text
strata serve: the adaptive tier's evictions reach the device's table before the next window (STRATA_ADAPT_EVICT_SYNC=0: when its copies land)
```

`docs/DETAILS.md` の opt-in switch 表にはこの変数固有の測定値や挙動の記載はない（`docs/DETAILS.md:1252-1262`）。ここでは性能値を記載しない。

## 根拠

- `engine/src/program/generate.cpp:2350-2354` — 変数の唯一の読み取り箇所、判定と static cache。
- `engine/src/program/generate.cpp:15236-15257,15330-15335` — serve の適用条件、piped groups の代替処理、ログ。
- `engine/src/program/generate.cpp:15217-15234,15272-15295,15468-15488` — serve の swap と residency table 更新。
- `engine/src/program/generate.cpp:2237-2250,24615-24619,24630-24655,24670-24699,24784-24791` — 関連する `NOWAIT` / `LAG` の判定と generate 経路。
- `engine/include/strata/core/expert_source.hpp:662-669` — `ExpertDispatch::evict_sync` と residency table の役割の説明。
