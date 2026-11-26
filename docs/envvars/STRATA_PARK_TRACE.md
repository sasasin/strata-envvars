# `STRATA_PARK_TRACE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

会話状態を park（会話キャッシュへ退避）するときの処理時間、join 待ち、K/V バッファのページフォルト数・配置などを `stderr` に出す診断フラグ。診断用の計測と出力を加えるもので、park のコピー方式や生成結果を選ぶ制御ではない。park の保存処理は `generate.cpp` の `park_source` から `conversation_snapshot_save`、`conversation_kv_save` へ進む。通常の会話キャッシュが無効、または保存対象の live 会話が空なら、park 内部の計測ログは発生しない（`engine/src/program/generate.cpp:14467-14479,14519-14525`）。

この名前は候補一覧に加え `docs/SETTINGS.md` と `docs/DETAILS.md` にも記載されている。実装では `std::getenv("STRATA_PARK_TRACE")` を実際に呼び、診断の分岐に使っている（`engine/src/core/conversation_state.cpp:301-302,310,569,654-674`; `engine/src/core/conversation_snapshot.cpp:151,259-261`; `engine/src/program/generate.cpp:13945-13957,14507-14510`）。

## 値と判定

すべて設定有無の判定で、値のパースはしない。`getenv` が非 null なら有効であり、値が空文字でも有効。未設定だけが無効。`0`、`false`、`0anything` も文字列内容を検査しないため有効で、大小文字・空白・数値としての妥当性も関係しない。有効な値の数値境界はない（`engine/src/core/conversation_state.cpp:301,310,569`; `engine/src/core/conversation_snapshot.cpp:151,259-261`; `engine/src/program/generate.cpp:13945,13949,13955,14507`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| すべての読み取り箇所 | 診断分岐は false | 空文字、`0`、`1`、`true`、`0anything` | なし（設定済みの文字列は内容によらず true） |

## 有効になる条件

- 診断フラグ自体は OS、backend、モデル状態、CLI 値を調べず、環境変数の存在だけで有効になる。
- park の内部詳細ログには、会話キャッシュを使う serve 経路で保存処理が実行されることが必要。`park_current_body` は cache が無効、live state が不正、または live 会話が空なら早期に戻る（`engine/src/program/generate.cpp:14519-14525`）。batch slot の上書き前にも `park_source` を通る別経路がある（`engine/src/program/generate.cpp:17075-17102`）。
- segment pool の予約・常駐ログは pool が作られる条件に従う。予約ログは `want_mib > 0` かつ会話キャッシュ有効時の初期化で出て、常駐量ログは `segpool != nullptr` の park 後に出る（`engine/src/program/generate.cpp:13923-13929,13945-13950,14505-14510`）。
- K/V VRAM slot の追加ログは `STRATA_PARK_VRAM_MIB` の予算が 0 でない場合に限る。slot を取得できたか、理由付きで取得できなかったかを出す（`engine/src/core/conversation_snapshot.cpp:143-149,1091-1099`）。`STRATA_PARK_TRACE` は `STRATA_PARK_ASYNC` を有効化しない。非同期 park が無効または必要サイズが 0 なら `conversation_park_async_begin` は false を返す（`engine/src/core/conversation_snapshot.cpp:237-243,1077-1088`）。
- `conversation_trace` のページフォルト、THP、heap/map 補助値は Linux 以外では 0、`?` 等の sentinel になる。park のタイマーや stderr 出力の分岐自体はこの OS 条件に依存しない（`engine/src/core/conversation_trace.hpp:11-24,27-40,43-66,76-83`）。

## 実行時の詳細

一部は関数内 `static const bool` に初回評価結果を保存する。`checkpoint_save`、`conversation_snapshot_save`、`park_trace`、`park_trace_on` がそれぞれ最初に呼ばれた時点で設定有無を読み、そのプロセス中はキャッシュされた値を使う（`engine/src/core/conversation_state.cpp:296-310,563-570`; `engine/src/core/conversation_snapshot.cpp:151,259-262`）。これらの static は翻訳単位・関数ごとに別々である。一方、`checkpoint_save` の join ログ、serve 初期化時の pool ログ、park 後の segpool ログは各箇所で都度 `getenv` を呼ぶ（`engine/src/core/conversation_state.cpp:299-302`; `engine/src/program/generate.cpp:13945-13957,14505-14510`）。したがって後者は環境がプロセス内で変更されれば次の該当箇所で反映されるが、static に保存済みの診断分岐は変わらない。

snapshot save は前回の checkpoint と park の非同期コピーを join した時間、同期、checkpoint 複製、live state 保存、K/V 保存の合計と層別時間を計り、必要に応じて minor faults や各バッファのサイズも出す（`engine/src/core/conversation_state.cpp:573-597,639-674`）。K/V 保存側では pointer 属性判定・resize・copy の時間を集計する（`engine/src/core/conversation_snapshot.cpp:451-457,498-525,528-534,1070-1075`）。この環境変数自体による timeout、終了、失敗処理はない。park の保存失敗や `bad_alloc` の扱いは通常の処理経路で行われ、診断フラグがそれを切り替えるコードはない（`engine/src/program/generate.cpp:14467-14472,14512-14517`）。

## ログと測定値

有効時の主な `stderr` 文言は次のとおり。park 実行時にはさらに `strata parktrace: ckpt copy ...`、`strata parktrace: K/V layer 0 buffers ...` 等が条件に応じて出る（`engine/src/core/conversation_state.cpp:301-302,316-318,593-596,654-674`）。

- `strata parktrace: save join %.2f ms`
- `strata parktrace: joins ... sync ... checkpoints copied ... live state ... begin ... K/V ...`
- `strata parktrace: faults: checkpoint copies ..., K/V resize ...`
- `strata parktrace: THP enabled ...; defrag ...; page size ...; sbrk end ...`
- `strata parktrace: segpool ...` / `strata parktrace: park pools: ...`
- VRAM slot 予算がある場合: `strata parktrace: kv slot ...` または `strata parktrace: kv slot: none (...)`、restore 時に `strata parktrace: kv restore: ...`（`engine/src/core/conversation_snapshot.cpp:1094-1099,1244-1249`）。

`docs/DETAILS.md` は「the park's joins and timers on stderr」と記載しており、現行実装の追加詳細ログと整合する。掲載測定値はなく、ここでも性能値は示さない（`docs/DETAILS.md:1797-1798`）。

## 根拠

- 候補名と実装での直接読み取り: `engine/src/core/conversation_state.cpp:301-302,310,569`; `engine/src/core/conversation_snapshot.cpp:151,259-261`; `engine/src/program/generate.cpp:13945-13957,14507-14510`。
- park 経路・適用条件: `engine/src/program/generate.cpp:14467-14479,14519-14525,17075-17102`。
- 計測値・ログと OS 補助関数: `engine/src/core/conversation_state.cpp:639-674`; `engine/src/core/conversation_snapshot.cpp:451-457,498-534,1070-1075`; `engine/src/core/conversation_trace.hpp:11-83`。
