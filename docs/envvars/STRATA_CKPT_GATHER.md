# `STRATA_CKPT_GATHER`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

CUDA の conversation checkpoint 保存時に、PLE 履歴と各 QSA layer の indexer tail・dead row・block position を一つの device staging buffer に集め、まとめて host へコピーします。checkpoint の GDN state 本体はこの gather の対象外で、別のコピー経路です。変わるのは小さい running-state vector 群のコピー方法で、保存される vector の内容は同じです。

## 値と判定

環境変数の文字列を数値や真偽値として parse せず、最初の文字だけを検査します。

| ビルド条件 | unset | 設定値 |
|---|---|---|
| HIP、`STRATA_HIP_GFX906`、または Metal macro が定義済み | 無効 | 値にかかわらず無効。関数は環境変数を読みません |
| 上記以外（CUDA 実装） | 無効 | 先頭文字が `1` なら有効。それ以外は無効 |

したがって CUDA では `1`、`10`、`1anything` が有効です。空文字、`0`、`true`、` 1` は無効です。大文字小文字や後続文字は見ません。既定値は OFF で、CLI 引数や別の環境変数による上書きはこの判定にはありません。

## 有効になる条件

- 対象ビルドが上表の CUDA 側であること。
- `conversation_checkpoint_save` または内部の snapshot save が呼ばれ、保存対象 vector の合計サイズが 0 でないこと。
- gather buffer の割り当てが成功すること。割り当てに失敗すると個別コピー経路へ戻ります。

layer split 経路でも各 stage の session state を個別に `checkpoint_save` するため、その stage ごとに同じ判定と gather が適用され得ます。実装には layer split を排除する条件はありません。一方、`docs/DETAILS.md` の測定表は「layer split across cards」では未テストとしています。これは測定範囲の注記であり、実装がその経路を無効化するという意味ではありません。

## 実行時の詳細

`ckpt_gather_on()` の結果は関数内の `static const bool` に保存され、プロセス内で最初に呼んだ時に一度だけ評価されます。以降の環境変更は反映されません。無効なら、PLE と各 layer の三つの vector をそれぞれコピーします。

有効なら `ckpt_gather_small()` が mutex を保持し、現在の device に対応する staging buffer と pinned host buffer を確保・再利用します。必要サイズが増えた場合または device が変わった場合は既存 buffer を解放して作り直します。各 vector を順に device buffer へ queued copy し、最後に一度 host へコピーして、各 checkpoint vector に `memcpy` します。合計サイズが 0 の場合は何もコピーせず成功扱いです。

device staging または pinned host buffer の確保ができない場合は `0` を返し、呼び出し元が通常の個別コピーを実行します。gather 中のコピー失敗は `-1` となり、個別コピーには戻らず checkpoint 保存失敗になります。コピー helper は `conversation snapshot running-state copy: <CUDA error>` などを error に設定し、serve の checkpoint 保存 wrapper が stderr に `strata serve: checkpoint save: ...` を出します。保存失敗がコピー資源不足として回復可能なら checkpoint を skip して要求を続け、GPU 側の sticky error など回復不能な場合は要求失敗経路へ進みます。

この変数自体が有効・無効や fallback のログを出すことはありません。`STRATA_PARK_TRACE` が有効な場合、checkpoint snapshot 内の小コピー所要時間を `strata parktrace: save small copies ... ms` として stderr に出します。`STRATA_CKPT_ASYNC` は GDN state 本体の非同期コピーを別に制御します。GDN state の非同期化は gather の必須条件ではありません。

## 根拠

- `src/core/conversation_state.cpp:216-230` — gather 対象の説明、backend macro guard、環境変数の先頭文字判定。
- `src/core/conversation_state.cpp:232-269` — 合計サイズ判定、mutex、buffer の割り当て、vector の gather と host への一括コピー。
- `src/core/conversation_state.cpp:284-303,305-363` — checkpoint save の初期化と GDN 本体の別コピー経路。
- `src/core/conversation_state.cpp:364-382` — gather 呼び出し、割り当て失敗時の個別コピー fallback、および save の戻り値。
- `src/core/conversation_copy.hpp:138-153` — queued copy と通常 copy の完了待ち、およびコピー helper。
- `src/program/generate.cpp:1915-1920,1923-1929,11065-11073` — serve 側の stderr と checkpoint skip / 失敗処理。
- `src/program/generate.cpp:10850-10890,10925-10932` — layer split の各 stage で checkpoint save を行う経路。
- `docs/DETAILS.md:1504-1516` — opt-in スイッチとしての説明、測定者・環境に関する注記、layer split 未測定の記載。
