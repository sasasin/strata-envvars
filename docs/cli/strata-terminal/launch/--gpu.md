# `--gpu`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | `LIST`。GPU 番号をカンマ区切りで指定（例: `0`、`0,1`） |

## 役割

この起動で使う GPU 番号を明示します。1 枚を指定するとそのカードを選び、複数を指定すると同じモデルをカード間で分割します。カードごとの `main` / `helper` / `off` の役割まで指定する場合は、代わりに `--gpu-roles` を使います。`--gpu` と `--gpu-roles` を同時に指定すると拒否されます（`strata_cli/launch/cmd.py:108-110,236-247`）。

## 使い方

```sh
strata launch --gpu 0 --plan
strata launch --gpu 0,1 --plan
```

`--plan` は予定を表示して終了するため、選んだカードを含む計画を確認する用途に使えます（`strata_cli/launch/cmd.py:138`、`strata_cli/launch/cmd.py:733-760`）。実際に起動する場合は `--plan` を外します。モデルを指定しない場合は、利用可能なら Strata がこのコンピューター向けの候補を選びます（`strata_cli/launch/cmd.py:302-314`）。

## 値と既定値

- 値は GPU 番号の整数列です。`strata_cli/launch/cmd.py:188-195` は文字列中の空白を除き、カンマで分けた各要素を `int` に変換します。整数にできない要素があれば `ValueError` になります。
- 空の要素は除かれます。そのため `0,,1` はこの処理では `[0, 1]` になります。番号の重複、負数、存在範囲はこの parser/helper では検証されません。また、引数値が空文字列の場合は設定へ適用されません（`strata_cli/launch/cmd.py:188-194,236-240`）。
- オプションを省略すると `LaunchSettings.gpus` は `None` です。選択済みモデル設定に明示カードが保存されていればそれを維持し、そうでなければ複数の使用可能カードがある場合に推奨カードを使う経路があります。それ以外は既存設定または engine 側の選択に委ねられます（`strata_cli/launch/settings.py:77-88`、`strata_cli/launch/runner.py:341-368`）。

## 実行時の動作

`settings_from_args` は指定リストを `LaunchSettings.gpus` に入れ、GPU 役割の指定を解除します（`strata_cli/launch/cmd.py:236-247`）。起動時には `cards_for_launch` がその番号列を優先し、`derive_config` / `apply_cards` が launch 用設定に `gpu` と `gpus_asked` を反映します。複数番号ならリストとして保存し、既存の `layer_split` がなければ `auto` を設定します。1 枚なら `gpu` は単一番号となり、`layer_split` は取り除かれます（`strata_cli/launch/runner.py:296-323,341-368`）。launch 設定ファイルは `launch_dir()/...json` に書かれます（`strata_cli/launch/runner.py:1235-1243`）。

モデルの setup が必要な場合、Runner は1枚なら setup の `--gpu`、複数なら `--gpus` として番号を渡します。setup 側では選択カードの有無・使用可否を確認し、複数枚の場合は同一モデルの分割先として扱います（`strata_cli/launch/runner.py:727-775`、`setup.py:1660-1674,1677-1703,1774-1791,8461-8465`）。macOS の setup 引数整形では `--gpu` は転送対象に含まれず、削除されます（`strata_cli/launch/runner.py:760-775`）。

setup 済みモデルの起動時は、setup の `--gpu N` はその起動だけに使われ、複数 GPU の選択は `--gpus` 相当として設定へ保存されます（`setup.py:6737-6745,6781-6824,8461-8465`）。ただし `strata launch` 自身は launch ごとの private 設定を作るため、上記の `apply_cards` の反映経路も通ります。

## 適用条件と副作用

- カード番号は Strata が検出した GPU の番号です。実際に利用できる backend、カード番号と vendor の対応、カード間分割の可否はハードウェアとその Strata build に依存します。
- `gpu_notices` は、build が駆動する vendor と異なる使用可能カードが指定された場合にエラー通知を作ります。同じ vendor で番号が存在しない場合は、この通知処理だけでは範囲エラーにしません。setup 時には setup 側の `check_gpus` が未検出カードや利用不可カードを拒否します（`strata_cli/launch/cmd.py:376-407`、`setup.py:1677-1703`）。
- 複数 GPU を指定するとモデルをカード間で分割する設定になります。選択により VRAM が不足する、あるいはカードが setup/engine で使えない場合、setup または起動処理で失敗することがあります。性能向上を保証する根拠はこの調査では確認していません。
- setup が必要な通常起動ではモデル/engine の取得や setup が発生し得ます。`--plan` 経路は「Nothing was changed」と出して終了します（`strata_cli/launch/cmd.py:733-760`、`strata_cli/launch/runner.py:2011-2025`）。

## 出力とエラー

- 整数へ変換できないリストは `ValueError` となり、`strata launch` は人向け出力では `strata: ...` を stderr に表示し、終了コード 2 を返します。JSON 出力時は `ok: false` のエラー JSON を出し、コード 2 を返します（`strata_cli/launch/cmd.py:630-641,832-837`）。
- `--gpu` の値が欠けている場合は `argparse` の引数エラーです。番号の存在確認や GPU 選択後の engine 起動エラーは setup/engine の処理に委ねられ、具体的なメッセージは失敗条件により異なります。
- 指定した他 vendor のカードは `gpu_notices` が理由と代替案を示すエラー通知にします。`run_launch` は通知中の最初の error を出力し、コード 2 で止めます（`strata_cli/launch/cmd.py:382-395,721-725`）。

## 根拠

- parser、値の変換、設定への適用、相互排他: `strata_cli/launch/cmd.py:75-110,188-195,236-247`
- 起動時のカード選択、launch 設定への反映、設定ファイル書き込み: `strata_cli/launch/runner.py:296-323,341-368,1235-1243`
- setup 引数への転送と macOS 分岐: `strata_cli/launch/runner.py:727-775`
- setup 側の選択検査・保存、および起動時の GPU 指定: `setup.py:1660-1703,1774-1791,6737-6824,8461-8465`
- 対象コマンドと文書配置: `docs/cli/README.md` の `strata launch` 節（索引には本ファイルへの `--gpu` リンクがある）。

調査範囲は上記 commit の source checkout です。Release 配布物の実行確認、実 GPU 上の挙動、個々の driver/backend における番号対応は確認していません。
