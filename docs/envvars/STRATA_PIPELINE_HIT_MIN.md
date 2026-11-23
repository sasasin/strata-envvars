# `STRATA_PIPELINE_HIT_MIN`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`strata generate` の `--serve` 中に使われる pipeline windows の speculative window gate を、予測確率 `theta` との比較から、同じ確率帯の過去の on-path 率と比較する gate に切り替えます。対象値は、確率帯ごとの推定 on-path 率が設定値以上なら、その speculative window を先行実行するための下限です。値は `generate.cpp` で無条件に環境から読み取られます。`STRATA_PIPELINE_DEBUG=1` を要求する `pipe_dbg_env` 経由ではありません（`engine/src/program/generate.cpp:679-685, 20143-20159`）。

対象値自体は pipeline の有効化スイッチではありません。パイプラインが動いていない経路では gate も使われません。また、この値は生成する token や verifier の選択条件を直接変えず、投機的な window を先に走らせるかどうかを変えます。実装コメントは `STRATA_IQ_MT_MIN=1` のとき serial loop と同じ token になるとしています（`engine/src/program/generate.cpp:20143-20152, 21747-21765, 21696-21705`）。

## 値と判定

読み取りは `std::getenv` で、値が null または先頭文字が NUL（空文字）の場合は `-1.0f` になります。それ以外は `std::atof` の結果を `float` にします。全体の文字列検証、範囲制限、clamp、エラー処理はありません。`atof` が数値として読める先頭部分を変換するため、末尾の文字は無視されます。たとえば `0.35tail` は `0.35`、`nonsense` は `0` です（`engine/src/program/generate.cpp:20153-20156`）。

| 環境値 | 読み取り結果と gate |
|---|---|
| 未設定、空文字 | `pl_hit_min=-1`; θが未指定なら `pl_theta=0.2` となり、予測確率 `p_on >= 0.2` の gate |
| `0`、`0.0`、`0anything`、数値に変換できない非空文字 | `pl_hit_min=0`; θが未指定なら θ gate は無効化され、過去の on-path 率が 0 以上なら通過 |
| `0.35`、`0.35tail` | `pl_hit_min=0.35`; θが未指定なら確率帯の過去 on-path 率が 35% 以上で通過 |
| `1` | 過去 on-path 率が 100% の確率帯だけ通過 |
| `1` より大きい有限値 | 過去 on-path 率の上限は 100% なので通過しない |
| 負の有限値（例 `-0.1`） | 値自体は保存されるが `pl_hit_min >= 0` ではないため、θが未指定なら既定の θ=0.2 gate になり、この値は gate に使われない。θが明示的に負なら counted gate になり、負の下限との比較は通る |
| `nan` | `atof` の NaN。`>= 0` が偽となるため θが未指定なら θ=0.2 gate |
| `inf` | `pl_hit_min >= 0` が真となり counted gate に切り替わるが、有限の過去 on-path 率は `inf` 以上にならないため通過しない |

比較は `pl_cal.on[row] >= hit_min * pl_cal.n[row]` です。確率帯は chain の `p_on` を 10 分割して 0〜9 行、lookup continuation は専用の 10 行目にします。既定の校正表は各行 24 件分の事前値で初期化され、実行中の観測結果で更新されます（`engine/src/program/generate.cpp:21747-21765`）。

`STRATA_PIPELINE_THETA` は `pipe_dbg_env` 経由なので、`STRATA_PIPELINE_DEBUG` が未設定・空文字・`0...` 始まりなら参照されません。参照される場合は `atof` され、`pl_theta >= 0` なら `STRATA_PIPELINE_HIT_MIN` より θ gate が優先されます。θが参照されず未指定で対象値が非負なら counted gate、対象値が負または NaN なら θ=0.2 が選ばれます。θの非数値文字列は `atof` により 0 となるので θ gate (`p_on >= 0`) です。明示的な負の θ は counted gate を選び、対象値が負でも比較条件を満たします（`engine/src/program/generate.cpp:679-685, 20153-20160, 21761-21765`）。

## 有効になる条件

- 変数値が非空かつ `atof` 結果が 0 以上である場合に counted gate が選ばれます。ただし、デバッグ有効時の `STRATA_PIPELINE_THETA` が 0 以上なら θ gate が優先します（`engine/src/program/generate.cpp:20153-20160, 21761-21765`）。
- pipeline windows が実際に選択される必要があります。自動選択は `--serve`、複数 GPU の layer split、draft/MTP および `--spec >= 2` などに依存し、HIP では architecture 条件もあります。明示設定でも `--serve`、別 GPU 上の各 stage、必要な draft、`--spec`、helper cache や `--peer-device` などの制約があります。条件不足なら `--pipeline-windows ... is off: ...` の理由ログを出して無効化します（`engine/src/program/generate.cpp:6527-6554, 6556-6573`）。
- Decode の pipeline は `pipe && pl_pw >= 2 && pl_snap_ok` が必要です。反復ペナルティ (`hist_n > 0`) または coupled draft sampling の request は serial decode になり、その理由を一度 stderr に出します（`engine/src/program/generate.cpp:21696-21715`）。
- `STRATA_PIPELINE_SWITCH` がデバッグ有効で、pipeline が有効な場合、各 request で読まれる switch ファイル中の `hit=<f>` がこの値を上書きします。`hit=` があり `theta=` が無ければ counted gate に切り替えます。両方あれば `theta` が gate を選びます。この動的 switch は当該環境変数の通常値ではなく、後段の明示的な上書きです（`engine/src/program/generate.cpp:20139-20142, 20178-20196`）。

## 実行時の詳細

対象値は各 request の prompt/window 処理に入る前後の共通処理で一度読み取られ、decode pipeline の gate で使われます。prompt の pipelined verify windows 自体はこの gate を参照しません。関数内 `static` cache ではありません。次の request では再評価されますが、request 処理中の環境変更はその request の値へ反映されません。switch ファイルの設定は別途、request ごとに読み直されます（`engine/src/program/generate.cpp:20117-20118, 20139-20159, 20178-20197, 21744-21765`）。

counted gate は chain の予測 `p_on` の decile（または lookup 専用行）ごとに蓄積した on-path 件数と件数合計を比較します。window が gate を通らなければ `B.ready=false` とし、投機 launch を行わず gate 未通過数を増やします。通れば stage 0 が次の window を投機的に実行し、予測が外れたときは state を戻して実際の token で処理する rollback 経路を取ります（`engine/src/program/generate.cpp:21747-21765, 21875, 22239-22253, 22324-22330`）。

## ログと測定値

この環境変数単独の設定値ログや無効値警告はありません。`STRATA_DECODE_TIMING` が設定されていると pipeline 終了時の stderr 統計に gate 名と値（`hit %.2f`）が表示されます（`engine/src/program/generate.cpp:22476-22488`）。デバッグ有効かつ switch ファイルを開けた場合は `strata pipeline switch: ... hit=...` が stderr に出ます（`engine/src/program/generate.cpp:20178-20196`）。

ソースコメントには 2x RTX 3090、250 W での 0.2 / 0.3 / 0.4 の比較として serial loop 比 +7.0% / +7.8% / +7.5% とありますが、モデル、OS/backend、測定回数など条件が揃っていないため、一般的な性能値とは扱いません（`engine/src/program/generate.cpp:20143-20149`）。`docs/MULTI_GPU.md` は `STRATA_PIPELINE_*` tuning/test variables は `STRATA_PIPELINE_DEBUG=1` のときだけ読むと記載していますが、この変数は同ファイル内で直接 `std::getenv` されるため、その一般記述は本変数には当てはまりません（`docs/MULTI_GPU.md:203-203`, `engine/src/program/generate.cpp:20153-20156`）。

## 根拠

- `engine/src/program/generate.cpp:679-685` — `pipe_dbg_env` のデバッグ判定と対象変数が helper を経由しないこと。
- `engine/src/program/generate.cpp:20139-20197` — request scope の読み取り、既定値、値変換、theta と switch の上書き。
- `engine/src/program/generate.cpp:21696-21715, 21747-21765` — decode pipeline 条件と gate の比較。
- `engine/src/program/generate.cpp:21875, 22239-22253, 22324-22330` — gate の結果、speculative launch、校正データ。
- `engine/src/program/generate.cpp:22476-22488` — decode timing の gate 統計。
- `engine/src/program/generate.cpp:6527-6573` — pipeline windows の自動選択、前提条件、無効化ログ。
- `docs/MULTI_GPU.md:203-203` — tuning/test 変数に関する文書記述。
