# `STRATA_REFILL_SERIAL`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

prompt path が expert cache から借りた slot を返す refill 処理の順序を切り替える。CUDA/HIP 側 (`engine/src/program/generate.cpp`) と SYCL 側 (`engine/sycl/src/program/generate.cpp`) の両方に読み取りと同じ分岐がある。複数の参加 stage がある通常経路では、未設定なら全参加者のコピーを先に発行してから待ち、設定ありなら参加者ごとにコピーを発行して完了を待つ。各経路は借りた slot を同じ cache に戻す処理であり、この変数が直接変えるのは refill の順序である（`engine/src/program/generate.cpp:20543-20568`, `engine/sycl/src/program/generate.cpp:11373-11399`）。

## 値と判定

| ビルド | unset | 設定時に有効になる値 | 無効になる値 |
|---|---|---|---|
| `engine/src` (CUDA/HIP) と `engine/sycl/src` (SYCL) | `refill_serial == false` | 空文字、`0`、`1`、`true`、`false`、`0anything` を含む、環境変数が存在するすべての場合 | なし |

両実装とも `std::getenv("STRATA_REFILL_SERIAL") != nullptr` の真偽だけを `static const bool` に保存する。文字列の変換・比較はせず、空白、大文字小文字、数値としての妥当性も調べない。したがって `=0` や空文字も有効である。未設定だけが false になる（`engine/src/program/generate.cpp:20545-20546`, `engine/sycl/src/program/generate.cpp:11375-11376`）。

## 有効になる条件

- 実行バイナリが該当する `engine/src` または `engine/sycl/src` の実装を使うこと。両方のコードに同じ判定がある（上記行）。
- prompt path が expert cache の slot を借りて返す refill を通ること。CUDA/HIP 側では `pf_borrow` が `!o.no_prefill_borrow && !o.expert_profile.empty()` で始まり、auto cache sizing がこれを解除する経路もある。SYCL 側にも同じ初期条件がある（`engine/src/program/generate.cpp:6821`, `engine/src/program/generate.cpp:9334-9343`, `engine/sycl/src/program/generate.cpp:3847-3850`）。
- この設定が refill 順序を変えるのは、全体 refill 時に lent slot を持つ参加者が 2 つ以上 (`n_parts > 1`) の場合だけ。参加者が 0 または 1 なら両設定とも同じ `refill_one` 経路になる（`engine/src/program/generate.cpp:20549-20560`, `engine/sycl/src/program/generate.cpp:11379-11390`）。layer split の各 stage はそれぞれ自身の cache から slot を借りる（`engine/src/program/generate.cpp:12442-12455`）。
- chunk の再設定時など、単独の参加者だけを返す `refill_one(p, e)` の直接呼び出しは、この変数を判定せず同じ順序で実行する（`engine/src/program/generate.cpp:20629-20637`, `engine/sycl/src/program/generate.cpp:11403-11424`）。
- `--no-prefill-borrow`、空の `--expert-profile`、または cache sizing による borrowing 無効化などで slot を借りない場合、この変数が切り替える refill は発生しない。CLI や他の環境変数がこの変数の値を上書きする処理はない。

## 実行時の詳細

値は各 backend の生成処理中に到達した関数スコープの `static` 初期化で一度読み取られ、その後プロセス内で cache される。実行中に環境を書き換えても再評価されない（`engine/src/program/generate.cpp:20545-20547`, `engine/sycl/src/program/generate.cpp:11375-11377`）。

設定なしで `n_parts > 1` のときは、lent slot を持つ各 `PfPart` の `refill_issue` を順に呼び、その後各 `refill_wait` を順に呼ぶ。設定ありでは各参加者について `refill_one`（issue と wait）を順に完了させてから次へ進む。全体 refill 完了後は `res_upload()` を呼ぶ。1 participant の場合は `refill_one` のみで、設定の有無による順序差はない（`engine/src/program/generate.cpp:20547-20561`, `engine/sycl/src/program/generate.cpp:11377-11391`）。

CUDA/HIP 実装は `blob_stable` が null、slot への copy、または queued copy の失敗で false を返す。SYCL 実装は `blob` が null、slot への copy、途中の queued sync、または最終 sync の失敗で false を返す（`engine/src/program/generate.cpp:20498-20518,20520-20522`, `engine/sycl/src/program/generate.cpp:11341-11359`）。prompt の window 前または prompt 処理後の全体 refill が失敗すると、両実装とも stdout に `ERR refilling a lent slot failed: <error>` を出して `1` を返す（`engine/src/program/generate.cpp:21551-21558,21625-21628`, `engine/sycl/src/program/generate.cpp:11639-11645,11687-11689`）。

成功時の refill 所要時間は `STRATA_TRACE` が設定され、かつ lent participant がある場合に stderr へ `strata trace: refilled %lld slots on %lld stage(s) in %.1f ms` の形式で出る。`STRATA_REFILL_SERIAL` 自体はログを有効化しない（`engine/src/program/generate.cpp:16069-16072,20561-20567`, `engine/sycl/src/program/generate.cpp:9461-9465,11391-11397`）。

## 根拠

- 変数の全読み取り箇所と分岐: `engine/src/program/generate.cpp:20543-20568`, `engine/sycl/src/program/generate.cpp:11373-11399`。
- 借用参加者の構成と有効条件: `engine/src/program/generate.cpp:6821,12442-12455`; SYCL は `engine/sycl/src/program/generate.cpp:3847-3850,7243-7250`。
- refill の失敗と観測可能な戻り: `engine/src/program/generate.cpp:20498-20522,21551-21558,21625-21628`; `engine/sycl/src/program/generate.cpp:11341-11367,11639-11645,11687-11689`。
