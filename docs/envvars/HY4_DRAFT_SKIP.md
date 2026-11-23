# `HY4_DRAFT_SKIP`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Hy4-Flash の DFly2 drafter 内の一部計算段階をビットマスクで飛ばす、debug/bisect 用のスイッチです。通常は未設定で `skip == 0` となり、各段階を飛ばしません。変数は `DFly2` オブジェクトの `skip` メンバー初期化時に読みます（`engine/src/hy4flash/run/hy4_dfly2.hip.h:410-416`）。

DFly2 は通常の推論そのものではなく、`--draft dfly2`（通常 CLI）または `--draft` が `off` 以外の serve 経路でモデルに drafter があり、serve chunk が 8 以上の場合に初期化されます。serve では初期化に失敗した場合も警告して drafter なしで続行します（`engine/src/hy4flash/run/hy4_main.hip.cpp:701-715`、`engine/src/hy4flash/run/hy4_serve.hip.h:319-341`）。

## 値と判定

`getenv` が null のときだけ 0、それ以外は `atoi(getenv(...))` の結果を使います。したがって未設定と空文字はいずれも 0 です。`atoi` のため、先頭の空白と符号は数値変換に含まれ、数値の後ろの文字列は検査されません。例として `2x` は 2、`0anything` と `true` は 0 になります。全体一致、大文字小文字、数値文字列の末尾、範囲を検証する処理はありません。負値も拒否されず、整数として得られた後に各ビットとの AND 判定に使われます（同 `:416`、各判定は `:743-797,807-812,970-1024,1030`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| DFly2 の通常経路 | 0。以下の段階スキップなし | 整数値の各ビットを判定。1: 5 層、2: base-logit pass、4: `draft()` の chain loop、8: attention/KV 処理、16: MLP 射影、32: attention 射影、64: MLA workspace 確保をスキップ | 「無効値」の検査・拒否はない。`abc` や空文字は `atoi` で 0。既知のビットを含まない非ゼロ値（例: 128）は各段階をスキップしないが、graph 経路の条件からは外れる |

各ビットは `skip & mask` で独立に判定されるため、複数のビットを足した値も組み合わせとして作用します。コメントに列挙された 1/2/4 のほか、コードでは 8/16/32/64 も使われています（`engine/src/hy4flash/run/hy4_dfly2.hip.h:743-797,807-812,970-1024,1030-1034`）。

## 有効になる条件

- 変数を読むのは DFly2 の `DFly2` オブジェクト構築時です。通常 CLI では `engine/src/hy4flash/run/hy4_main.hip.cpp:711-715`、serve では `engine/src/hy4flash/run/hy4_serve.hip.h:319-341` に構築・初期化経路があります。
- 実際の段階スキップが行われるのは `draft()` または `draft_tree()` が実行されるときです。通常の speculative `Spec::run` は `draft_tree()` を呼びます（`engine/src/hy4flash/run/hy4_spec.hip.h:284-313`）。
- `draft()` は `--dfly-warm` の warm-up 経路などで使われます。ビット 4 はこの関数の chain loop を止めますが、通常の `draft_tree()` の候補展開ループにはその判定がありません（`engine/src/hy4flash/run/hy4_main.hip.cpp:374,435,1024-1029`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:807-812,1121-1154`）。
- serve で `--draft off` の場合は DFly2 を初期化せず、`--draft auto` / `dfly2` では `r.Tc >= 8` の場合に初期化を試みます。モデルに DFly2 tensor がない、または必要 VRAM が不足する場合は serve が drafter なしで続きます（`engine/src/hy4flash/run/hy4_serve.hip.h:321-336`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:470-482`）。
- `HY4_HAS_GRAPHS` が有効な build でも、`skip == 0` が graph 経路の条件です。したがって既知のビットを含まない 128 などの非ゼロ値も graph 経路を外し、通常の非 graph 経路になります（`engine/src/hy4flash/run/hy4_dfly2.hip.h:600-601,855-856`）。
- CLI の `--draft` は DFly2 を使うかを選びますが、`HY4_DRAFT_SKIP` の値を上書きする処理は見つかりません。`--spec-nodraft` の場合は `Spec::run` 側で DFly2 呼び出しを通らない経路があります（`engine/src/hy4flash/run/hy4_main.hip.cpp:406,428`、`engine/src/hy4flash/run/hy4_spec.hip.h:284-310`）。

## 実行時の詳細

環境値は DFly2 インスタンスごとにメンバー初期化で一度読み、`draft()` / `draft_tree()` はその保存値を参照します。実行中に環境を変更しても既存インスタンスには反映されません。名前を動的に渡す helper を介した別読み取りはなく、ソース全体の完全一致検索でも読み取りは `engine/src/hy4flash/run/hy4_dfly2.hip.h:416` のみでした。

ビット 1 は 5 層ループを 0 回にしますが、fusion と final norm はループ外に残ります。ビット 8 は KV 書き込み・query 準備・attention・value projection、16 は MLP gate/up/down projection、32 は attention projection の一部、64 は MLA workspace 確保をそれぞれ条件付きで飛ばします。これらの処理は `draft()` と `run_block_backbone()` の両方にあります（`engine/src/hy4flash/run/hy4_dfly2.hip.h:733-800,962-1027`）。

ビット 2 は `N > 0` のときに base-logit 計算と top-N 候補生成を止めます。通常 `draft()` の後続 chain と `draft_tree()` の候補評価は引き続き候補配列を使うコード経路があるため、スキップ時にはこの計算で生成する候補データが更新されません。ソースはこの組み合わせに対する検証済み結果や fallback を示していません（同 `:807-810,1030-1035`、`engine/src/hy4flash/run/hy4_spec.hip.h:1157-1166,1195-1199`）。ビット 4 では `draft()` の chain loop を止めますが、同関数はその後も chain/confidence バッファを読み取ります。同 `:812-839`。

## ログと測定値

`HY4_DRAFT_SKIP` の値やスキップしたビットを報告する専用ログはありません。値が非ゼロなら graph 条件を外れますが、その切り替え自体のログも該当コードにはありません（`engine/src/hy4flash/run/hy4_dfly2.hip.h:600-601,855-856`）。この debug 用スイッチに関する条件付き測定値は確認できません。

## 根拠

- `engine/src/hy4flash/run/hy4_dfly2.hip.h:410-416` — `DFly2::skip` の読み取りと既定値。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:600-601,733-812,834-839` — graph 条件と通常 `draft()` の各ビット分岐・戻り値処理。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:846-856,962-1036,1121-1154` — `draft_tree()` 用 backbone と呼び出し。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701-715,1024-1029` — CLI の DFly2 初期化と warm-up 呼び出し。
- `engine/src/hy4flash/run/hy4_serve.hip.h:319-341` — serve 側の初期化条件と drafter なしで続行する分岐。
- `engine/src/hy4flash/run/hy4_spec.hip.h:284-313,1157-1199` — speculative tree 経路、候補評価、および失敗時の処理。
