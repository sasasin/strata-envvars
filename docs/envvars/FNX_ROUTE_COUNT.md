# `FNX_ROUTE_COUNT`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA split engine が router の選択結果を expert ごとに数え、`Engine::route_counts()` から取得できる集計を有効にする診断用スイッチ。集計領域は card 0 にだけ確保され、`[decode | prompt][layer][expert]` の順に `unsigned` 値を持つ。router の選択や生成結果を変更する分岐ではなく、選択済み expert ID を追加集計する（`engine/src/split/src/engine.cu:235-238, 706-712, 955-959`; `engine/src/split/src/prefill.cu:1739-1744`; `engine/src/split/src/kernels.cu:1802-1805, 1878-1880`）。

主な利用先は sfnx サーバーと `fnx_run`。sfnx は返信ごとに集計ファイルを更新する。`fnx_run` は終了時に `FNX_ROUTE_FILE` が設定されていれば書き出す。変数自体に CLI 引数による上書きはない（`engine/src/split/tools/sfnx.cpp:527-531, 544-564`; `engine/src/split/tools/fnx_run.cpp:1145-1152`）。

## 値と判定

エンジンの `env_flag` は `env_int(name, 0) != 0`。未設定なら `false`。設定時は符号付き base-10 整数として文字列全体を parse し、任意の符号と数字列だけを許す。値が 0 なら無効、0 以外（負数を含む）なら有効。空文字、空白、`true` / `false`、数字の後ろに文字がある値、long long の範囲外は無効値ではなく例外になる。空白を飛ばしたり、先頭の数値だけを採用したりはしない（`engine/src/split/src/env.hpp:15-22, 33-40, 51-52`）。

| 条件 | unset | 有効になる値（例） | 無効・エラーになる値（例） |
|---|---|---|---|
| sfnx の起動検査 | off | `1`, `-1`, `2` | `0` は off。空文字、`true`、`0anything`、` 1`, 範囲外整数は parse エラー |
| CUDA split Engine の初期化 | off | 0 以外の whole number | 0 は off。parse 規則は上記と同じ |

sfnx はモデルを読む前にこの値を検査するため、不正値は `sfnx: FNX_ROUTE_COUNT: '<値>' is not a whole number` の形式で stderr に出し、終了コード 2 で終了する。値が on で `FNX_ROUTE_FILE` が未設定なら `sfnx: FNX_ROUTE_COUNT needs FNX_ROUTE_FILE` を出し、同じく終了コード 2。`FNX_ROUTE_FILE` の検査は設定有無のみなので空文字も設定済み扱いとなり、後のファイル書き込み時に失敗する（`engine/src/split/tools/sfnx.cpp:1022-1028, 1107-1116`; `engine/src/split/src/env.hpp:34-39`）。

## 有効になる条件

- CUDA split engine を使う実行経路であること。直接の読み取りとカウンターの実装は `engine/src/split/src/engine.cu` / `.cu` カーネルにある。別 backend の読み取りは見つからなかった（`engine/src/split/src/engine.cu:235-238`; `engine/src/split/src/kernels.cu:1802-1805`）。
- モデル処理で router が実行されること。decode は各 layer の `router_route` 後に、prompt は prefill の top-i を得た後に数える。これらの経路を通らない間は値が増えない（`engine/src/split/src/engine.cu:950-959`; `engine/src/split/src/prefill.cu:1739-1744`）。
- sfnx では、on にするなら `FNX_ROUTE_FILE` も設定すること。これは必須の出力先であり、CLI からは指定できない（`engine/src/split/tools/sfnx.cpp:1024-1027`）。
- `fnx_run` は `FNX_ROUTE_COUNT` と `FNX_ROUTE_FILE` の組み合わせを起動前検証しない。ファイル名が設定されている場合にだけ、終了時に集計を要求して保存する。したがって count を on にしても file が unset ならファイル出力は行わない（`engine/src/split/tools/fnx_run.cpp:1145-1152`）。

## 実行時の詳細

sfnx では CLI 引数解析後、モデル読込前に `check_route_env()` が `FNX_ROUTE_COUNT` を読み、Engine 初期化時に CUDA engine が再度読み取る。`env_flag` 自体に static cache はないが、この値を使う分岐は Engine 初期化時だけなので、実行中に環境値を変更しても確保済みのカウンターは切り替わらない。初期化時に card 0 上へ `2 * NL * NEXP` 個を確保してゼロ初期化する（`engine/src/split/tools/sfnx.cpp:1107-1132`; `engine/src/split/src/engine.cu:235-238`; `engine/src/split/src/env.hpp:33-52`）。

各 decode layer の `topi` の `P` 個、各 prompt layer の prefill `topi` の `P` 個について、それぞれ対応する `[layer][expert]` カウンターを atomic increment する。prompt 用領域は decode 用の `NL * NEXP` 個の後ろに置かれる。`route_counts()` は全領域を device から host にコピーして返す（`engine/src/split/src/engine.cu:706-712, 950-959`; `engine/src/split/src/prefill.cu:1740-1744`）。

sfnx は返信完了時に `save_routes()` を呼び、集計が空でなければ `FNX_ROUTE_FILE + ".tmp"` へ全 `unsigned` 値を書いてから指定先へ rename する。カウンターを返信ごとにリセットする処理はなく、ファイル内容は Engine 起動後の累積値で、返信ごとに更新される。書き込みまたは rename が失敗すると stderr に `sfnx: FNX_ROUTE_FILE: cannot write <path> (<error>): route counting stopped` を出し、それ以降の route count 保存を止めるが、サーバー処理は続ける（`engine/src/split/tools/sfnx.cpp:544-564, 567-582, 860-868`）。

`fnx_run` は `FNX_ROUTE_FILE` 設定時、処理終了時に `route_counts()` の内容を指定先へ binary write する。集計が空、open 失敗、write 失敗時は `FNX_ROUTE_FILE <path>: no tallies (FNX_ROUTE_COUNT=1?) or not written` を stderr に出して終了コード 1 を返す（`engine/src/split/tools/fnx_run.cpp:1145-1152`）。

## ログと測定値

有効化だけを知らせるログはない。sfnx の必須出力先不足・不正値・保存失敗の文言と終了・継続条件は上記のとおり。CUDA の確保・コピー・kernel launch に失敗した場合は engine の CUDA エラー処理経路に進むが、この変数専用の追加警告文はない（`engine/src/split/src/engine.cu:235-238, 706-712, 958`; `engine/src/split/tools/sfnx.cpp:1097-1103`）。性能測定値は該当する Strata の資料で確認できなかった。

## 根拠

- `engine/src/split/src/env.hpp:15-22, 33-52` — 整数全体の parse と flag 判定。
- `engine/src/split/src/engine.cu:235-238, 706-712, 950-959` — card 0 の領域確保、取得、decode 集計。
- `engine/src/split/src/prefill.cu:1739-1744` — prompt の top-i 集計。
- `engine/src/split/src/kernels.cu:1802-1805, 1878-1880` — expert ID ごとの atomic increment。
- `engine/src/split/tools/sfnx.cpp:1022-1028, 1107-1135, 527-564, 567-582, 860-868` — 起動前検査、server 出力。
- `engine/src/split/tools/fnx_run.cpp:1145-1152` — CLI ツールの終了時出力。
