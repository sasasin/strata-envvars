# `STRATA_Q36_PEER_FIXED`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 engine の peer tier について、起動時の expert profile 等で決まった配置を実行中の適応的な再配置から固定する。`peer_rebalance()` は変数が設定されていると早期 return するため、peer GPU の slot に入った expert を routing count に応じて入れ替えない。初期配置を選ぶ変数ではなく、peer tier 自体やそこにある expert の計算を無効にするものでもない。CUDA device への peer tier が開かれ、hybrid mode で実行するときに関係する。実装は `engine/src/qwen35/q36_engine.cu` の `Engine::peer_rebalance()`。Qwen3.6 は NVIDIA / AMD 向けの独自 engine path で、Intel Arc と Mac の engine は対象モデルを実行しないと資料に記載されている（`docs/QWEN36.md:7-9`）。

## 値と判定

`std::getenv("STRATA_Q36_PEER_FIXED") != nullptr` の有無だけを判定し、文字列の内容は変換・比較しない（`engine/src/qwen35/q36_engine.cu:3506-3511`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `peer_rebalance()` が実際に到達する場合 | 再配置を許可 | 空文字、`0`、`1`、`false`、`anything` を含む、環境変数が存在する任意の値 | なし（未設定だけが再配置を止めない） |

空白、大文字小文字、数値としての妥当性は調べない。CLI 引数による上書きや値ごとの fallback はない。設定時は関数内 `static const bool` が初期化されるため、そのプロセスで以後変更しても反映されない。初期化より前に環境を設定する必要がある（同 `3506-3511`）。

## 有効になる条件

- Qwen3.6 engine の実行経路であること。資料では Qwen3.6 が `engine/src/qwen35` の独自経路で NVIDIA / AMD で動作するとされ、Intel Arc と Mac は対象外（`docs/QWEN36.md:7-9`）。
- engine が hybrid mode であること。`after_rows()` は `m->hybrid` が false なら戻り、peer の再配置もそこからのみ呼ばれる（`engine/src/qwen35/q36_engine.cu:1878-1885`）。
- peer tier が初期化済みであること。`peer_rebalance()` は `peer.comp`、`peer.arena`、正の slot 数および layer ごとの slot 表を要求し、満たさない場合は環境変数の判定前に戻る（同 `3506-3511`）。peer tier は `--peer-device` が指定された場合に開かれ、配置処理は `open_peer_tier()` を呼ぶ（同 `4077-4079`, `4345-4349`, `4390-4392`）。
- 初期配置は別の処理で行われる。`--expert-profile` があれば profile の順位を使い、なければ expert index 順で slot を埋める。この変数はその後の再配置だけを止める（同 `4091-4109`, `4179-4200`, `3505-3511`）。
- routing count による再配置は decode / verify の確定行数を数え、`pos % 32 == 0` の境界で試みる。`warming` または `rows_deferred` の間も `peer_rebalance()` は戻る（同 `1866-1885`, `3506-3511`）。
- `STRATA_Q36_PEER_SWAPS`、`STRATA_Q36_PEER_SWAP_MIB`、`STRATA_Q36_PEER_SWAP_QUIET` は再配置時の swap 数・コピー予算・ログを制御する別変数だが、固定が有効ならそれらを読む前に戻る（同 `3510-3524`）。
- GPU 0 側の slot 適応は別関数 `rebalance()` であり、この変数では止まらない。そちらには別の `STRATA_Q36_FIXED_SLOTS` 判定がある（同 `3445-3448`, `3510-3511`）。

## 実行時の詳細

peer tier の初期配置は profile の順位（profile がない場合は index 順）から構成される。その後 `after_rows()` は hybrid mode で確定した routing count を記録し、位置が32の倍数になると GPU 0 の同期と slot 再配置を行った後、`peer_rebalance(8)` を呼ぶ（`engine/src/qwen35/q36_engine.cu:1878-1885`, `4091-4109`, `4179-4200`）。peer 関数では tier の有無を確認してから環境変数を一度だけ読み、設定されていれば `warming` / `rows_deferred` の判定も含む再配置処理を行わず戻る（同 `3506-3511`）。

未設定で再配置が実行される場合は、各 layer で両 GPU のどちらにもない expert の routing count と peer slot の resident expert の count を比べ、より多く要求された expert を最大 `min(8, STRATA_Q36_PEER_SWAPS)` 件まで選び、host arena から peer GPU の対応 slot へ blob を非同期コピーする。既定の swap 上限は1 layer あたり4件、負数は0に丸める。1回の再配置のコピー予算も `STRATA_Q36_PEER_SWAP_MIB`（既定512 MiB）で制限する（同 `3512-3523`, `3531-3579`）。固定が有効な場合、この peer slot の交換、対応する blob コピー、および交換ログは発生しない。通常の peer tier による expert 計算や GPU 0 側の処理は引き続き別経路で行われる。

## ログと測定値

この変数自体の有効・無効ログはない。設定時は peer swap のループに入らず、1交換ごとの `strata-q36: peer swap ...` と、交換数が正の場合の集計行 `strata-q36: peer tier: ...` もこの関数からは出ない（`engine/src/qwen35/q36_engine.cu:3510-3511`, `3574-3587`）。初期 tier の配置ログなど、別処理のログはこの判定対象ではない。変数の効果を切り分けた測定値は、参照したコード・資料に見当たらない。

## 根拠

- `engine/src/qwen35/q36_engine.cu:1866-1885` — 確定行の count と32位置ごとの peer 再配置呼び出し。
- `engine/src/qwen35/q36_engine.cu:3505-3511` — 固定判定と早期 return。
- `engine/src/qwen35/q36_engine.cu:3512-3524`, `3531-3587` — 関連する peer swap 設定、交換処理とログ。
- `engine/src/qwen35/q36_engine.cu:4077-4109`, `4179-4200`, `4345-4392` — peer tier の条件、初期配置、hybrid mode での呼び出し。
- `docs/QWEN36.md:7-9` — Qwen3.6 engine の対象 backend とモデル経路。
