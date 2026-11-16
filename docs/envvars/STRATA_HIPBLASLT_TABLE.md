# `STRATA_HIPBLASLT_TABLE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。調査開始時の Strata 作業ツリーは `## main...origin/main` で、表示された未コミット変更はありませんでした。

## 役割

このスイッチは、HIP engine が起動時に engine パッケージ内の hipBLASLt tuning table を自動選択するかを決めます。table が使われると、対応する dense GEMM shape で hipBLASLt の solution ID を使います。table が使えない shape や無効な状態では通常の GEMM 経路へ戻ります。実装は HIP で `STRATA_HIPBLASLT_AVAILABLE` が定義された `src/prefill/gemm.cu` にあり、各 `Gemm` 初期化時に選択状態を作ります（`src/prefill/gemm.cu:21-60,276-338,696-718,767-790`）。

`STRATA_HIPBLASLT_TUNING` に非空のパスが設定されている場合、engine はそれを優先し、このスイッチを調べません。未設定または空のときだけ、このスイッチで engine 隣の `tuning/<arch>-hipblaslt-<version>.txt` を選ぶか判断します（`src/prefill/gemm.cu:276-293`）。セットアップ経路では `setup.py` の `hipblaslt_table()` が同じスイッチを `hipblaslt_tuning.switched_off()` 経由で参照し、off なら生成する設定にテーブルパスを入れません（`setup.py:5098-5119`; `strata_control/hipblaslt_tuning.py:148-164`; `strata_control/setup_config.py:432-442`）。

## 値と判定

engine は `getenv` の値を ASCII 空白で前後 trim し、小文字化してから文字列全体を比較します。数値変換はしません。次の表は C++ engine の判定です（`src/prefill/gemm.cu:278-293`）。

| 条件 | 値 | 判定 |
| --- | --- | --- |
| `STRATA_HIPBLASLT_TUNING` が非空 | 任意の値 | この変数を読まず、明示された tuning path を使用候補にする。`STRATA_HIPBLASLT_TABLE=off` でもこの優先順位は変わらない。 |
| `STRATA_HIPBLASLT_TUNING` 未設定または空 | `off`, `0`, `no`, `false`, `none`, `disable`, `disabled`（大文字・前後空白も同じ） | packaged table を使わず、state を作らない。 |
| 同上 | `on`, `1`, `yes`, `true`, `force`, `enable`, `enabled` | GPU architecture を問わず、engine 隣の一致する packaged table を探す。 |
| 同上 | 未設定、空文字、`auto` | 自動判定。`gfx1151` のみ既定で table を試し、他の architecture は選ばない。 |
| 同上 | 上記以外（例: `0anything`, `trueish`, `-1`） | 文字列全体が一致しないため `auto` と同じ扱い。 |

比較は大文字小文字を区別しません。前後の `isspace` 文字は取り除きますが、値の内部空白は残り、別の文字列として扱います。`0` は明示的な off、`1` は on です。空文字は off ではなく auto です（`src/prefill/gemm.cu:280-292`）。

サーバーの run config に限り、Python は環境値を trim・小文字化し、環境変数を config の `hipblaslt_table` boolean より先に解釈します。既知の off/on 語はそのまま反映し、環境値が未設定・空・`auto` のときだけ config の `true`/`false` が選択を上書きします。未知の文字列は Python 側では auto となり、boolean config にフォールスルーします。C++ engine へ渡す際、該当する boolean は `on`/`off` にコピーされます（`strata_control/hipblaslt_tuning.py:148-159,222-244`）。

## 有効になる条件

- engine が HIP でビルドされ、`__HIPCC__` と `STRATA_HIPBLASLT_AVAILABLE` の両方が有効であること。ほかの backend/build ではこの読み取りと state 初期化コードはコンパイルされません（`src/prefill/gemm.cu:21-60,712-718,785-790`）。
- 明示 `STRATA_HIPBLASLT_TUNING` がない場合、`on` または自動選択された `gfx1151` に対応する table が engine 隣の `tuning/` にあり、実 GPU architecture と hipBLASLt version に一致すること。一致するファイルがなければ通常経路です（`src/prefill/gemm.cu:303-338`）。
- auto の既定では architecture が `gfx1151` であること。その他の architecture は table が同梱されていても `on` が必要です（`src/prefill/gemm.cu:318-327`）。
- 実行中の shape、dtype、beta、workspace が table の solution を受け付けること。該当 row がない、solution が利用不可、shape が非対応、workspace 不足などではその GEMM が hipBLASLt table を使わず fallback します（`src/prefill/gemm.cu:341-400,403-435`）。
- server の component-engine 経路は config の backend が `hip` の場合に限り起動前に Python の適用処理を通ります。ここではインストール済み engine package と GPU architecture/version に基づきログを出し、config env を child environment に反映します（`serve/server.py:9817-9828,10175-10183`; `serve/server.py:4428-4441`; `strata_control/hipblaslt_tuning.py:185-244`）。直接 engine を起動する場合は Python 判定を通らず、C++ engine の判定が適用されます。

## 実行時の詳細

HIP `Gemm::init()` または `Gemm::init_external()` ごとに `create_hipblaslt_state()` が呼ばれます。関数は tuning path と switch を読み、必要なら hipBLASLt handle・version・GPU architecture を照会し、`<engine-dir>/tuning/<arch>-hipblaslt-<version>.txt` を探します。読み取り値はプロセス全体の static cache ではなく、この `Gemm` の state の生成時に評価されます。作成済み state は algorithm resolution の shape key を cache します。したがって後から環境値を書き換えても既存 state は再選択されません。新たに作られる `Gemm` state ではその時点の環境を読みます（`src/prefill/gemm.cu:202-225,257-338,341-400,712-718,767-790`）。

成功時は table の対応 row が示す solution ID を使った hipBLASLt GEMM を試みます。これは dense prompt GEMM の algorithm 選択を変えます。table row 不在・非対応・workspace 不足などなら `try_hipblaslt()` は false を返し、呼び出し側の既存経路を続けます（BF16: `src/prefill/gemm.cu:1095-1105`; FP16: `src/prefill/gemm.cu:1209-1218`; 判定: `src/prefill/gemm.cu:414-435`）。CUDA build や hipBLASLt が利用できない HIP build での挙動にはこの変数は関与しません。

サーバー component-engine の run config に `hipblaslt_table: true/false` がある場合、環境値が空で `cfg.env` に switch がないと `apply()` が複製 config の `env` に `on`/`off` を入れます。`cfg.env` の同名値が既にあれば追加しません。engine 起動時の child env は親環境を複製後、config の `env` を反映するため、config env は同名の親環境値より優先されます。このため config env に switch があるケースでは Python の選択判定（親環境を先に見る）と engine が受け取る値が異なる可能性があります（`strata_control/hipblaslt_tuning.py:238-244`; `serve/server.py:4428-4441,10175-10183`）。CLI 引数による同名設定はありません。

## ログと測定値

Python component-engine 経路では `[strata] hipBLASLt tuning table: ...` の形式で選択結果を出します。明示 off、table 非搭載、architecture/version 不一致、既定 auto で不使用の場合は理由または不使用の説明を含む行になります（`strata_control/hipblaslt_tuning.py:189-219,235-237`）。engine が table を読み込むと stderr に `prefill gemm: hipBLASLt tuning enabled (%zu rows, %s, version %d)` を出します。handle/version/device query 失敗時は、それぞれ `...; using hipBLASEx` のメッセージを出して table state を作りません（`src/prefill/gemm.cu:298-338`）。

`STRATA_HIPBLASLT_VERBOSE` が設定されていると、未対応 shape / solution、workspace不足、成功した solution、state 破棄時の fallback 集計を stderr に出します。これは別の変数で、今回のスイッチの値判定には影響しません（`src/prefill/gemm.cu:212-221,351-400,428-435`）。hipBLASLt launch 自体が失敗した場合は status を stderr に出します。beta が非ゼロなら fallback を拒否して `exit(1)`、beta が 0 なら当該 shape の cache を無効にして呼び出し元に fallback させます（`src/prefill/gemm.cu:450-462`）。

`docs/AMD_HIP.md` は同じく gfx1151 を既定、他の card は opt-in と説明し、table が GEMM の丸めに影響するとしています（`docs/AMD_HIP.md:82-93`）。この文書では独自の速度・正確性測定値を追加していません。

## 根拠

- `src/prefill/gemm.cu:21-60,202-225,257-338,341-400,403-462,696-718,767-790,1095-1105,1209-1218`
- `strata_control/hipblaslt_tuning.py:28-41,148-159,185-244`
- `setup.py:5098-5119`; `strata_control/setup_config.py:432-442`
- `serve/server.py:4428-4441,9817-9828,10175-10183`
- `docs/AMD_HIP.md:82-93`
