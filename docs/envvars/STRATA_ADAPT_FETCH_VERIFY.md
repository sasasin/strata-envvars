# `STRATA_ADAPT_FETCH_VERIFY`

調査対象: Strata `main` の HEAD `146df3c468739147f520ac3816de806f71232571`（2026-11-07 時点）。

## 役割

`strata generate` で adaptive fetch により VRAM cache slot へ admitted した expert を、後続の decode window 前に読み戻して元データと照合する診断用フックです。生成・fetch の有効化そのものは制御しません。`STRATA_ADAPT_FETCH` が有効で fetch の実行条件を満たす場合にだけ、この変数が読み取られます。

## 値と判定

値の内容は parse されず、`std::getenv("STRATA_ADAPT_FETCH_VERIFY") != nullptr` だけで判定します。

| 設定 | 判定 |
| --- | --- |
| 未設定 | 読み戻し用ログを記録しない |
| 空文字を含む任意の設定値 | 読み戻し用ログを記録する |

`0`、`false`、数値や文字列の妥当性は区別されません。無効値時の fallback、clamp、CLI による上書きはありません。設定の有無は fetch 設定時に一度読み取られ、後から環境を変更してもその実行中の `fetch_log_on` は更新されません。

## 有効になる条件

このフックが動作するには、`STRATA_ADAPT_FETCH` の値が正として扱われ、`strata generate` の fetch 機能が開始できる必要があります。`STRATA_ADAPT_FETCH` 自体は `atoi` で読み、範囲 `[0, 2]` に clamp した値を static local に cache します（未設定時は `0`）。adaptive tier の usage table が空、device residency table がない、`--spec-split`、layer split、peer tier、helper GPU、`--pcie-mode dma` / `direct`、GPU plan または PCIe share がない、resident RAM mode などでは fetch が停止し、VERIFY の読み取り・検査も行われません。これらの場合に `STRATA_ADAPT_FETCH` が正なら stderr に `strata generate: STRATA_ADAPT_FETCH is off (...)` が出ます。

`strata serve` 側の fetch 初期化は `STRATA_ADAPT_FETCH`、`STRATA_ADAPT_FETCH_MIN`、`STRATA_ADAPT_FETCH_MARGIN` を参照しますが、`STRATA_ADAPT_FETCH_VERIFY` の読み取りはありません。この診断フックの根拠は `strata generate` の経路に限られます。

## 実行時の詳細

fetch の初期化が条件を通るとき、`generate.cpp` は VERIFY の設定有無を `drive.d.fetch_log_on` に保存します。expert pool は実際に admission した expert と slot の組だけをこのフラグが true の場合に `fetch_log` へ追加します。次の speculative decode window の前に、ログが空でなければ GPU device synchronize を呼び、各記録について、現在もその expert が同じ slot を占めている場合に限り slot の内容を読み戻して expert の blob と byte 単位で比較します。すでに evict されていた場合は比較を省略します。

不一致または slot 読み戻し失敗時は stderr に `strata: FETCH VERIFY layer ...` と検査エラーを出し、`bad` 件数を増やします。各検査後に `fetch_log` を消去し、累計 `checked` 件数の下位 10 bit が 0〜63 の範囲にあるとき `strata: fetch verify: ... admitted slots read back, ... differ` を出します。この比較結果は診断ログに反映されるだけで、VERIFY 経路自体は decode を失敗終了させません。`ExpertCache::verify_slot` は slot 範囲外、device-to-host copy エラー、byte mismatch を false として返し、mismatch では最初に異なる byte offset をエラー文字列に含めます。

## 根拠

- `src/program/generate.cpp:2005-2010` — `STRATA_ADAPT_FETCH` の `atoi`、`[0, 2]` clamp、既定値 0、static cache。
- `src/program/generate.cpp:20451-20473` — adaptive usage table、fetch を止める条件、VERIFY の presence 判定、fetch 状態ログ。
- `include/strata/core/expert_source.hpp:658-675` — fetch state と `fetch_log_on` / `fetch_log` の役割。
- `src/core/expert_source.cpp:5098-5134` — admission 時の slot 更新と、VERIFY 有効時の admission 記録。
- `src/program/generate.cpp:20976-20995` — window 前の同期、slot 検査、stderr の詳細・集計ログ。
- `src/core/expert_cache.cpp:891-917` — slot の読み戻し、比較、範囲・copy・mismatch のエラー。
- `src/program/generate.cpp:12772-12795` — serve 側の fetch 初期化に VERIFY 読み取りがないこと。
- `docs/DETAILS.md:1076` — 設計資料も VERIFY を `strata generate` の admitted slot read-back と記載。上記の比較・ログ挙動は資料の要約に頼らず実装で確認。
