# `strata-hy4-sycl --spec-k`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（SYCL） |
| オプション | `--spec-k` |
| 別名 | なし |
| 値 | 整数。DFly2 speculative decoding で1ブロックに draft するトークン数。構築時に1〜7へ補正される |

## 役割

DFly2 drafter が1回に作る draft の最大深さを指定する。既定値は5で、設定値は適応型の検証窓選択や固定窓の上限として使われる。実際の生成では context の残量、バックオフ状態、draft の可否によって、指定値より短い窓になるか通常の1トークン decode に切り替わることがある（`engine/src/hy4flash/sycl/sy_spec.h:21-30, 175-205`）。

## 使い方

```sh
strata-hy4-sycl --model model.strata --tokens prompt.ids --gen 128 --draft dfly2 --spec-k 5
```

`--spec-k` は値を次の引数に渡す。通常の一括生成では `--draft dfly2` と `--gen` が必要で、サーバーモードでは `--draft dfly2` または条件を満たす `--draft auto` によって speculative decoding が有効になる（`engine/src/hy4flash/sycl/sy_main.cpp:107-116, 180, 250-253, 279-280`; `engine/src/hy4flash/sycl/sy_serve.h:248-278`）。

## 値と既定値

`SpecCfg::K` の初期値は5。parser は `atoi` で次の引数を整数化し、数値形式や範囲を個別には検証しない。`Spec` の構築時に7より大きい値は7へ、1未満の値は1へ補正する。このため、整数として読めない文字列は `atoi` の結果0となり、最終的に1として扱われる。値の欠落時は `ERR --spec-k needs a value` を標準出力へ出して終了コード2で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:107-116, 180`; `engine/src/hy4flash/sycl/sy_spec.h:21-30, 65-72`; 上限7は `engine/src/hy4flash/sycl/sy_dfly2.h:183-185`）。

同じオプションを複数回指定した場合、parser は引数を順に処理して `scfg.K` を更新するため、最後の値が残る（`engine/src/hy4flash/sycl/sy_main.cpp:105-116, 180`）。

## 実行時の動作

`--spec-k` の値は `SpecCfg::K` に格納され、`Spec` が作られるときに上記の範囲へ補正される。各生成反復で `Kd` にこの値を設定し、context 上限に近い場合は `max_ctx - a - 3` まで縮める。環境変数 `HY4S_CLAMP32=1` かつ `--spec-check` 無効、適応型 VRAM cache 有効の条件では、次の32-token 境界を越えないようさらに短縮する（`engine/src/hy4flash/sycl/sy_spec.h:65-72, 175-187`）。

`Kd < 1`、drafter が利用できない、または `DFly2::can_draft` が位置・容量条件を満たさない場合、その反復では通常の1トークン decode を行う。draft 可能な場合は `Kd` を `draft_tree` に渡し、生成する木のノード数を最大 `min(Kd + 1, 8)` に制限する（`engine/src/hy4flash/sycl/sy_spec.h:181-208`; `engine/src/hy4flash/sycl/sy_dfly2.h:183-185, 583-589, 789-795, 888-909`）。

既定の adaptive モードでは、信頼度・推定受理数・測定済み検証時間に基づいて検証窓を選ぶため、`--spec-k` は draft の深さの上限となる。`--spec-fixed` を併用すると adaptive 選択を無効にし、作成された木の全ノードを検証する。context 制限などで木が短くなれば、その短い窓が対象になる（`engine/src/hy4flash/sycl/sy_spec.h:23-24, 88-104, 181-216`）。

## 適用条件と副作用

一括生成では `--draft dfly2` かつ `--gen` が1以上の場合に `Spec` が生成され、値が decode に使われる。`--draft` の既定値は `off` なので、`--spec-k` だけでは speculative decoding は有効にならない。`--gen` が0の場合も `Spec` の実行経路には入らない（`engine/src/hy4flash/sycl/sy_main.cpp:250-253, 279-280, 310-317, 379-386`）。

サーバーモードでは `--draft dfly2`、または drafter tensor を持つモデルで `--draft auto` を使い、chunk が8以上の場合に `Spec` が作られる。`--draft dfly2` で drafter がない場合や chunk が8未満の場合はエラーとなる。`--draft auto` で speculative decoding が有効にならない場合、`--spec-k` は使われない（`engine/src/hy4flash/sycl/sy_serve.h:248-278, 303-307`）。サーバー起動時の `INFO` 行に出る `draft_window` は入力値 `o.spec.K` を表示する一方、実際の `Spec` はコピーを1〜7に補正して使う（`engine/src/hy4flash/sycl/sy_serve.h:303-307, 331-333`; `engine/src/hy4flash/sycl/sy_spec.h:65-72`）。

一括生成で speculative decoding が動いた場合、生成 ID は標準出力にも出力され、`--out` のディレクトリに `gen_ids.txt` を作成する。既存ファイルがあれば `std::ofstream` で開く際に切り詰められる。これは speculative decode の経路全体の副作用であり、`--spec-k` 単独によるファイル操作ではない（`engine/src/hy4flash/sycl/sy_main.cpp:379-408`）。

## 出力とエラー

DFly2 の初期化後、一括生成では標準エラーに `[dfly2] drafter ready (K=..., ...)` を出す。この表示は `Spec` 構築前の入力値を使うため、1〜7の範囲外を指定すると表示値と実効値が異なることがある。decode 後の `[spec] K=...` 統計行は補正後の設定を表示する（`engine/src/hy4flash/sycl/sy_main.cpp:310-317, 379-406`; `engine/src/hy4flash/sycl/sy_spec.h:65-72, 414-419`）。

引数が欠けている場合は `nxt()` が標準出力へエラーを出して終了コード2で終了する（`engine/src/hy4flash/sycl/sy_main.cpp:107-116`）。値そのものの範囲外エラーはなく、構築時に補正される。draft 実行または検証中の失敗は `finish == "error"` となり、一括生成では `spec: <理由>` を標準エラーへ出して終了コード1で終了する（`engine/src/hy4flash/sycl/sy_spec.h:201-208, 239-249`; `engine/src/hy4flash/sycl/sy_main.cpp:386-391`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:107-116, 180` — 引数取得、値の変換、欠落時の終了処理、parser 登録。
- `engine/src/hy4flash/sycl/sy_spec.h:21-30, 65-72` — 既定値と `Spec` 構築時の1〜7への補正。
- `engine/src/hy4flash/sycl/sy_spec.h:88-104, 175-216` — adaptive/fixed の検証窓選択、context・環境条件による縮小、plain decode への切替。
- `engine/src/hy4flash/sycl/sy_dfly2.h:183-185, 583-589, 789-795, 888-909` — DFly2 の最大値、draft 可否、`K` に基づく draft 木の深さとサイズ。
- `engine/src/hy4flash/sycl/sy_main.cpp:250-253, 279-317, 379-408` — 一括生成での有効条件、ログ、生成 ID の出力先。
- `engine/src/hy4flash/sycl/sy_serve.h:248-278, 303-307, 331-333, 468-475` — サーバーでの drafter 判定、`Spec` の生成、起動情報、生成リクエストでの利用。
