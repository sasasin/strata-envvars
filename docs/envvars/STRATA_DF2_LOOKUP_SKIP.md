# `STRATA_DF2_LOOKUP_SKIP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

suffix lookup が指定長以上の過去一致を見つけたとき、DFlash2 の次ラウンド用 draft をその場で計算せず、次ラウンドの開始時に lookup を使うか DFlash2 draft を計算するか決めるための最小一致長（token 数）です。読み取りと共通条件判定は `strata::spec::df2_lookup_skip_min` / `skip_draft_for_lookup` にあり、CLI の生成ループと server の生成ループで使われます。環境変数が 0 以下ならこの先送りは起きません。`engine/include/strata/spec/window_rule.hpp:40-55`、`engine/src/program/generate.cpp:22619-22635,24938-24957`、`engine/sycl/src/program/generate.cpp:12648-12660,14012-14023`。

## 値と判定

`df2_lookup_skip_min` は関数内 `static const int` を初期化するときに `std::getenv` で読みます。変数が未設定、または値が空文字なら呼び出し側の既定値を使います。それ以外は `std::atoi` の戻り値を使い、文字列全体の妥当性検証や clamp はしません。したがって先頭の数値部分だけが変換され、数値に変換できない文字列は 0 になります。`engine/include/strata/spec/window_rule.hpp:48-55`。

| 条件 | unset / 空文字 | 有効になる値 | 先送りしない値の例 |
|---|---|---|---|
| `STRATA_GPU_METAL` でビルドされた engine（CLI / server） | 8 | 正の整数。実際には suffix match 長がその値以上のとき候補になる | `0`, `-1`, `abc`, `0anything` |
| Metal 以外の `engine/src` 経路（DFlash2 対応ビルド） | 0 | 正の整数。実際には suffix match 長がその値以上のとき候補になる | unset、空文字、`0`, `-1`, `abc`, `0anything` |
| SYCL 経路 | 0 | 正の整数。実際には suffix match 長がその値以上のとき候補になる | unset、空文字、`0`, `-1`, `abc`, `0anything` |

`atoi` のため `8junk` は 8、` 8` は 8、`+8` は 8 と判定されます。`true` は 0 です。負数も数値として受け取りますが、有効化側で `min_match > 0` を要求するため先送りはしません。閾値を超える suffix match の長さに上限 clamp はありません。空文字は unset と同じ build 既定値です。`atoi` の変換方法と `min_match > 0` 条件は `engine/include/strata/spec/window_rule.hpp:44-53`。

## 有効になる条件

- DFlash2 対応の実行経路で DFlash2 がそのラウンドの draft 元であること。CLI では `req_df2`（pipeline）または `use_df2`（serial）、server では `use_df2` が条件です。DFlash2 のビルド条件は `STRATA_HAVE_DFLASH2` です。`engine/src/program/generate.cpp:22619-22633,23142-23144,24949-24957`、`engine/sycl/src/program/generate.cpp:12655-12659,12920-12921,14018-14022,14215-14216`。
- `--suffix-draft` が正であること。suffix drafter が無効なら候補を調べず、先送りもしません。`engine/src/program/generate.cpp:22630-22633,24952-24954`、`engine/sycl/src/program/generate.cpp:12655-12658,14018-14021`。
- 先頭 window ではないこと。CLI の serial と server の条件で first window を除外します。`engine/src/program/generate.cpp:24952-24954`、`engine/sycl/src/program/generate.cpp:14063-14067`。
- `sfx.propose` が正の lookup 長を返し、`sfx.last_match()` が設定値以上であること。`lookup_k > 0` と `match >= min_match` の両方を検査します。共通判定は `engine/include/strata/spec/window_rule.hpp:44-46`。
- `engine/src` は `STRATA_GPU_METAL` ビルドなら既定 8、それ以外は 0。SYCL は呼び出し時に 0 を渡します。したがって環境変数が空または未設定のとき、Metal 以外ではこの機能は既定で無効です。`engine/src/program/generate.cpp:22619-22624,24938-24943`、`engine/sycl/src/program/generate.cpp:12648-12650,14012-14013`。
- suffix match が閾値を満たしても、次ラウンドの policy が lookup を選ばない場合、DFlash2 draft は次ラウンド冒頭で実行されます。環境変数は lookup の採用を強制しません。`engine/src/program/generate.cpp:22675-22688,24999-25012`、`engine/sycl/src/program/generate.cpp:12673-12686,14037-14050`。

## 実行時の詳細

環境変数は `df2_lookup_skip_min` の最初の呼び出しで一度読み、関数内 static に保存します。呼び出しは各生成ループの初期化時にあり、同じプロセス内で環境を変更しても値は再読込されません。engine の CLI / server は Metal 既定値 8 またはその他 0 を渡し、SYCL は 0 を渡します。`engine/include/strata/spec/window_rule.hpp:48-55`、`engine/src/program/generate.cpp:22619-22624,24938-24943`、`engine/sycl/src/program/generate.cpp:12648-12650,14012-14013`。

条件に合うと、現在の window の commit 後に DFlash2 draft を計算せず、行数・位置・anchor を保存して次の反復へ進みます。次の反復では suffix lookup を再提案し、policy が lookup を選べば DFlash2 の context 更新を行い、その lookup window を使います。選ばなければ保存した位置と anchor で DFlash2 draft を計算します。つまり draft を省略できるのは lookup が実際に選ばれた場合だけで、結果の候補 window は通常どおり後続の処理で検証されます。`engine/src/program/generate.cpp:22630-22635,22675-22688,24949-24964,24999-25012`、`engine/sycl/src/program/generate.cpp:12655-12668,12673-12686,14018-14030,14037-14050`。

engine の server pipeline では、先送り確認に加えて merged window でないことも条件です。SYCL server の deferred lookup は `policy.choose` が選ばない場合でも同じ保存位置から draft し直します。`engine/src/program/generate.cpp:22630-22635,23142-23144`、`engine/sycl/src/program/generate.cpp:12655-12660,12673-12686`。

## ログと測定値

この変数の読み取り値や先送り判断を直接表示するログはありません。通常の失敗経路では、次ラウンドで lookup context 更新または DFlash2 draft が失敗した場合、CLI は `strata generate: <err>`（serial）、server は `ERR <err>` を出して終了コード 1 を返し、SYCL の serial も `strata generate: <err>`、server は `ERR <err>` を出します。該当箇所は `engine/src/program/generate.cpp:22682-22686,25006-25010`、`engine/sycl/src/program/generate.cpp:12680-12684,14044-14048`。変数による速度や品質の測定値は、`docs/DETAILS.md` に記載がありません。同資料には一般的な prompt lookup の説明がありますが、この環境変数や DFlash2 draft 先送りの測定条件・値はありません（`docs/DETAILS.md:376-383,1565-1568`）。

## 根拠

- `engine/include/strata/spec/window_rule.hpp:40-55` — 共通条件、環境値の読み取り、既定値の扱い。
- `engine/src/program/generate.cpp:22619-22635,22675-22688,23142-23144,24938-24964,24999-25012` — CLI / server の build 別既定値、先送りと次 window の選択。
- `engine/sycl/src/program/generate.cpp:12648-12668,12673-12686,12920-12921,14012-14030,14037-14050,14215-14216` — SYCL CLI / server の呼び出し、既定値、先送りと失敗経路。
- `docs/DETAILS.md:376-383,1565-1568` — draft layer と prompt lookup の説明。対象変数固有の測定値はなし。
