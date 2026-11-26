# `STRATA_ROUTE_TAIL_SKIP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

miss した expert のうち、verify window 内で現れる router rank がすべて指定 rank 以上のものを、転送も計算もせず寄与ゼロにします。rank `R` は `1`〜`9` で、値が小さいほど対象が広がります。Router が作った expert ID と routing weight はこの変数自体では書き換えませんが、除外した expert の出力行がゼロになるため、後段の結果は変わり得ます（`engine/src/core/expert_source.cpp:5502-5525,5578-5581,5822-5825`）。

処理は `expert_pool_dispatch_multi` の共通 expert dispatch にあり、環境値の解決は `tail_skip_rank()` が行います。値の解決コード自体に backend 判定はありません。実際に skip するには、この dispatch で miss した expert がある必要があります（`engine/src/core/expert_source.cpp:5416-5424,5498-5500,5505-5527`）。

## 値と判定

`tail_skip_rank_from_text` は未設定 (`nullptr`) を `0` にし、それ以外は `std::atoi` で整数変換し、結果が `1`〜`9` のときだけその rank を採用します。それ以外は `0`（off）です。文字列全体の妥当性検査はなく、`atoi` が先頭から変換できた整数を使います。したがって空文字・非数値は `0`、`7x` と先頭空白付き ` 7` は `7`、`0anything` は `0`、`10` と `-1` は `0` です。大文字小文字は関係しません（`engine/include/strata/core/tail_skip_default.hpp:11-20`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
| --- | --- | --- | --- |
| Engine が環境値を読む場合 | rank `0`（off） | `1`〜`9`（例: `7`, `7x`, ` 7`） | 空文字、`0`, `0anything`, `true`, `10`, `-1` は rank `0` |

Terminal の engine 子プロセス環境は、親プロセスの環境を基にし、run config の `env` が同名値を上書きし、最後に未設定なら `STRATA_ROUTE_TAIL_SKIP=0` を補います。したがって子プロセス環境では run config がユーザー環境より優先され、明示的な空文字や `0` も値として維持されます。`strata launch --set STRATA_ROUTE_TAIL_SKIP=...` は起動設定の `env` に値を反映します（`terminal/serve/server.py:4007-4010,4027-4028,4034-4036`; `terminal/strata_control/speed_switches.py:172-186`; `terminal/strata_cli/launch/runner.py:802-806`）。Setup は Unsloth の run config に `0` を書き、既存 config の非空・非 `0` の利用者値を再 setup 時に保持します（`terminal/setup.py:4741-4759,7581-7586`）。

## 有効になる条件

- Parse 後の rank が `1`〜`9` で、dispatch window に少なくとも一つの miss expert があること。GPU cache 内 (`host_res >= 0`) の expert は対象外です（`engine/src/core/expert_source.cpp:5498-5500,5518-5526`）。
- 対象の dispatch で `d.peer == nullptr` かつ `d.remote_count == 0` であること。peer GPU または remote helper が関与する dispatch では、この skip 判定ブロックに入りません（`engine/src/core/expert_source.cpp:5510-5512`）。
- 対象 expert の window 内での最小 routing rank（`i % k`）が設定 rank 以上であること。コードは expert ごとの window 内の出現をまとめて最小 rank を計算し、条件に合うものを skip します（`engine/src/core/expert_source.cpp:5513-5525`）。
- `STRATA_ROUTE_TAIL_RENORM` は別の任意設定です。これが有効で非-Metal build などの条件を満たす場合、verify 経路で skip 対象の routing weight を再正規化する処理が追加されます。未設定または `atoi` 結果が `0` の場合は追加されません。この再正規化は `STRATA_ROUTE_TAIL_SKIP` 自体の有効化条件ではありません（`engine/include/strata/core/device_hits_plan.hpp:29-31`; `engine/src/core/verify.cpp:1533-1537,2681-2685`）。

## 実行時の詳細

Engine は `g_tail_skip_rank` が未解決 (`-1`) のとき `std::getenv("STRATA_ROUTE_TAIL_SKIP")` を一度読み、その parse 結果を atomic に保存します。以後の `tail_skip_rank()` 呼び出しは cache を返すため、engine 起動後に環境値を変えても適用 rank は変わりません。別の `set_tail_skip_rank()` API は `1`〜`9` 以外を `0` に正規化して cache を上書きしますが、engine 内にその API の呼び出し箇所は見つかりませんでした（`engine/src/core/expert_source.cpp:5412-5424`; 呼び出し箇所: `engine/src/core/expert_source.cpp:5505`, `engine/src/core/verify.cpp:2682-2684`, `engine/src/program/generate.cpp:14939,16253`）。

dispatch は window の router 出力から distinct expert を作り、miss 数を数えます。各 expert の最小 rank が閾値以上なら `skip_d` に印をつけ、miss 数を減らします。その後その expert の各 entry を `kind=-2` とし、CPU prefetch / GPU fetch の対象から外します。計算段階で該当 row をゼロにして `tail_skipped` を増やします。通常の skip 経路では routing weight の再正規化は行いません（`engine/src/core/expert_source.cpp:5490-5500,5510-5527,5560-5568,5573-5581,5822-5825`）。

Serve 起動時には rank が正で、全 expert が resident ではない場合に限って stderr に有効ログを出します。全 expert resident の場合はこのログが抑制されます。skip が実際に起きた場合は累積数も出ます。run manifest の `decode/route-tail-skip` には有効状態と unset または生の環境文字列が記録されます（`engine/src/program/generate.cpp:14932-14942,16253-16255,23791-23793`）。

## ログと測定値

有効時の serve 起動ログは `strata serve: STRATA_ROUTE_TAIL_SKIP=%d is ON: a missed expert that every token of a verify window routes at rank %d or lower is skipped (answers differ slightly); it is off when STRATA_ROUTE_TAIL_SKIP is not set or is 0` です。実 skip があった後の累積ログは `strata serve: route tail skip: %lld missed experts skipped (%lld entries) since the start` です（`engine/src/program/generate.cpp:14939-14942,23791-23793`）。無効値専用の警告、終了、失敗経路は見つかりませんでした。

`docs/DETAILS.md` は rank 7・UD-Q4_K_XL・RTX 5090・DFlash2 `--spec 6`・48 prompts・12,288 forced-token positions の測定表を記載しています（`docs/DETAILS.md:1237-1245`）。同資料が述べる `STRATA_TAIL_SKIP_MAX_CACHED` による適用条件変更は、この checkout の Strata 所有実装で参照を確認できず、現行コードの条件としては記載していません。

## 根拠

- 値の変換と unset default: `engine/include/strata/core/tail_skip_default.hpp:11-20`
- 環境読み取り、cache、rank 判定: `engine/src/core/expert_source.cpp:5412-5424,5505-5527`
- miss 除外、zero row、skip 集計: `engine/src/core/expert_source.cpp:5560-5581,5822-5825`
- 起動ログ・manifest・累積ログ: `engine/src/program/generate.cpp:14932-14942,16253-16255,23791-23793`
- 子プロセス環境の優先順位と default: `terminal/serve/server.py:4007-4010,4027-4036`; `terminal/strata_control/speed_switches.py:172-186`
- `--set` の反映、setup config: `terminal/strata_cli/launch/runner.py:802-806`; `terminal/setup.py:4741-4759,7581-7586`
- 関連する weight 再正規化条件: `engine/src/core/verify.cpp:1533-1537,2681-2685`; `engine/include/strata/core/device_hits_plan.hpp:29-31`
