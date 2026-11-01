# `DS4_ATTN2Q`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

DeepSeek V4.1 の Metal 実装にある prompt path の sparse attention で、対応条件が整った場合に 1 threadgroup あたり 2 query を処理する `ds4_sparse_attn_mx2` カーネルを選びます。環境変数の値自体は解釈せず、設定の有無を要求スイッチとして使います。Strata は各 dispatch の行情報も検査し、2 query の共有条件が合わなければ通常の 1 query カーネルを選びます（`metal/src/engine/ds4_finish.cpp:1149-1159,1219-1241`）。

## 値と判定

| 状態 | 判定 |
|---|---|
| 未設定 | 要求しない |
| 空文字を含む任意の設定値 | `getenv(...) != nullptr` なので要求する。文字列比較・数値変換はしない |

ただし要求判定は `use_mx` との論理積です。`use_mx` は `ckv_fmt == 2 && G == 8 && attn_mode != 0` のときだけ真です。`attn_mode` は別変数 `DS4_ATTN_MX` を `atoi` で読み、未設定なら 1 です（`metal/src/engine/ds4_finish.cpp:1223-1228`）。このため `DS4_ATTN2Q` を設定しても、対応する packed cache format、`G == 8`、matrix-unit 経路の条件を満たさない場合は 2-query カーネルを要求しません。

`attn2q_env` は関数内の `static const bool` です。最初に `sparse_attn` がこの式へ到達した時点の環境変数の有無と `use_mx` の値を一度だけ評価し、その結果をプロセス内で保持します。最初の到達時に環境変数が未設定、または `use_mx` が偽なら、後の呼び出しで環境を設定したり `use_mx` が真になったりしても有効になりません。最初に真で初期化された場合は、その後の呼び出しでも `attn2q_env` は真のままです。環境を実行中に変更した結果はこの判定に反映されません（同 `ds4_finish.cpp:1223-1233`）。

## 有効になる条件

- このコードは Metal の DeepSeek V4.1 エンジンにある `sparse_attn` prompt path です。別 backend の実装はこの候補名を参照しません（`metal/src/engine/ds4_finish.cpp:1149-1154,1223-1241`）。
- 関数は `T <= 0` または `heads <= 0` なら成功扱いで先に戻るため、環境変数の判定まで到達しません。`d != 512`、`rows == nullptr`、`ckv_fmt` が 0/2 以外の場合もエラーで先に戻ります（同 `ds4_finish.cpp:1151-1160`）。
- 初回の static 判定に加えて、その dispatch で `ar.win0[t] == ar.win0[0]`、`ar.nsel[t] == ar.nsel[0]`、および `ar.nwin[t] >= ar.nwin[t-1]` が全ての `t=1..T-1` で成り立つ必要があります。どれか一つでも違えば、その dispatch では `attn2q` を偽に戻します（同 `ds4_finish.cpp:1229-1238`）。
- 2-query 条件が崩れたとき、または環境スイッチが無効のときは、他の条件に応じて `ds4_sparse_attn_mx`、packed cache 用の `ds4_sparse_attn_g8/g4/g2/g1`、または BF16 用 `ds4_sparse_attn_bf16` を選びます（同 `ds4_finish.cpp:1238-1241`）。

## 実行時の詳細

`DS4_ATTN2Q` を参照するコードは `metal/src/engine/ds4_finish.cpp:1228` の一箇所です。環境変数を初回に読み、その要求を各 dispatch の行情報でさらに絞り込みます。2-query kernel が選ばれると `qpt=2` となり、dispatch の query grid は `(T + 1) / 2` です。1-query 経路では `qpt=1` で grid は `T` になります（同 `ds4_finish.cpp:1232-1241,1266-1269`）。

選ばれた関数名で Metal pipeline を取得します。pipeline の取得が例外になった場合、stderr に `dsv41 metal: sparse_attn pipeline <関数名> unavailable` を出して `false` を返します。2-query の pipeline 取得に失敗した場合に、1-query pipeline へ再試行する処理はこの箇所にはありません（同 `ds4_finish.cpp:1238-1256`）。環境変数の設定・値そのものに対するログはありません。

## 根拠

- 候補一覧の掲載: `docs/envvars/000_envvers.md:104`。これは候補掲載のみで、実読み取りは次の実装箇所で確認。
- 入力検査と prompt sparse-attention 関数: `metal/src/engine/ds4_finish.cpp:1149-1160`。
- `DS4_ATTN_MX`、`use_mx`、`DS4_ATTN2Q` の読み取りと cache: `metal/src/engine/ds4_finish.cpp:1223-1233`。
- 行条件、query 単位、kernel 選択: `metal/src/engine/ds4_finish.cpp:1229-1241`。
- pipeline 失敗時の stderr と戻り値、dispatch grid: `metal/src/engine/ds4_finish.cpp:1242-1256,1266-1271`。
