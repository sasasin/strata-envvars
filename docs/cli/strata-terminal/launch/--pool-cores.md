# `--pool-cores`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--pool-cores` |
| 別名 | なし |
| 値 | 論理プロセッサ番号のリスト。番号、範囲、`開始-終了:間隔` をカンマで連結 |

## 役割

実行エンジンの CPU expert worker を割り当てる論理プロセッサと順序を指定します。実験的な設定で、指定しない場合は engine の既定配置（物理コアごとに worker を置く方針）が使われます。設定はスレッドの配置に作用し、計算結果は変更しません。

## 使い方

```sh
strata launch --model q2_0 --pool-cores 2-14:2 --no-tui
```

`--model` など起動する選択と一緒に指定します。`strata launch` は `--pool-cores` だけでは起動対象を選んだ扱いにしないため、非対話実行ではモデルまたは preset も指定してください。`--plan` を付けると起動計画を表示して終了します。

## 値と既定値

- 例: `0,2,4,6`、`2-14:2`、`4-6`。範囲は昇順のみで、間隔を省略すると 1 です。
- `strata launch` parser は値の型変換をせず、空白文字のうち通常のスペースを除去してから、数字・カンマ・範囲・間隔の形式を検査します。タブや符号付き数値などは Terminal 側の形式検査を通りません。
- `--pool-cores` を省略した場合は設定を追加しません。Terminal parser 上で複数回指定した場合は最後の値が使われます。空文字は truthy 判定を通らず、設定追加も警告もありません。
- engine はリストを展開し、重複番号を一度だけ残します。空項目、逆順範囲、0 以下の間隔、数字以外、4096 個を超える展開結果など、読めない値は engine の既定配置に戻ります。

## 実行時の動作

Terminal は受理した値からスペースを除き、launch 設定の `extra` に `--pool-cores` として保存します。launch の実行設定作成時に `extra` は engine の `args` に反映され、engine は pool 作成前に CLI 値を読みます。値が空の場合に限り環境変数 `STRATA_POOL_CORES` を参照します。したがって CLI 値が空でなければ環境変数より優先されます。

有効な番号の順序は指定どおり保たれます。実行プロセスが利用できない、または存在しない論理プロセッサは除外されます。使える番号が一つも残らなければ既定配置になります。指定リストが worker 数の既定値になりますが、engine の `--pool-workers N` が別途設定されていればその数を優先します。N がリストより小さければ先頭 N 個を使い、大きければリスト以降の worker は CPU に pin されません。

同一物理コアの SMT sibling を複数指定した場合や、host thread と同じ CPU／コアを指定した場合も指定は維持され、競合について警告されます。engine は起動時に worker 配置を stderr に表示します。

## 適用条件と副作用

この設定は Terminal launch が選ぶ通常の Strata engine の CPU pool に適用されます。ソース内の `strata` engine は `--pool-cores` を解析し、CPU pool 構築前に設定します。Qwen3.6 は独自 engine path を使い、このオプションの対象外です。調査対象 checkout の Terminal launch 用カタログでは Qwen3.6 は Terminal の通常モデル一覧に含まれていません。

thread affinity の変更と、配置・不適用 CPU・SMT／host 競合に関する stderr 出力が副作用です。未使用または利用不能な番号が含まれても、それだけで起動を拒否する実装ではありません。性能向上は保証されず、既定の配置を変える実験的設定です。

## 出力とエラー

- Terminal の形式検査に失敗した値は拒否されず、その値を除外した旨と既定配置を使う旨の警告になります。`--plan` では warning として表示されます。
- engine のリスト parser が拒否した値も stderr に理由を出して既定配置を使います。
- プロセスから pin できない CPU は pool 初期化時に stderr の警告とともに除外されます。全番号が除外された場合は既定配置になります。
- `--pool-cores` に値を渡さない場合、argparse の必須値エラーになります（終了コードは Python argparse の標準処理）。

## 根拠

- 索引上の配置と option scope: `docs/cli/README.md`（`strata-terminal` → `strata launch`）。
- Terminal parser と help 説明: `strata_cli/launch/cmd.py:75-82,115-118`。
- Terminal 側の値正規化・形式検査・設定反映: `strata_cli/launch/cmd.py:270-281`。起動対象の判定と warning 表示: `strata_cli/launch/cmd.py:688-700,733-760`。
- launch 設定から engine argv への反映: `strata_cli/launch/runner.py:400-407`。
- engine parser と pool 前の環境変数 fallback: `src/program/generate.cpp:2529,2900-2910`。同系統の SYCL engine にも同じ parser・設定処理があります: `sycl/src/program/generate.cpp:1852,2089-2099`。
- リスト文法、境界、重複排除: `include/strata/kernels/cpu/pool_plan.hpp:180-224`。利用可能 CPU の除外と警告: `include/strata/kernels/cpu/pool_plan.hpp:227-281`。
- pool での適用、worker 数との相互作用、警告: `src/kernels/cpu/pool.cpp:763-818,923-945`。
- Qwen3.6 の別 engine path: `src/program/generate.cpp:2393-2408`。本オプションの対象範囲の説明: `docs/DETAILS.md:2128-2145`。Terminal launch カタログの範囲: `strata_cli/launch/catalog.py:327-333`。

## 調査範囲

指定 checkout のソースとリポジトリ内資料を確認しました。Release 配布物や実機ごとの affinity 可否・性能は調査していません。`strata launch` parser は通常スペースを除去してから独自形式検査するため、engine の `parse_pool_cores` が直接受理するタブ等の空白も Terminal 経由では同じように受理されるとは限りません。
