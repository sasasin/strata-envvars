# `--vram-reserve-mib`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` などの setup wrapper |
| オプション | `--vram-reserve-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数 `N`。setup parser では `0` 以上 |

## 役割

通常の GPU setup では、指定値をそのモデルの run config に engine 引数として保存します。engine が expert cache のサイズを決めるときに、この量の VRAM を空けておくための設定です。既存モデルの通常起動に付けた場合も、値を config に保存してから起動します（`setup.py:6745-6765, 8677-8682`）。

## 使い方

既存モデルを起動し、今後も使う予約量を 1024 MiB に設定する例です（Linux の `setup.sh` は引数を `setup.py` に渡します）。

```sh
./setup.sh --vram-reserve-mib 1024
```

新しいモデルの setup に指定する場合も同じ option を使います。索引上のスコープは `setup.py` の root option です（`docs/cli/README.md:1489-1520`）。

## 値と既定値

- `setup.py` の parser は `type=int` で受け取り、明示値が負なら `ap.error` で拒否します。`0` は受理されます。整数として解釈できない値も argparse の変換エラーになります（`setup.py:8531-8533, 8569-8570`）。
- setup parser 自体の既定値は `None`（未指定）です。通常の setup では未指定値を engine 引数に加えず、engine 側の既定値 700 MiB が使われます（`setup.py:8531-8533, 9529-9537`; `sycl/src/program/generate.cpp:589-590`）。
- 既存 config を見つけて再 setup する場合、明示指定がなければ保存済みの reserve 値を引き継ぎます（`setup.py:8624-8637`）。他の旧 config 引数も setup 生成値に戻したうえで利用者の設定として保持し、今回の明示値はそれを上書きします（`setup.py:6240-6265`）。
- `--vision` が GPU encoder を使う setup では、未指定でも画像用 reserve が config に入ります。値を明示するとその値で置き換えます。明示値が encoder 用 reserve より小さい場合は警告しますが、指定値を保持します（`setup.py:9521-9539`）。CPU reader では画像用 VRAM reserve は追加されません（`setup.py:3120-3125`）。

## 実行時の動作

通常の setup は明示値を `args` の `--vram-reserve-mib N` に設定し、`start()` 経由の指定では既存の同 option を置換または追加します。後者は `user_args` にも記録され、後続の setup/start で維持されます。config は書き換えられ、保存した MiB 数を示すメッセージが出ます（`setup.py:6745-6765, 9529-9539`）。`setup.sh` は `setup.py "$@"` として引数を転送します（`setup.sh:6-12`）。

確認できた engine 実装では、`--vram-reserve-mib` の値を整数として読み、指定済みフラグを立てます（`sycl/src/program/generate.cpp:1891`）。expert cache の自動 sizing では、reserve と prefill buffer、draft head、pipeline 分を利用可能 VRAM から差し引いて slot 数を決めます。したがって reserve を増やすと、この経路では expert cache に使える VRAM が減ります（`sycl/src/program/generate.cpp:4512-4526`）。

### SYCL setup

`--backend sycl` は `sycl/setup_intel.py` に委譲されます（`setup.py:8563-8564`）。SYCL setup は config にある同 option をいったん取り除き、明示値がなければ小容量カード用値、または context に応じた 1024/2048 MiB を選びます。fit 調整が必要なら reserve も調整し、最後に engine 引数へ追加します（`sycl/setup_intel.py:317-328, 337-355`）。小容量カードでは未指定時にさらに `SMALL_RESERVE_MIB` を渡す分岐があります（`sycl/setup_intel.py:541-549`）。この経路の数値定数・fit 条件はカードや context に依存するため、固定の既定値としては扱えません。

## 適用条件と副作用

- 通常の setup では、モデルの run config に値を書き込みます。既存モデルの起動時に指定しても永続化されます（`setup.py:6753-6765`）。
- CUDA/HIP などのすべての配布 engine で同じ sizing 実装が動くかは、この checkout の該当 parser/使用箇所だけからは確定できません。上記の cache sizing の根拠は `sycl/src/program/generate.cpp` にある実装として示しています。setup 側の通常経路が engine 引数に値を渡すこととは区別してください。
- macOS の非 Control setup は parser 作成前に別の `metal/setup_mac.py` に委譲されます。この文書で確認した `setup.py` parser の受理範囲に macOS Metal setup を含めません（`setup.py:8418-8420`）。
- 通常の engine parser の初期値は 700 MiB です。自動 expert-cache sizing で必要 slot 数を確保できず、reserve が未指定なら、実装は 300 MiB まで reserve を下げて再計算する場合があります。明示値はこの自動縮小の対象外です。cache が 0 slot になると stderr に不足量と調整案を出します（`sycl/src/program/generate.cpp:4534-4575`）。
- 起動後の VRAM 空きが 256 MiB 未満なら、stderr に LOW 警告、または reserve を下げて fit した旨の警告を出します（`sycl/src/program/generate.cpp:8690-8704`）。
- setup は小容量カードや desktop を駆動する GPU について reserve の提案を表示することがありますが、未指定値をその提案値に変更する処理ではありません（`setup.py:9576-9586`）。

## 出力とエラー

- 負数は `--vram-reserve-mib takes a number of MiB, 0 or more...` の parser error になります（`setup.py:8569-8570`）。整数に変換できない値も argparse の parse error 経路です（`setup.py:8531`）。
- 画像 encoder の必要値を下回る明示値は warning を出し、値自体は保持します。encoder が画像読み込み時に VRAM 不足になる可能性を伝えます（`setup.py:9532-9535`）。
- engine が expert cache 用の最低 slot を割り当てられない場合は `strata generate: no VRAM is left for the expert cache...` を stderr に出す箇所を確認しました。ただし、この source checkout の調査では該当 engine の起動実行や各 backend の終了コードを確認していません（`sycl/src/program/generate.cpp:4555-4575`）。

## 根拠

- parser、整数型、setup validation: `setup.py:8531-8533, 8569-8570`
- setup wrapper の引数転送: `setup.sh:6-12`
- 新規 config への反映と画像用 reserve との相互作用: `setup.py:9521-9539`
- 既存設定の引継ぎと明示値の優先: `setup.py:6240-6265, 8624-8637`
- plain start での永続化: `setup.py:6745-6765, 8677-8682`
- SYCL setup の値選択・fit 調整・engine 引数追加: `setup.py:8563-8564`; `sycl/setup_intel.py:317-355, 541-549`
- 確認できた engine parser、reserve による auto cache sizing、失敗・空き VRAM 出力: `sycl/src/program/generate.cpp:589-590, 1891, 4512-4526, 4534-4575, 8690-8704`
- 索引上のツールと option scope: `docs/cli/README.md:1489-1520`

調査制約: 対象 checkout の parser とコード経路を読み取り専用で確認しました。CLI help の実行、配布 Release artifact の照合、ビルド、GPU 実行、テストは行っていません。特に CUDA/HIP の配布 engine 実装と macOS Metal setup の option 挙動は、本調査で確認できたソース範囲外です。
