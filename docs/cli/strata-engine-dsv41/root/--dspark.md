# `--dspark`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象リポジトリの状態は `main...origin/main` で、`git status --short --branch` に未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（root） |
| オプション | `--dspark` |
| 別名 | なし |
| 値 | `on`、`off`、`none`、`auto`（usage に記載）。値は必須 |

例: `strata-dsv41 --pack <model>/maya-ds4 --dspark auto --ids 1,2,3 --n 128`

## 効果

DeepSeek-V4.1 pack 内の `mtp.*` ブロックを drafter として扱い、通常の生成で DSpark speculative decoding を試すか、そのブロックをモデルにロードするかを指定します。`src/dsv41/ds4_main.cpp:1224-1229` では `off` のときだけ speculative decoding の試行フラグを下げ、`none` のときだけ drafter のロードフラグを下げています。このため `off` は「drafter をロードしない」という意味ではなく、`none` は「speculative decoding の試行を止める」という意味ではありません（`none` では drafter 自体が無効なので試行条件を満たしません）。

| 値 | speculative decoding の試行 | drafter のロード | 備考 |
| --- | --- | --- | --- |
| `on` | 有効 | 有効 | GPU 容量による `auto` の無効化を適用しません。 |
| `off` | 無効 | 有効 | モデル読込時に `g.n_mtp` を 0 にしないため、MTP 重みは通常どおりロード対象です。 |
| `none` | フラグ上は有効 | 無効 | MTP ブロックが無効になり、drafter を使う条件を満たさないため通常生成では通常の1ステップ生成に進みます（`draft_block()` は MTP block 数が正のときだけ pack の block size を返します。`src/dsv41/ds4_model.cu:9102`）。 |
| `auto` | 有効。ただし容量判定で無効化される場合あり | 有効。ただし容量判定で無効化される場合あり | 省略時もこの動作です。 |

usage が値候補を示す一方、parser は候補との照合・エラーを行いません。実装は文字列が `off` と一致するか、`none` と一致するか、`auto` と一致するかだけでフラグを設定します（`src/dsv41/ds4_main.cpp:85-93,1200-1208,1224-1229`）。したがって未知の値は拒否されず、`off` / `none` / `auto` のいずれにも一致しない値は `on` と同じフラグ状態になります。値を省略すると `--dspark needs a value` を stderr に出して終了コード 2 です（同 `:1202-1207`）。

## 既定値と適用条件

指定を省略した場合の `dspark` と `dspark_auto` はともに `true`、すなわち `auto` 相当です（`src/dsv41/ds4_model.hpp:42-48`）。`dspark_conf` は既定値 `0.5`、`dspark_block` は既定値 `0`（pack の block size を使用）です。これらは `--dspark` 自体の validation ではありませんが、実際に drafter を使う条件に関わります。

`auto` では、pack に MTP block がある場合に、routed expert の重み総量が利用可能な全 GPU メモリ（各 GPU の `--reserve-mib` 分を差し引いた量）の 1.5 倍を超えると drafter を無効化します。判定後 `g.n_mtp` を 0 にし、stderr に `DSpark not loaded` の理由を出します。`on` は `dspark_auto` が false なのでこの容量判定を回避し、drafter をロード対象に残します（`src/dsv41/ds4_model.cu:1997-2010`）。この処理はモデル読込時に行われるため、GPU / pack の状態によって `auto` の有効性が変わります。MTP block が pack にない場合、この容量判定は実行されません。

通常の生成では、残り生成枠が1より大きく、`m.draft_block() > 0` の場合に speculative round を試します。draft ごとの confidence が `--dspark-conf` 以上である間、最大で残り枠または draft 数まで検証し、採用 draft がなければ通常の1ステップ生成に戻ります（`src/dsv41/ds4_main.cpp:167-203,1397-1413`）。`--dspark-block N` は `N > 0` の場合に1 round の draft 上限を変えますが、`DS4_DSPARK_MAX` 環境変数が設定されている場合は CLI 値が反映されません（`src/dsv41/ds4_model.cu:2010`）。累積 confidence 閾値には環境変数 `STRATA_DS4_DSPARK_CUM` が使われ、未設定なら `0.0` です（`src/dsv41/ds4_main.cpp:152-162,179-183`）。

## モード、出力、失敗経路

`--dspark` は top-level parser のオプションです。通常の token 生成では上記の speculative round と、`spec` が真で round が発生した場合の stderr 統計表示に関係します（`src/dsv41/ds4_main.cpp:1385-1425`）。`--serve` では同じ起動時フラグが各 request の既定値になり、request の `spec=0|1` があればその request だけ上書きできます（同 `:211-212,318-323,892-900`）。`--spec-eval` でも起動時のフラグが使われます（同 `:1129-1164,1296-1301`）。

値の候補外であっても parser は拒否せず、その値に対応するフラグ状態でモデル読込へ進みます。未知の option は `unknown option ...` と usage を stderr に出して終了コード 2 です（`src/dsv41/ds4_main.cpp:1266-1272`）。`--pack` 等の必須条件を満たしていてもモデル読込が失敗すればエラーを stderr に出し終了コード 1 になります（同 `:1282-1294`）。`auto` の容量判定で drafter が抑止された場合は警告相当の stderr メッセージを出して通常の生成に進みます（`src/dsv41/ds4_model.cu:1998-2010`）。

## 根拠と調査範囲

- 索引は `strata-engine-dsv41` を `STRATA_BUILD_DSV41=ON` で生成する独立 engine CLI とし、`--dspark` を root scope に掲載しています（`docs/cli/README.md:1353-1362`）。ビルド条件と executable 定義も `CMakeLists.txt:797-812` で確認しました。
- parser と usage: `src/dsv41/ds4_main.cpp:85-93,1187-1273`。
- option 既定値: `src/dsv41/ds4_model.hpp:42-48`。
- drafter の容量判定とモデルへの反映: `src/dsv41/ds4_model.cu:1997-2010,9102`。
- speculative round と confidence / fallback: `src/dsv41/ds4_main.cpp:152-203,892-910,1385-1425`。
- 安全に実行できる同一 revision の既存 CLI バイナリは確認していないため `--help` は実行していません。usage 表記は parser ソースで照合しました。Release artifact の配布有無や個別 GPU 構成での実際の容量・速度はこのソース調査では確認していません。
