# `STRATA_GFX1151_CHUNK`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

Windows HIP で gfx1151 の統合 GPU 構成を検出したとき、bare `--prefill auto` に適用される Windows HIP 共通の 6,144-token 上限を外し、初期 chunk を少なくとも 16,384 にします。既定の own-buffer 経路では後続処理が auto を解除してこの chunk を保ちます。一方、loan planner が動く経路では `prefill_auto_max` は 8,192 のままなので、16,384 が実 chunk になるとは限りません。`STRATA_GFX1151_CHUNK` 自体は chunk 数を指定する変数ではなく、値が `0` で始まるかどうかだけを調べる opt-out です。unset も含め `0` で始まらない値なら既定の引き上げが働きます（`engine/src/program/generate.cpp:4371-4390, 4990-4995, 11244-11248`、`engine/include/strata/platform/host_limits.hpp:19-30`）。

この判定は起動時に `--prefill` を処理した後、HIP デバイスの性質を確認する箇所で行われます。GPU の kernel や生成 token を直接選ぶ変数ではなく、prompt prefill 用 chunk の auto ceiling を変えます。後段の VRAM/cache に応じた選択や prompt 長によって、実際に使う chunk は ceiling より小さくなることがあります（`engine/src/program/generate.cpp:4287-4303, 4374-4390, 11229-11233, 23989-24063`）。

## 値と判定

実装は `std::getenv` で値を取得し、`v != nullptr && v[0] == '0'` の形で先頭文字だけを確認します。整数変換、文字列全体の比較、空白除去、大文字小文字変換はありません。`'0'` で始まれば opt-out、その他は opt-out になりません（`engine/src/program/generate.cpp:4375-4383`）。

| 条件 | unset | 有効になる値（引き上げを許す） | opt-out になる値 |
|---|---|---|---|
| Windows HIP、device 0 が gfx1151 統合 GPU、bare `--prefill auto`（`STRATA_PREFILL_AUTO_MAX` 未設定） | 引き上げる。初期 chunk は 16,384 | `1`, `16`, `true`, 空文字、`false` など先頭文字が `0` でない任意の値 | `0`, `0anything` など先頭文字が `0` の値。通常の Windows HIP bare-auto cap 6,144 が残る |
| 上記以外 | 対象変数による変更なし | 対象変数による変更なし | 対象変数による変更なし |

値の例は数値として解釈されません。たとえば `16` は 16-token chunk を意味せず引き上げを許し、`0anything` は無効値エラーにはならず opt-out になります。空文字は設定済みですが先頭文字が `0` ではないため引き上げを許します。`STRATA_GFX1151_DEFAULTS` も同じ条件で `0` 始まりなら引き上げを抑止します（`engine/src/program/generate.cpp:4375-4389`）。

## 有効になる条件

- ビルドが HIP で、Windows (`_WIN32`) であること。共通の Windows HIP bare-auto cap は 6,144 です（`engine/src/program/generate.cpp:4011-4019`、`engine/include/strata/platform/host_limits.hpp:19-25`）。
- デバイス 0 のプロパティ取得が成功し、その device が統合 GPU と報告され、architecture 名が `gfx1151` であること。device count の取得に成功した場合、device 0 以降の最大 63 台も統合 GPU かつ device 0 と同じ architecture か確認します。別種の GPU が検出されれば引き上げません。device count の取得自体に失敗した場合、追加 GPU の検査は行われず、device 0 の条件で続きます（`engine/src/program/generate.cpp:4291-4303, 4374-4379`）。
- `--prefill auto` が bare であること。`--prefill auto:N` と `STRATA_PREFILL_AUTO_MAX` が設定された `--prefill auto` は bare 扱いにならず、この gfx1151 引き上げを受けません。明示的な `--prefill N` も対象外です（`engine/src/program/generate.cpp:4000-4021, 4379-4389`）。
- `STRATA_GFX1151_CHUNK` または `STRATA_GFX1151_DEFAULTS` のどちらも `0` で始まらないこと。どちらか一方が `0` で始まれば上限引き上げを行いません（`engine/src/program/generate.cpp:4380-4389`）。
- 16,384 は初期 chunk です。既定の Windows gfx1151 own-buffer 経路では `prefill_own_keep_chunk` が有効になり、auto が通常 2,048 に戻す箇所でもこの値を保持します。`STRATA_PREFILL_BORROW=1` で loan を有効にすると auto planner が動き、`prefill_auto_max` は別に 8,192 のままです。chunk は cache / ring に入る最大値を planner が決めるので、対象変数だけでは loan 経路を 16,384 に拡張しません（`engine/src/program/generate.cpp:4392-4405, 4990-4995, 11244-11248, 11351-11409`）。prompt が短ければ必要量だけを読みます。特定 chunk の buffer 初期化が失敗すれば smaller chunk で再試行し、再試行できない場合は理由を stderr に出して起動を失敗させる経路があります（`engine/src/program/generate.cpp:12747-12764, 13101-13140`）。Windows gfx1151 で own-buffer 経路が選ばれる場合は、初期化前の arithmetic-only free-VRAM check では chunk を縮小せず、実 allocation 失敗時の step-down は残ります（`engine/src/program/generate.cpp:13071-13098`）。

## 実行時の詳細

`--prefill auto` の引数処理時に、`STRATA_PREFILL_AUTO_MAX` が未設定なら `prefill_auto_max` は 8,192 になります。Windows HIP の bare-auto cap により `prefill_auto_cap=6,144`、chunk 初期値も 6,144 になります。その後 GPU を検出し、上記 gfx1151 条件を満たし、両方の opt-out がなければ cap を `0`（上限なし）へ戻し、chunk 初期値を `max(current, 16,384)` にします。ここでは `prefill_auto_max` 自体は変更されません（`engine/src/program/generate.cpp:4000-4021, 4374-4389`）。

既定の gfx1151 ブロックは `STRATA_PREFILL_BORROW` が `1` で始まらず、`STRATA_GFX1151_DEFAULTS` が `0` で始まらない場合、`no_prefill_borrow` と `prefill_own_keep_chunk` を有効にします。引数処理後に own-buffer 経路へ入ると auto flag を解除し、`prefill_own_keep_chunk` が true なら選定済み chunk を 2,048 に戻しません。この標準経路では対象変数の引き上げ後 chunk が 16,384 になります。`STRATA_PREFILL_BORROW=1` で loan を選ぶと、この auto 解除は行われず、loan planner の `auto_ceiling` は `prefill_auto_max` 由来の 8,192 を上限にします（`engine/src/program/generate.cpp:4399-4405, 4990-4995, 11244-11248, 11351-11390`）。

この env 値は起動時のデバイス判定ブロックで2回取得されます。static cache ではなく、リクエストごとに読む実装でもありません。値は起動後に再評価されず、プロセス実行中に環境を変更しても現在の engine の chunk 設定には反映されません（`engine/src/program/generate.cpp:4374-4383`）。

`STRATA_GFX1151_CHUNK=0` の場合は Windows HIP 共通の bare-auto cap 6,144 が残ります。`STRATA_GFX1151_DEFAULTS=0` もこの上限引き上げを抑止します。どちらも設定されず引き上げが有効なとき、Windows gfx1151 の prompt path は own-buffer 設定も有効になり、auto が「借りる slot がない場合に 2,048 に戻す」処理でも選定済み chunk を保ちます（`engine/src/program/generate.cpp:4380-4405, 4990-4995`）。

CLI / 別変数の関係は次のとおりです。

- `--prefill N` は指定 chunk を使い、この変数は変更しません。Windows HIP では 8,192 以上のユーザー指定 chunk に警告を出す経路がありますが、gfx1151 条件でこの変数が unset または `0` 以外なら、その警告を抑止します（`engine/src/program/generate.cpp:4008-4021, 4374-4377, 4416-4420`）。
- `--prefill auto:N` は `N` を 8,192 / 16,384 / 32,768 の `prefill_auto_max` に丸めて扱います。`STRATA_PREFILL_AUTO_MAX` も設定されている bare `--prefill auto` を非-bare にします。どちらも gfx1151 の引き上げ条件から外れ、対象変数は `prefill_auto_max` を変更しません（`engine/src/program/generate.cpp:4002-4021, 4379-4389`）。
- `STRATA_GFX1151_DEFAULTS=0` は gfx1151 chunk 引き上げを抑止します。これはこの文書の対象変数とは別の opt-out で、gfx1151 の他の既定設定にも関係します（`engine/src/program/generate.cpp:4375-4389`）。

## ログと測定値

対象変数が設定された／引き上げられたことを専用に表示するログは、この分岐にはありません。serve 経路では auto で確定した値を `strata serve: prompt chunk auto: %lld tokens, a %lld-slot ring` と出し、generate 経路の loan が成立した場合は `strata generate: prompt chunk auto: %lld tokens` と出します。これらは対象変数の値ではなく、選択後の chunk を示します（`engine/src/program/generate.cpp:12747-12759, 23989-24063`）。

ソースコメントには過去の測定として、Strix Halo / Windows gfx1151、engine 0.1.52、IQ3_S、own prompt buffers で、chunk 上限を 8,192 から 16,384 にした際の 32K prompt が 1,260.0 から 1,307.9 tok/s、64K prompt が 1,191.0 から 1,238.2 tok/s とあります。調査対象 commit で新たに測定した値ではありません（`engine/src/program/generate.cpp:4384-4388`）。

## 根拠

- `engine/src/program/generate.cpp:4000-4021` — CLI `--prefill`、bare-auto 判定、Windows HIP 上限と警告の設定。
- `engine/src/program/generate.cpp:4287-4303, 4371-4407` — HIP デバイス条件、対象変数と `STRATA_GFX1151_DEFAULTS` の判定、chunk ceiling と own-buffer 設定。
- `engine/include/strata/platform/host_limits.hpp:19-30` — Windows HIP の 6,144 cap と明示 chunk 警告の条件。
- `engine/src/program/generate.cpp:4990-4995, 11229-11233, 12747-12764, 13071-13140, 23989-24063` — 後段の chunk 選択、失敗時の縮小・終了、選択 chunk のログ。
