# `STRATA_PARK_VRAM_MIB`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

会話を park するときに K/V のコピーを保持する CUDA device memory slot の合計予算を MiB 単位で指定する。正の値を指定しても、この変数だけでは機能は動かず、`STRATA_PARK_ASYNC` が有効で、park 対象の device-resident K/V がある場合に slot の取得を試みる。slot を取得した場合、該当する K/V 部分を device-to-device で slot に複製し、復帰時はそこから復元する。slot を使わない場合も通常の park/restore は続き、非同期 stage または host buffer の経路に戻る（`engine/src/core/conversation_snapshot.cpp:165-197, 466-494, 664-699, 1077-1141`）。

コード上、この変数の環境読み取りは `park_vram_budget()` だけにある。CLI 引数、設定ファイル、別の環境変数から予算値を上書きする経路はない（同 `:143-149`）。

## 値と判定

`std::getenv` の結果を `std::atoll` に渡し、変換結果が正の場合だけ MiB を byte に換算する。未設定は `0`、空文字や数字で始まらない文字列も `atoll` の結果が `0` になり無効。負数とゼロも無効。先頭の空白と符号は `atoll` の整数変換規則に従い、数字以降の文字列全体を検証しない。例えば `"  +64MiB"` は `64` として扱われ、`"0anything"` は `0`、`"true"` は `0` になる。正値に上限 clamp はなく、MiB から byte への左シフトも上限検査なしで行われる（`engine/src/core/conversation_snapshot.cpp:143-149`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| `STRATA_PARK_ASYNC` が有効な CUDA 経路 | 予算 0 byte（slot なし） | `64`, `+64`, ` 64MiB`（`atoll` が正値を返す） | 空文字、`0`, `0anything`, `-1`, `true` |
| HIP、gfx906 shim、Metal のビルド | 予算値にかかわらず park async が無効 | なし | すべて（この機能経路では使用されない） |

`atoll` の戻り値が正かどうかだけを判定し、数値文字列全体の妥当性、単位、小数、末尾文字は検証しない。巨大な値に対する明示的な範囲検査もない（同 `:143-149`）。

## 有効になる条件

- `STRATA_PARK_ASYNC` が設定され、その値の**先頭文字**が `'1'` であること。`"1"`, `"10"`, `"1anything"` は on、未設定・空文字・`"true"`・`" 1"` は off。判定結果も関数内 `static` に保存される（`engine/src/core/conversation_snapshot.cpp:237-244`）。
- HIP (`STRATA_USE_HIP`)、gfx906 shim (`STRATA_HIP_GFX906`)、Metal (`STRATA_GPU_METAL`) では上記の値にかかわらず `park_async_on()` が `false` を返す（同 `:237-244`）。
- park 開始時に必要量 `need` が 0 でないこと。必要量は通常 K/V 全体から計算されるが、streamed K/V (`kv_mode != 0`) では host 側にある K/V 部分を除き、device-resident の pooled 部分だけを見積もる（`engine/src/core/conversation_state.cpp:623-636`）。
- 取得できる slot は同じ device の空き slot を再利用するか、新しい slot を 64 MiB 単位に切り上げて確保する。新規確保時は予算内であり、確保後にも 1.5 GiB 以上の空き VRAM が残る必要がある。条件不足や CUDA allocation 失敗時は slot を使わず、async stage を試す（`engine/src/core/conversation_snapshot.cpp:165-197, 179-188, 1086-1141`）。
- slot 容量に収まらない部分や device memory として扱えない部分は、その部分だけ通常の transfer で保存する。したがって値が正でも、全 K/V が slot に入るとは限らない（同 `:466-494`）。

## 実行時の詳細

予算は `park_vram_budget()` の関数内 `static const` として初回評価時にキャッシュされる。値は各 park ごとには再読込されず、初回評価後の環境変更は反映されない。`STRATA_PARK_ASYNC` も別の関数内 `static const` で同様に初回評価時の値を保持する（`engine/src/core/conversation_snapshot.cpp:143-149, 237-244`）。

park の save 処理は K/V の必要量を計算して `conversation_park_async_begin()` を呼ぶ。予算が 0、予算超過、空き VRAM 不足、または slot の `cudaMalloc` 失敗で slot を得られない場合は slot 経路を使わず、通常の async stage 確保を試す。stage も使えないときは `conversation_kv_save()` が同期 transfer にフォールバックするため、予算不足そのものは park の失敗を意味しない（`engine/src/core/conversation_state.cpp:623-638`; `engine/src/core/conversation_snapshot.cpp:165-197, 1086-1141, 496-518`）。

slot に保存できたデータは復帰時に slot から device-to-device で復元される。画像の全 layer が slot にあれば背景コピーの join を待たずに済む。slot が見つからない、または必要な各 part が揃わない場合は join して image の host buffer から復元する（`engine/src/core/conversation_snapshot.cpp:664-699, 702-735`; `engine/src/core/conversation_state.cpp:899-912, 1244-1250`）。

slot は park image と K/V layer の生存期間に紐づき、対応する token が解放されると再利用可能になる。K/V の成長で確保に失敗した場合は、Strata は park slot と stage を解放して一度だけ再試行する。バッチで復元する場合も、park slot 解放後に K/V の成長を再試行し、なお失敗すれば `ERR the K/V cannot grow to the parked conversation: no VRAM is left` を表示して終了コード 1 を返す（`engine/src/core/conversation_snapshot.cpp:1213-1241`; `engine/src/program/generate.cpp:11656-11674, 19952-19958`）。

## ログと測定値

`STRATA_PARK_TRACE` が設定されている場合、かつ予算が正なら、slot 取得成功時に `strata parktrace: kv slot %zu MB tag %llu`、失敗時に `strata parktrace: kv slot: none (%s)` を stderr に出す。失敗理由は `budget`、`vram`、`cudaMalloc` など。予算が 0 の場合、この slot 結果ログは出ない。`STRATA_PARK_TRACE` 自体は値の内容でなく設定有無を見ており、空文字でも有効になる（`engine/src/core/conversation_snapshot.cpp:151, 259-262, 1091-1099`）。

通常の slot 取得失敗に専用の警告や終了はなく、上述の stage / 同期保存へ移る。CUDA のコピー失敗は `conversation snapshot slot copy: ...` 等のエラー文字列として保存処理へ返り、async 背景コピーの失敗は `strata: STRATA_PARK_ASYNC: a parked K/V copy failed (%s)` を stderr に記録する（同 `:477-479, 1061-1068`）。

`docs/DETAILS.md:1797` は、64 MiB 単位、最大 N MiB、空き 1.5 GB 条件、2 回目以降の restore が 33–51 ms から 7–13 ms になった測定を記載している。これは資料記載の値であり、この調査では再測定していない。ソース実装では `N` を byte に換算して 64 MiB 単位で確保する一方、streamed K/V では device-resident 分だけを slot 対象にし、slot 取得失敗時には fallback するため、資料の「whole K/V」は全経路に当てはまる説明ではない（`engine/src/core/conversation_snapshot.cpp:143-149, 165-197, 466-494`; `engine/src/core/conversation_state.cpp:623-636`）。

## 根拠

- `engine/src/core/conversation_snapshot.cpp:143-149` — 予算値の読み取り、`atoll` 変換、static cache。
- `engine/src/core/conversation_snapshot.cpp:165-197, 237-244` — 予算・slot 確保条件、async の build guard と判定。
- `engine/src/core/conversation_snapshot.cpp:466-494, 664-699, 1077-1141` — park save / restore、fallback、slot と stage の取得。
- `engine/src/core/conversation_state.cpp:623-636, 682-699, 899-912` — 必要量算定、非同期 park の呼び出し・lifetime token、restore 呼び出し。
- `engine/src/core/conversation_snapshot.cpp:1061-1068, 1213-1250` — 背景コピー失敗ログ、slot 解放と restore join。
- `engine/src/program/generate.cpp:11656-11674, 19952-19958` — VRAM 不足時の解放・再試行と失敗時の出力。
- `docs/DETAILS.md:1797` — Strata 資料に記載された測定値（本調査での再測定なし）。
