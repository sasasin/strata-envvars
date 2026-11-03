# `STRATA_METAL_F16`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Metal engine の decode window で、一部の量子化行列積と Q2_0 routed expert を fp16 経路で実行する opt-in 設定です。engine 自体の既定値は OFF です。Mac のセットアップは resident（SSD streaming ではない）IQ3_S / Q2_0 pack の config に `STRATA_METAL_F16=1` を記載しますが、これは engine の環境既定値ではありません。`metal_f16()` の結果を使って Metal kernel library のコンパイル定義、activation buffer の大きさ、dispatch を切り替えます（`metal/src/engine/window.cpp:119-124,691-741`）。

## 値と判定

| 環境値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 文字列が正確に `1` | ON |
| `0`、`true`、`01`、`1x`、空白を含む値など | OFF |

数値変換や trim はせず、`std::string(e) == "1"` の完全一致です。判定は関数内の `static const bool` に初回評価結果を保存するため、engine プロセス内で環境を書き換えても再評価されません（`metal/src/engine/window.cpp:122-124`）。CLI 引数による同じ設定の上書きはこの実装にはありません。

## 有効になる条件

環境値が `1` でも、fp16 window encoding は `head && !stream_ && !rows_` の場合だけ有効です。つまり head を含む resident decode window が対象で、SSD から expert を読む streaming 経路、head のない window（例: MTP draft 側）、および rows/batch-window 経路では使われません（`metal/src/engine/window.cpp:1413-1418`）。

この条件を満たす window でも、型や tile が対象外なら通常 GEMV に戻ります。dense GEMV の fp16 対象は Q2_0、Q3_K〜Q6_K、IQ4_XS で、さらに選ばれた tile が `gemv16_tile()` の登録 tile と一致する必要があります（`metal/src/engine/window.cpp:126-139,903-918`）。routed expert の `moe_gu16` / `moe_down16` は gate/up と down の両方が Q2_0 で、Hadamard の expert 入出力変換がない場合に限られます。streaming 中はこの条件も満たしません（`metal/src/engine/window.cpp:1188-1199,1229-1263`）。

Mac セットアップの `strata_control.mac_fit.engine_env()` は model 名（大文字小文字を無視）が IQ3_S または Q2_0 で、かつ `stream` が false の場合だけ `{"STRATA_METAL_F16": "1"}` を返します（`strata_control/mac_fit.py:59-66`）。セットアップはその値を `cfg["env"]` に書きます（`metal/setup_mac.py:548-553`）。サーバーの `child_env()` は親プロセス環境をコピーした後 config の `env` を反映するため、config にこのキーがあれば config 値が継承環境より優先します。config にキーがない場合は親環境の値が残ります（`serve/server.py:4054-4067`）。したがって、通常のセットアップ config では、外側の shell で `STRATA_METAL_F16=0` を設定するだけでは config の `1` を打ち消しません。config の値を `0` にすれば OFF になります。

## 実行時の詳細

Metal engine は `metal_f16()` が ON のとき `STRATA_METAL_F16` 定義つきで `quant.metal`、`units.metal`、`moe.metal`、`gemv.metal` などをコンパイルし、activation 用 buffer に half plane の領域を確保します（`metal/src/engine/window.cpp:691-699,734-741`）。window の head 有無、streaming、rows モードを評価して fp16 encoding を選び、対応する dense GEMV では `gemv16_...` kernel を dispatch します（`metal/src/engine/window.cpp:903-918,1413-1418`）。この経路の Metal kernel は重みと activation の一部を half で扱い、累積結果を float にします（`metal/kernels/gemv.metal:162-200`; 説明と演算は `metal/kernels/units.metal:324-328`）。

対象の Q2_0 routed expert では `moe_gu16_...` / `moe_down16_...` を選び、gate/up の half 出力を down kernel に渡します（`metal/src/engine/window.cpp:1229-1263`）。それ以外の条件では通常の `gemv_...` / `moe_gu_...` / `moe_down_...` 経路を使います。

この変数について、Strata は個別の有効・無効ログや無効値警告を出しません。window 初期化時の一般ログは device、モデルファイル、streaming/wrapped 状態、cell 数、PLE 状態を表示しますが、fp16 設定値は含みません（`metal/src/engine/window.cpp:870-872`）。対象外の型・window は通常経路へ進み、変数だけを理由とする終了・失敗処理は確認できません。

## 文書との照合

`docs/MAC.md:267` は resident window の dense GEMV 型と Q2_0 routed expert、setup が resident IQ3_S / Q2_0 に ON を書くこと、config の `=0` で無効化できることを説明しています。実装では engine の直接既定値は OFF で、setup が該当 config に `1` を記載します。コードで確認できる fp16 dispatch の条件は上記の通りです。性能値や品質比較は同文書記載の測定報告であり、この調査では再測定していません。

## 根拠

- `metal/src/engine/window.cpp:119-143,691-699,734-741` — 値判定、cache、Metal library 定義、half buffer。
- `metal/src/engine/window.cpp:903-918,1188-1199,1229-1263,1413-1418` — 対象型、tile、expert 条件、window の有効条件と dispatch。
- `metal/kernels/gemv.metal:162-223`, `metal/kernels/units.metal:324-328` — fp16 GEMV kernel と演算経路。
- `strata_control/mac_fit.py:59-66`, `metal/setup_mac.py:548-553` — setup が値を生成し config に書く条件。
- `serve/server.py:4054-4067` — 親環境の継承と config env による上書き。
- `docs/MAC.md:267` — Strata の説明資料との照合。
