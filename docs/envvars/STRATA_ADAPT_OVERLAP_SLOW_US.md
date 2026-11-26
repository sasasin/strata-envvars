# `STRATA_ADAPT_OVERLAP_SLOW_US`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

適応キャッシュの overlap コピーに、各レイヤーの転送前に指定マイクロ秒数の host callback を挿入するテストフックです。遅い転送リンクを模擬し、次の verify window がコピー完了を待つ状態を作ります。適応 swap の選択や値そのものは変更せず、コピーの進行を遅らせます。実装は `engine/src/program/generate.cpp` の適応コピー処理です（`engine/src/program/generate.cpp:15431-15439`）。

## 値と判定

`std::getenv` の結果を `std::atoi` で `int` に変換します。未設定なら `0`、空文字や数値として読めない先頭なら `atoi` の結果は `0` です。変換後の値が `0` 以下なら callback を挿入しません。正の値なら、その値をマイクロ秒として sleep します。文字列全体の妥当性検査や範囲制限はありません。`atoi` は数値の後ろの文字を検査しないため、`25ms` は `25`、`0anything` は `0` になります。先頭空白と符号は `atoi` の変換規則に従い、大文字小文字の判定はありません。`int` の範囲外の文字列に対する変換結果はコードで規定していません（`engine/src/program/generate.cpp:15435-15438`）。

| 条件 | 未設定 | 遅延が入る値 | 遅延が入らない値 |
| --- | --- | --- | --- |
| overlap の適応コピー経路 | `0` | `1`、`25ms`（`25` と変換） | 空文字、`0`、`0anything`、`-1`、`abc` |

## 有効になる条件

- `strata generate` の適応キャッシュで swap が発生し、`aov` が有効なコピー処理に入る必要があります。`aov` は `STRATA_ADAPT_OVERLAP` が先頭文字 `'1'` で、以下の無効化条件がない場合に有効です（`engine/src/program/generate.cpp:2269-2288, 15122-15136`）。
- overlap はレイヤー分割、`--remote-expert-opt`、`--adapt-async`、`--pipeline-windows`、ページロックされた swap source、`STRATA_DMA_BATCH`、`STRATA_ADAPT_LAG` が既定の 1 以外、`STRATA_ADAPT_NOWAIT` 有効時には動きません（`engine/src/program/generate.cpp:15122-15136`）。
- resident RAM mode では通常無効です。`STRATA_ADAPT_OVERLAP_RESIDENT` が設定され、先頭文字が `'1'` の場合に限りこの条件を通ります。また適応 tier が無効なら動きません（同上）。
- overlap gate の設定に失敗した場合や `STRATA_VERIFY_DEVICE_PLAN` が有効な場合も実行されません（`engine/src/program/generate.cpp:15137-15144`）。Windows の HIP build では `STRATA_ADAPT_OVERLAP=1` は別の安全判定を受け、拒否される場合があります（`engine/src/program/generate.cpp:2259-2285`）。
- 値の読み取りは `aov` が真で、swap のレイヤー単位のコピー処理に到達した場合だけです。従って通常の生成、overlap 無効時、swap がない間はこの変数の値は使われません（`engine/src/program/generate.cpp:15431-15438`）。

## 実行時の詳細

`slow_us` はコピー処理内の関数ローカル `static const` です。最初に overlap 中の swap がレイヤー単位のコピー箇所まで進んだときに環境を読み、以後プロセス内で cache します。実行中に環境を書き換えても反映されません。callback 用の `slow_arg` も同じ値で初期化されます（`engine/src/program/generate.cpp:15433-15439`）。

swap はレイヤー順に並べられ、各レイヤーの最初の swap の直前に、遅延値が正なら `adapt_stream` へ `cudaLaunchHostFunc` を enqueue します。同じレイヤーの後続 swap ごとには追加しません。callback は `std::this_thread::sleep_for(std::chrono::microseconds(...))` を実行し、その後にそのレイヤーのコピーが enqueue されます（`engine/src/program/generate.cpp:15380-15386, 15431-15439`）。overlap gate はコピー完了をレイヤーごとに知らせ、次の window がそのレイヤーのコピーを待てるようにします（`engine/src/program/generate.cpp:15471-15482, 15137-15143`）。

## ログと測定値

この変数専用のログはありません。overlap が有効なら起動時に `strata serve: adaptive overlap (STRATA_ADAPT_OVERLAP=0 turns it off): the adaptive tier's copies land while the next window runs (same tokens, a layer waits for its own copies)` が出ます。設定した overlap が条件不足で無効の場合は `strata serve: STRATA_ADAPT_OVERLAP=1 is off: ...` と理由が出ます（`engine/src/program/generate.cpp:15176-15186`）。

`--decode-timing` の計測行に加え、overlap が有効で window が未完了 swap に遭遇した場合は `strata decode adapt overlap: ...` が出て、layer gate の累積待ち時間を表示します（`engine/src/program/generate.cpp:23352-23384`）。このテストフック自体の測定値は記載されていません。`docs/DETAILS.md:1260` は親の `STRATA_ADAPT_OVERLAP` の条件と測定を説明していますが、この変数を使った測定値はありません。

コピー自体が失敗すると `strata serve: adaptive swap copy failed (layer %d, slot %d, pinned %d): %s` を stderr に出して適応処理が `false` を返します（`engine/src/program/generate.cpp:15458-15465`）。遅延 callback の enqueue 戻り値は検査されず、この変数に固有の enqueue 失敗ログもありません（`engine/src/program/generate.cpp:15435-15439`）。

## 根拠

- `engine/src/program/generate.cpp:15431-15439` — 変数の読み取り、`atoi`、正値のときのレイヤーごとの遅延 callback。
- `engine/src/program/generate.cpp:15122-15186` — overlap の有効条件、gate の設定、起動時ログ。
- `engine/src/program/generate.cpp:15380-15386, 15471-15482` — レイヤー順の swap とコピー完了 gate。
- `engine/src/program/generate.cpp:23352-23384` — decode timing と overlap 待ち時間の表示。
- `docs/DETAILS.md:1252-1262` — 親の overlap 機能の説明と測定値。対象変数自体の測定値ではない。
