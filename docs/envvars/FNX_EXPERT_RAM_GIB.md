# `FNX_EXPERT_RAM_GIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリの環境変数は対象外。

## 役割

Flash-Next split engine の routed expert のうち、cold な expert を GPU VRAM の初期常駐分から外して RAM 上の mapped page-locked copy とし、GPU 側の expert cache に何 GiB 分を入れるか指定します。RAM 側の対象は個数ではなく重みサイズで選びます。値 `G` は「RAM に置く量」ではなく、その目標量です。デフォルトは 3 GiB です。

`docs/DETAILS.md:242-255` の低 RAM mode は通常 engine の setup option（`--resident-budget-gib` など）の説明で、この split engine 専用変数とは別の設定経路です。同資料にはこの変数名の直接説明はありません。

この値を読むのは `Model::choose_residency()` です。通常の plain load と、worker が expert を再配置する `place_experts()` から呼ばれます。`FNX_27B` build では plain load からこの関数を呼ばず、27B 用 `load_card` も residency/cache 引数を使わないため、この設定はその build には適用されません。

## 値と判定

| 環境値 | 判定と効果 |
|---|---|
| 未設定 | `3.0` GiB を目標にする。 |
| 厳密に `off` | cache を無効化する。`FNX_ARENA=0` も必要。 |
| 数値文字列 | `strtod` で変換し、文字列全体を消費し、負値でなければ受け付ける。単位は GiB。expert は分割されないため、目標を超えるところまで whole expert 単位で RAM 側に選ばれる。 |
| 空文字、数値に変換できない文字列、末尾に文字が残る文字列、負数 | エラー。先頭・末尾の空白を trim せず、`off` の大文字小文字も区別する。 |
| `nan` / `inf` など `strtod` が全体を変換する非有限値 | 有限性の検査がないため parse は通る。比較条件上全 routed expert が RAM 側に選ばれるが、その後 ExpertCache の必要 slot 数を満たせず model load は失敗する。 |

数値 `0`（および `-0`）は有効で、RAM 側に選ぶ expert はありません。これは `off` と異なり ExpertCache 自体を無効化しません。負数は reject されます。`strtod` が返す値に上限や clamp はありません。数値変換と判定は `src/split/src/model.cpp:1475-1490,1518-1525` にあります。

## 有効になる条件

- Flash-Next の CUDA split engine で、通常の non-27B model を plain load するか、保持済み host copy から worker が expert を配置する経路で有効です。model load 時の plain 経路と `FNX_27B` 条件は `src/split/src/model.cpp:1253-1267,1432-1443`、27B では `resident` を使わないことは `src/split/src/model.cpp:802-805` にあります。
- `FNX_EXPERT_RAM_GIB=off` は ExpertCache を作らず、expert 全体を VRAM に置く扱いです。ただしデフォルトの `FNX_ARENA` は有効であり、arena が cache の slot を K/V pool に貸す前提なので、`FNX_ARENA` が未設定または `1` のまま `off` を指定すると `FNX_EXPERT_RAM_GIB=off needs FNX_ARENA=0 (the arena lends the cache's slots)` で失敗します。`FNX_ARENA` は文字列 `0` / `1` のみ許可され、未設定は有効です（`src/split/src/model.cpp:1476-1488`）。
- 同梱の `strata_control.split_config()` は split engine 用の設定に `FNX_ARENA=0` と `FNX_EXPERT_RAM_GIB=off` を明示設定し、「全 expert を VRAM、cache なし」にします。serve は設定の `env` を子プロセス環境にコピーしてから engine を起動するため、この値が split engine に渡ります（`strata_control/split_engine.py:250-264`; `serve/server.py:4054-4067`）。
- Cache が有効な場合、対象 expert の順位づけに `FNX_EXPERT_PROFILE` を使います。未設定なら `FNX_DIR/data/expert-routes.bin` を開きます。profile は decode/prompt の tally を含む所定長の binary でなければ load が失敗します（`src/split/src/model.cpp:1490-1517`）。
- 指定値が有効でも、VRAM に残る expert cache の pool が window に必要な `2 * MAXT * TOPK` slot より少ないと ExpertCache 作成時に失敗します（`src/split/src/model.cpp:347-361`）。`FNX_ARENA` 有効時は engine が free VRAM を調べ、不足分の cold experts を追加で RAM 側に移して再配置します。8 回再試行しても足りなければエラーです（`src/split/src/engine.cu:276-315`）。

## 実行時の詳細

`choose_residency()` は呼ばれるたびに `getenv` で値を読み直し、static cache はありません。plain load ではモデルの host weights を stage した後に residency を決めます。worker の再配置では `place_experts()` が先に読み直します。通常の `sfnx` は起動時に `fnx::Model` を作るため、そのモデルの初期設定は起動時に決まります。CLI 引数による上書きはこの環境変数の実装にはありません（`src/split/src/model.cpp:1441-1443,1550-1565`; `src/split/tools/sfnx.cpp:1050-1059`）。

profile の expert score を bytes で割った値で昇順に並べ、最も cold な expert から、累積サイズが指定 GiB 以上になるまで選びます。`ram_extra` が増えている場合はその数だけ追加で選びます。選ばれた expert は host copy を持ち、VRAM cache slot には初期時点で選ばれなかった hot expert が入ります。decode window で VRAM slot にない expert は RAM copy から slot にコピーされます（`src/split/src/model.cpp:1501-1528`; `src/split/src/model.hpp:82-112`）。

通常の結果は stderr の `fnx: N of M routed experts (G GiB) in RAM, ranked by PROFILE` 行で観測できます。`off` と `FNX_ARENA=0` の場合、この cache 選択・集計ログは出ません。値・arena・profile・slot 不足の例外は呼び出し元に伝播し、`sfnx` のモデル load 中なら `sfnx: failed: ...` を stderr に出して終了コード 1 になります（`src/split/src/model.cpp:1486-1498,1527-1528`; `src/split/tools/sfnx.cpp:1030-1035,1050-1061`）。

## 根拠

- 読み取り、値判定、既定値、arena との制約、profile と cold expert の選択: `src/split/src/model.cpp:1469-1529`。
- load / 再配置時の呼び出し: `src/split/src/model.cpp:1432-1443,1550-1565`。
- ExpertCache が host copy と VRAM slot を使う構造: `src/split/src/model.hpp:82-112`; slot 数の下限: `src/split/src/model.cpp:347-361`。
- arena の VRAM 不足時の追加退避と失敗: `src/split/src/engine.cu:276-315`。
- split control による `off` / `FNX_ARENA=0` 設定と serve からの子環境への転送: `strata_control/split_engine.py:250-264`; `serve/server.py:4054-4067`。
- モデル load 失敗時の `sfnx` の stderr と終了: `src/split/tools/sfnx.cpp:1030-1035,1050-1061`。
