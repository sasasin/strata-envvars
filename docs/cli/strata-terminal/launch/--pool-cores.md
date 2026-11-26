# `--pool-cores`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--pool-cores` |
| 別名 | なし |
| 値 | 論理プロセッサ番号のリスト。番号、昇順範囲、任意の正の刻み幅をカンマで組み合わせる（例: `2,4,6,8`、`2-14:2`）。 |

## 役割

モデル計算に使う CPU worker pool の worker を、指定した論理プロセッサに割り当てる実験的な設定です。Terminal は値を launch 設定に載せ、実行時に engine の引数へ反映します。未指定時は engine の既定配置を使います。これは全ての Strata thread を制限する指定ではありません。

## 使い方

```sh
# 計画表示で指定値を確認する（起動や設定書き込みは行わない）
strata launch --model q2_0 --pool-cores 2,4,6,8 --plan

# モデルを起動し、CPU worker を指定する
strata launch --model q2_0 --pool-cores 2-14:2 --no-tui
```

## 値と既定値

- Terminal parser は値を必須とし、起動時の値検査では半角空白を除いた後、数字・範囲・`:刻み幅`・カンマ区切りの形式を確認します。適合しない値は拒否せず警告し、その指定を採用しません。既存 preset または同時指定の `--set pool-cores=...` があればその値は残ります（`terminal/strata_cli/launch/cmd.py:126-129,302-310`）。空文字は truthy 判定で処理されないため設定に反映されません。
- Terminal の形式検査は engine の範囲検査より緩く、数値上限や昇順、刻み幅が正かどうかは engine が確認します。engine は各番号が `0..100000` の範囲にあり、展開後の重複除去済みリストが最大 4096 件であることを要求します。逆順範囲・刻み幅 0・空要素・不正文字列などは解析失敗です（`engine/include/strata/kernels/cpu/pool_plan.hpp:183-224`）。
- engine は重複番号を最初の出現順で一度だけ残します。範囲の端点は含まれます（`engine/include/strata/kernels/cpu/pool_plan.hpp:201-224`）。
- 既定では本オプションは無効で、worker pool の既定配置が使われます（`engine/src/program/generate.cpp:865-866,1456-1462`）。

## 実行時の動作

`strata launch` は指定値から空白を除き、launch 設定の `extra` に `--pool-cores` として格納します。`--set pool-cores=...` と同時に指定した場合、有効な `--pool-cores` が後から同じ設定キーを上書きします。`--preset NAME` を使った場合も、指定値はその起動分の preset 設定に重ねられます（`terminal/strata_cli/launch/cmd.py:215-221,302-310`）。

launch 設定は engine の引数変更に変換され、明示した値が既存の設定や生成された既定値より優先されます。値は engine 起動時に pool 構築前に読み取られ、CPU worker の配置リストとして使われます（`terminal/strata_cli/launch/runner.py:801-804`、`engine/src/program/generate.cpp:4703-4713`）。環境変数 `STRATA_POOL_CORES` も engine 側で参照されますが、コマンドライン値が空の場合に限って採用されます（`engine/src/program/generate.cpp:4705-4712`）。

利用可能な論理プロセッサ番号だけが適用され、存在しない番号やプロセスが使えない番号は除外されます。SMT sibling を複数指定した場合や host thread と同じ processor / core を指定した場合は警告しますが、指定自体は維持されます（`engine/include/strata/kernels/cpu/pool_plan.hpp:236-280`）。利用可能な番号が一つもなければ既定配置へ戻ります（`engine/src/kernels/cpu/pool.cpp:825-839`）。

有効な指定リストは順序を保ちます。`--pool-workers` を併用しない場合、worker 数は適用できたリストの長さです。worker 数をリストより大きく明示すると、リストを超える worker は processor に pin されません（`engine/src/kernels/cpu/pool.cpp:865-870,1006-1013`）。NUMA の自動 CPU 配置との併用では、この指定が明示的な配置として扱われ、engine の自動 card-node CPU 制限は行われません（`engine/src/program/generate.cpp:4655-4679`、`engine/include/strata/kernels/cpu/card_node.hpp:59-62,118-148`）。

## 適用条件と副作用

- 設定は実験的で、CPU worker pool の構築時に適用されます。対応 parser は通常の engine の `engine/src/program/generate.cpp:3955` と SYCL engine の `engine/sycl/src/program/generate.cpp:2238-2247` で確認しました。Terminal 側は値を選択中の engine に渡すため、その他の engine 実装がこの引数を受理するかはこの調査では確認できていません。
- pool の worker thread を指定 CPU に pin しようとします。OS の CPU affinity 制限などで pin できない場合があり、NUMA split 有効時には pin 失敗が遠隔 node からの読み取りにつながる可能性を engine が stderr に通知します（`engine/src/kernels/cpu/pool.cpp:991-1002`）。
- 無効な形式は Terminal 側で警告して通常起動を続けます。Terminal の値検査を通過しても engine 側で解析できなければ stderr に理由を出し、既定配置を使います（`terminal/strata_cli/launch/cmd.py:304-310`、`engine/src/program/generate.cpp:4703-4713`）。
- 本オプションは現在の launch に適用されます。通常起動で `--save-preset NAME` を付けると、その値を含む preset が保存されます。`--plan` は保存処理に進まず、設定変更もしません（`terminal/strata_cli/launch/cmd.py:311-312,897-925,962-964`）。

## 出力とエラー

Terminal の形式不一致は `[!]` 警告として表示され、`--plan` の場合は plan の警告欄に含まれます。engine の値解析失敗も stderr に警告を出して起動を続け、pool の既定配置に戻ります（`terminal/strata_cli/launch/cmd.py:304-310,897-925`、`engine/src/program/generate.cpp:4703-4713`）。実行時に論理 processor が使えない場合や sibling / host-core との競合がある場合は engine が stderr に通知します（`engine/src/kernels/cpu/pool.cpp:825-839`、`engine/include/strata/kernels/cpu/pool_plan.hpp:245-280`）。このオプション固有の検証失敗による非ゼロ終了は確認できませんでした。

## 根拠

- `terminal/strata_cli/launch/cmd.py:126-129` — Terminal parser の定義と利用者向け説明。
- `terminal/strata_cli/launch/cmd.py:215-221,302-310` — preset を基にした設定組み立て、値の形式検査、警告、`extra` への格納。
- `terminal/strata_cli/launch/settings.py:392-417`、`terminal/strata_cli/launch/runner.py:801-804` — engine argv 設定への変換と明示値の適用。
- `terminal/serve/server_parts/engines.py:854-877`、`terminal/serve/server.py:3758-3759` — run config の `pool_cores` 値を engine 引数へ補う処理。既に `--pool-cores` が args にあれば重ねて追加しない。
- `engine/src/program/generate.cpp:3955,4703-4713`、`engine/sycl/src/program/generate.cpp:2238-2247` — engine parser と環境変数 fallback、pool 作成前の値設定。
- `engine/include/strata/kernels/cpu/pool_plan.hpp:180-224,236-280`、`engine/src/kernels/cpu/pool.cpp:823-839,865-870,991-1013` — リスト検証、適用可能 CPU の判定、worker 数・pin の動作。
- `engine/src/program/generate.cpp:4655-4679`、`engine/include/strata/kernels/cpu/card_node.hpp:59-73,118-148` — 明示配置時に card-node 自動 CPU 制限を選ばない条件。

調査範囲は上記 commit の Terminal launch parser、launch 設定・server の引数転送、および通常/SYCL engine の parser と CPU pool 実装です。実機での OS ごとの affinity API の成否や、ここで parser を確認できなかった engine 実装の受理可否は確認していません。
