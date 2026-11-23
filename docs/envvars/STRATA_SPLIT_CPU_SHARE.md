# `STRATA_SPLIT_CPU_SHARE`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

CUDA の `strata serve` で、2 枚の GPU にレイヤーを分割した構成における CPU prefill share の既定レイアウトを選びます。未設定ならこのレイアウトを既定で有効にし、`0` で無効、`0` 以外の先頭文字で有効にします。CPU share が有効になると、chunk の staged/streamed 切り替えに使う `stream_all_min()` が share の上限値に変わります。通常の CUDA レイヤー分割では既定上限は 3,072 tokens です（`engine/include/strata/prefill/share_rules.hpp:106-118`, `engine/src/prefill/prefill.cpp:648-658, 730-744, 3868`）。

この変数は既定動作の選択に使われます。`STRATA_PREFILL_CPU_SHARE` を明示した場合、その値による CPU share の有効・無効は別に判定されます。また、遅いリンク向けの `STRATA_PREFILL_CPU_SHARE_AUTO` ルールが条件を満たす場合も、このレイアウト判定とは別に share を既定で有効化する経路があります（`engine/src/prefill/prefill.cpp:691-704, 3878-3892`）。

## 値と判定

`generate.cpp` が `std::getenv()` で値を取得し、`split_share_env_of()` は値全体を parse せず、先頭文字だけを判定します（`engine/src/program/generate.cpp:11801-11804`, `engine/include/strata/prefill/share_rules.hpp:118`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| 2 GPU の CUDA レイヤー分割（後段 stage が 1 個） | 有効（内部値 `-1`） | 空でない値で先頭文字が `0` 以外。例: `1`, `true`, `on`, ` 0`, `0.5` は有効 | 先頭文字が `0`。例: `0`, `00`, `0anything`, `0.5` は無効 |
| 1 GPU、HIP/SYCL build、または 3 枚以上の GPU のレイヤー分割 | レイアウト既定の判定には影響しない | 同左 | 同左 |

未設定と空文字は同じ内部値 `-1` です。非空値は先頭が `0` なら `0`、それ以外なら `1` として扱います。数値としての妥当性、文字列全体、大文字小文字、空白は検査しません。そのため `false` や `off` も先頭が `0` ではなく、有効側になります（`engine/include/strata/prefill/share_rules.hpp:110-118`）。

レイアウト判定は、後段 stage が 1 個で `multi_gpu` かつ CUDA build の場合に限り、内部値が `-1` なら既定 ON、`0` なら OFF、それ以外なら ON です。後段 stage が 0 個で単一 GPU なら、この環境変数の値にかかわらずレイアウト判定は true です。それ以外のレイアウトは false です（`engine/include/strata/prefill/share_rules.hpp:113-118`）。

## 有効になる条件

- この環境変数による既定レイアウト切り替えが実際の share 有効化に使われるのは `o.serve` の経路です。通常の非 serve 経路では `arm_cpu_share()` に別条件を渡しており、この環境変数のレイアウト値は使いません（`engine/src/program/generate.cpp:11801-11827, 23870-23877`）。
- serve では CPU pool が必要です。`--no-pool` の場合は使われず、`--batch` 使用時は `STRATA_PREFILL_CPU_SHARE_BATCH` の先頭文字が `1` でなければ pool を share に使いません（`engine/src/program/generate.cpp:11789-11794, 11826-11827`）。
- 既定 share には、GPU cache にない expert が必要です。全 expert が cache resident なら既定では arm されません（`engine/src/program/generate.cpp:11794-11795, 12302-12306`; 判定式 `engine/include/strata/prefill/share_rules.hpp:101-104`）。
- 既定 share はホストメモリー判定でも止められます。serve の layer split では、pool が使え、batch がない場合にもこの判定を行い、メモリー条件を満たさなければ default share を disarm します。明示的な `STRATA_PREFILL_CPU_SHARE` がある場合は別扱いで、メモリー不足でも値を保持して警告するコードがあります（`engine/src/program/generate.cpp:12194-12221, 12307-12310`）。
- `STRATA_PREFILL_CPU_SHARE` が unset のとき、この変数が false でも、2 枚以上の stage で link-rule が独立して既定 share を arm する場合があります。serve、pool 使用、batch なし、GPU cache に未常駐 expert があり、全 stage の link probe が成功し、CUDA build で `STRATA_PREFILL_CPU_SHARE_AUTO` が許可し、計算された上限が 3,072 tokens を超えることが条件です。`STRATA_PREFILL_CPU_SHARE_AUTO` は未設定なら対象 compute capability 12.0 の discrete CUDA 構成、`1` なら対象 CUDA 構成で有効になり、`0` やその他の値では無効です。この独立ルールのため、`STRATA_SPLIT_CPU_SHARE=0` だけでは当該ルールによる既定 share を必ずしも無効化しません（`engine/src/program/generate.cpp:11811-11824`; `engine/src/prefill/prefill.cpp:499-510, 3878-3892`）。
- `STRATA_PREFILL_CPU_SHARE` を明示すると既定判定が変わります。unset はレイアウト選択に従い、`0` は share を無効にし、`auto` または clamp 後に 0 でない数値は明示設定として扱われます。従って `STRATA_SPLIT_CPU_SHARE=0` は明示した別変数を無効化しません（`engine/src/prefill/prefill.cpp:691-704, 3812-3815, 3868`）。
- `STRATA_PREFILL_STREAM_MIN` が 0 以上で設定されている場合、`stream_all_min()` は share の上限よりこの値を返します。これは `STRATA_SPLIT_CPU_SHARE` の判定を変えるものではありませんが、切り替え token 数に優先します（`engine/src/prefill/prefill.cpp:648-658`）。

## 実行時の詳細

値は generate のモデル・serve 初期化時に `getenv()` され、helper に値を渡します。対象変数自体を static cache するコードはありませんが、serve のレイアウト判定は各リクエストではなく初期化時に一度行われます。したがって、serve 起動後にプロセス環境を変えても、そのサーバーのレイアウト判定には反映されません（`engine/src/program/generate.cpp:11801-11805, 11826-11828`）。

既定 share が arm されると `arm_cpu_share()` が `g_stream_min_share` に `cpu_share_max()` を設定し、後続の `stream_all_min()` が chunk の処理経路を選びます。通常の default limit は 3,072 tokens ですが、`STRATA_PREFILL_CPU_SHARE_MAX`、card-specific default、または独立した link-rule によって異なる場合があります。`STRATA_PREFILL_STREAM_MIN` が設定されている場合は前述のとおりそちらが優先されます（`engine/src/prefill/prefill.cpp:730-744, 3868, 648-658`）。

## ログと測定値

share の既定 arm が成功した2-GPU serve では、明示的な `STRATA_PREFILL_CPU_SHARE` が unset の場合、stderr に次の行を出します（`engine/src/program/generate.cpp:12312-12313`）。

```text
strata serve: layer split of two cards: the CPU prefill share is armed by default, as on one card (STRATA_SPLIT_CPU_SHARE=0 turns it off)
```

ただしこの行は `share_pool`、`share_layout`、未常駐 expert があり、`STRATA_PREFILL_CPU_SHARE` が unset の場合だけです。link-rule が出すログは別で、`STRATA_SPLIT_CPU_SHARE` の値だけを示す専用ログや無効値の警告はありません（`engine/src/program/generate.cpp:12302-12313`; link-rule ログ `engine/src/prefill/prefill.cpp:3889-3891`）。この変数単独の性能測定値は記載しません。

## 根拠

- `engine/src/program/generate.cpp:11789-11827` — serve の pool・GPU cache 条件、CUDA/HIP/SYCL build 分岐、環境値の取得、split link-rule と `arm_cpu_share()` の呼び出し。
- `engine/include/strata/prefill/share_rules.hpp:106-118` — split layout の既定条件と文字列の分類。
- `engine/src/prefill/prefill.cpp:648-658, 691-704, 730-744, 3812-3892` — `stream_all_min()`、明示 CPU share の優先、既定 share の適用と split link-rule。
- `engine/src/program/generate.cpp:12194-12221, 12302-12313` — memory gate と観測できる serve ログ。
