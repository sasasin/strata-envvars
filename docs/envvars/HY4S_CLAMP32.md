# `HY4S_CLAMP32`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

SYCL 版 hy4flash サーバーの DFly2 speculative decoding で、適応型 VRAM expert cache が有効な場合に draft block の長さを次の 32-token 境界までに制限する。これにより、1 回の draft block がその境界をまたがないようにする。環境変数が変えるのは `Kd`（draft する token 数）の上限であり、通常の target 推論やサンプリング値の設定ではない（`engine/src/hy4flash/sycl/sy_spec.h:153-155,175-187`）。

## 値と判定

`Spec::run` 内で `std::getenv` の結果が非 null であり、かつその先頭文字が文字 `'1'` かを比較する。文字列全体の parse、数値変換、空白除去、大文字小文字変換はない（`engine/src/hy4flash/sycl/sy_spec.h:175`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL hy4flash の `Spec::run` | 無効 | 先頭が `'1'` の文字列。例: `1`, `10`, `1anything` | 空文字、`0`, `01`, `true`, ` 1`。先頭 1 文字が `'1'` でなければ無効 |

CLI 引数や設定ファイルからこの値を読む経路はなく、別の値への fallback もない。`--spec-check` は別の `cfg.check` 条件として clamp 分岐を無効にする（`engine/src/hy4flash/sycl/sy_main.cpp:179-185`; `engine/src/hy4flash/sycl/sy_spec.h:27,183`）。

## 有効になる条件

- SYCL hy4flash のサーバー経路で `Spec::run` が実行されること。サーバーでは `--draft off` でなく、モデルに DFly2 drafter tensor があり、chunk が 8 以上で、DFly2 の初期化に成功したとき speculative 経路が使われる。`--draft dfly2` で chunk が 8 未満の場合や drafter が無い場合はエラー経路になる（`engine/src/hy4flash/sycl/sy_serve.h:231-255,271-278,303-307,468-472`）。
- 生成上限が正で、画像リクエストではないこと。これらのときだけサーバーが `Spec::run` を呼ぶ（`engine/src/hy4flash/sycl/sy_serve.h:464-472`）。
- `--spec-check` が指定されていないこと（`engine/src/hy4flash/sycl/sy_main.cpp:179-185`; `engine/src/hy4flash/sycl/sy_spec.h:183`）。
- 有効な VRAM expert cache が存在し、かつその cache が adaptive であること。`Runner` には cache が active な場合だけポインタが設定され、`adaptive()` は active かつ `adaptive_` のとき true（`engine/src/hy4flash/sycl/sy_serve.h:280-288`; `engine/src/hy4flash/sycl/sy_vram_cache.h:648-650`）。
- `HY4S_VRAM_STATIC` の先頭文字が `'1'` のとき cache は adaptive ではなくなるため、この変数による clamp は働かない。未設定・空文字・`0`・`01` などではこの判定による static 化は起きない（`engine/src/hy4flash/sycl/sy_vram_cache.h:795`）。

## 実行時の詳細

サーバーは各生成要求で `Spec::run` を呼び、同関数は初回 token を出力した後、draft loop の前に環境値を一度読みローカルの `const bool clamp32` に保持する。従って 1 回の生成中に繰り返し環境を読み直すことも、関数 static にプロセス全体で cache することもない（`engine/src/hy4flash/sycl/sy_serve.h:468-472`; `engine/src/hy4flash/sycl/sy_spec.h:154-176`）。

各 draft loop では、まず `Kd` を `cfg.K` と context 上限で制限する。その後、環境値が有効で `cfg.check` が false、adaptive cache がある場合、次の 32-token 境界 `next_b` を求め、`a + 1 + Kd` がそこを越えるなら `Kd` を `max(0, next_b - a - 1)` に縮める。`Kd` が 0 になると `Kd < 1` により draft を使わない plain step に移る（`engine/src/hy4flash/sycl/sy_spec.h:177-199`）。

## ログと測定値

この環境変数を読んだことや clamp の発生を示す専用ログはない。既存の `[spec]` 統計は speculative / plain の実行状況を出すが、`HY4S_CLAMP32` の値や clamp 回数は記録しない（`engine/src/hy4flash/sycl/sy_spec.h:414-425`）。失敗時の経路は通常の speculative 処理と共通で、draft 失敗なら `finish = "error"` と `draft failed` が設定され、サーバーは `ERR spec: ...` を返して終了する。clamp 自体に固有の失敗・警告分岐はない（`engine/src/hy4flash/sycl/sy_spec.h:203-208`; `engine/src/hy4flash/sycl/sy_serve.h:470-475`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_spec.h:153-187` — 環境値の判定と 32-token 境界 clamp。
- `engine/src/hy4flash/sycl/sy_spec.h:187-199` — draft を使わない場合の plain step。
- `engine/src/hy4flash/sycl/sy_vram_cache.h:648-650,795-797` — cache の active/adaptive 判定と `HY4S_VRAM_STATIC`。
- `engine/src/hy4flash/sycl/sy_serve.h:248-255,271-288,468-475` — DFly2 経路と clamp 対象の呼び出し条件。
- `engine/src/hy4flash/sycl/sy_main.cpp:179-185` — `--spec-check` 設定。
