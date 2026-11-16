# `--gpu`

調査対象: Strata commit `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU 番号のカンマ区切りリスト（例: `0`、`0,1`） |

## 役割

起動に使う GPU を番号で指定します。省略時は保存済みの明示選択があればそれを維持し、なければ通常の GPU 選択規則に任せます。複数番号を指定するとそのカード群を使う設定になり、役割（Main / Helper / Off）まで個別に決める場合は `--gpu-roles` を使います（`strata_cli/launch/cmd.py:111-117`, `strata_cli/launch/runner.py:398-427`）。

## 使い方

```sh
# GPU 0 でモデルを起動
strata launch --model q2_0 --gpu 0 --no-tui

# GPU 0 と GPU 1 を使う起動計画を表示（変更なし）
strata launch --model q2_0 --gpu 0,1 --plan
```

## 値と既定値

- `--gpu` は値を一つ受け取ります。parser 自体では型変換せず、設定組み立て時に空白を除いてカンマで分割し、各要素を Python の整数へ変換します。例のように `0` または `0,1` と指定します（`strata_cli/launch/cmd.py:111-112,197-203`）。
- 文字列全体が空なら選択値にしません。分割後の空要素は読み飛ばすため、たとえば `0,,1` は `[0, 1]` になります。整数に変換できない要素があれば `'<入力>' is not a list of graphics card numbers. Use 0 or 0,1.` の `ValueError` になります（`strata_cli/launch/cmd.py:197-203`）。
- parser に既定値は明示されていません。未指定なら `None` となり、保存済み選択や通常の選択処理へ進みます（`strata_cli/launch/runner.py:398-427,989-1010`）。負数・重複番号・実機に存在しない番号をこの CLI の変換関数は拒否しません。後続処理での全ての値の扱いは、この parser だけからは確認できません（`strata_cli/launch/cmd.py:197-203`）。
- 同じ `--gpu` を複数回書いた場合の専用処理はなく、`argparse` の通常の単一値引数として扱われます（登録に `action` 指定なし: `strata_cli/launch/cmd.py:111-112`）。

## 実行時の動作

`strata launch` はまず保存 preset を読み、その上に CLI の指定を反映します。`--gpu` が指定されると番号リストを `LaunchSettings.gpus` に設定し、preset の GPU role 指定を解除します（`strata_cli/launch/cmd.py:206-212,251-255`）。`--gpu` と `--gpu-roles` を同時に指定すると拒否されます（同 `:251-261`）。

実際の起動では、明示した番号が選択カードとして優先されます。起動時の設定では単一 GPU は `gpu` に整数、複数 GPU は整数リストとして記録し、明示選択の印 `gpus_asked` を付けます。複数指定では `layer_split` が未設定なら `auto` を設定し、単一指定では既存の `layer_split` を除去します。旧 role 情報や `hip_ordinal` も除去して、今回の番号選択と競合しないようにします（`strata_cli/launch/runner.py:350-377,398-413,1692-1714`）。

モデル準備用の setup 呼び出しにも単数なら `--gpu N`、複数なら `--gpus N,...` として渡されます。指定しない場合、既存モデルに明示選択が保存されていればそれを渡し、自動選択は転送しません（`strata_cli/launch/runner.py:963-970,989-1010`）。macOS では setup へ渡す引数から `--gpu` / `--gpus` を除く処理があります（同 `:971-986`）。

通常起動は `launch/<name>.json` の private な実行設定を書き込み、そこからサーバー起動へ進みます。`--plan` は GPU の表示を含む計画を出力して `Nothing was changed.` と表示し、実行設定を書きません（`strata_cli/launch/runner.py:1692-1714`; `strata_cli/launch/cmd.py:851-877`）。

## 適用条件と副作用

- `--gpu` は `strata launch` 専用の指定です。索引上の `strata-engine` の `--gpu` とは別スコープです（`docs/cli/README.md:809-840`; Terminal parser: `strata_cli/launch/cmd.py:73-80,111-112`）。
- 複数 GPU のとき役割は engine 側の決定に委ねられます。役割を明示する設定は `--gpu-roles` で、両方は併用できません（`strata_cli/launch/cmd.py:111-117,251-261`）。
- 指定カードは今回の launch の実行設定に適用されます。実際の起動では設定ファイル書き込みとサーバー起動が伴います。`--plan` は確認用で変更しません（`strata_cli/launch/runner.py:350-377,1692-1714`; `strata_cli/launch/cmd.py:851-877`）。
- parser / `_gpus` に GPU 番号の実在性、非負範囲、重複の検査はありません。番号が backend で使えるかなど、後段の engine / setup における全ての拒否・fallback 条件はこの調査範囲では特定できません。

## 出力とエラー

整数へ変換できない値や `--gpu` と `--gpu-roles` の同時指定は `ValueError` になり、通常出力では `strata: <エラー文>` を stderr に出して終了コード `2` を返します（`strata_cli/launch/cmd.py:251-261,710-721,961-964`）。GPU 番号が実行環境で利用できない場合のエラー文・終了コードは、CLI の検証経路からは確認できません。

## 根拠

- `strata_cli/launch/cmd.py:73-80,111-117` — `launch` parser と `--gpu` / `--gpu-roles` の登録・説明。
- `strata_cli/launch/cmd.py:197-203,206-212,251-261` — リスト変換、preset への反映、role との排他。
- `strata_cli/launch/runner.py:350-377,398-427` — 選択カードの決定と実行設定への格納。
- `strata_cli/launch/runner.py:963-986,989-1010` — setup への GPU 引数転送と、選択済み設定の引き継ぎ。
- `strata_cli/launch/runner.py:1692-1714` — launch 専用設定ファイルの作成。
- `strata_cli/launch/cmd.py:710-721,851-877,961-964` — 計画表示、エラー出力と終了コード。
- `docs/cli/README.md:809-840` — `strata launch` の索引リンクおよび `--gpu` のコマンド scope。
