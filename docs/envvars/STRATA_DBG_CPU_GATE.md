# `STRATA_DBG_CPU_GATE`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（`2026-10-12` 時点）。

## 役割

短いプロンプトの prefill で CPU expert share の自動判定が行う計測ログを `stderr` に出す診断用環境変数。自動判定が記録したレイヤーの所要時間、非 resident expert 数、expert あたりの時間、および後続レイヤーに対する gate の選択（`share` / `do not share`）を表示する。CPU share の有効化や割合の指定には使われず、ログ出力以外の処理を変えない。

## 値と判定

| 環境変数の状態 | 判定 | 結果 |
| --- | --- | --- |
| 未設定 | `std::getenv(...) == nullptr` | ログを出さない |
| 空文字を含む何らかの値が設定済み | `std::getenv(...) != nullptr` | ログを出す |

値の文字列や数値への変換はない。従って `0`、`false`、任意の文字列も設定済みとして扱う。無効値や範囲の概念もない。

## 有効になる条件

- `src/prefill/prefill.cpp` の CPU share 対象レイヤー処理に入り、前の対象レイヤーについて wall time が保留されていること（`m.pend_wall` が真）。保留対象は自動判定で選んだ arm のうち、非 resident expert があり、計測対象処理が share による cold start ではないレイヤー。
- CUDA event の経過時間取得 `cudaEventElapsedTime` が成功すること。
- CPU share の自動モードであること。自動モードでは対象レイヤーの CPU share 可否を測るため wall-time 計測が設定される。固定割合や share 無効時はこの自動判定用ログ経路に入らない。
- CPU share 自体の適用条件を満たす必要がある。この変数だけでは CPU share を有効にしない。例えば CPU pool が保持され、レイヤーが対象となり、バッファ確保などで share が無効化されていないことが前提になる。

## 実行時の詳細

ログは `m.pend_wall` の処理で、event 計測に成功した後に出る。形式は次のとおり（実装文字列）。

```text
cpu gate: layer %d %s, %lld non-resident, %.2f ms (%.4f a expert) -> %s
```

`%s` は実行済みレイヤーが `shared` か `not shared` か、および現在の gate が後続で `share` を選ぶか `do not share` を選ぶかを示す。wall time と expert あたりの時間は `m.pend_wall_n`（非 resident expert 数）で割った値。

自動 share は最初の比較が揃うまでは対象レイヤーを交互に share / 非 share とし、同じ chunk 内の隣接する異なる arm の測定から比率を作る。最大5個の比率の中央値が1未満なら `m.cpu_gate` を share 側にし、以降はその arm を選びつつ29レイヤーごとに反対側を計測する。これは診断ログの対象となる gate の本体であり、`STRATA_DBG_CPU_GATE` 自身はこの選択を変更しない。

環境変数は `if` 内の関数ローカル `static const bool` 初期化子で最初にそのログ箇所へ到達した時に一度だけ読み取られる。同一プロセス内で後から環境を変更しても、このログ判定には反映されない。ログ条件が成立した回ごとに `stderr` へ1行出力する。起動時の設定表示や子プロセスへの転送はこの変数について実装されていない。

## 根拠

- `src/prefill/prefill.cpp:3149-3153` — 変数の唯一の直接参照、設定有無による分岐、`stderr` のログ文字列と引数。
- `src/prefill/prefill.cpp:801-816` — wall-time の保留状態、自動判定の履歴、`cpu_gate` の状態。
- `src/prefill/prefill.cpp:3075-3085` — 自動モードでの計測設定、初期交互 arm と CPU share 適用条件。
- `src/prefill/prefill.cpp:3136-3158` — event 経過時間の取得、比率・中央値による gate 更新、ログ出力。
- `src/prefill/prefill.cpp:3188-3190` — gate で選んだ arm が CPU に渡す expert 数へ反映される箇所。
- `src/prefill/prefill.cpp:3881-3888` — 自動判定の wall-time 計測対象となる条件と、次の読み取りで消費する計測値の保存。
- `docs/DETAILS.md:1541-1557` — CPU share の自動計測、最初の比較と29レイヤーごとの反対 arm 計測、適用範囲・条件の説明。`STRATA_DBG_CPU_GATE` 自体の説明はなく、本文はソースの判定ロジックと照合した。
