# `strata launch --new-key`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--new-key` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定時は真、未指定時は偽。 |

## 役割

`strata launch` が共有用 API キーを選ぶ際、保存済み・再利用可能なキーを使わず新しいキーを生成します。生成したキーで `no_key` を解除し、起動設定へ反映します。キーを作り直す用途のフラグで、キーをそのまま画面に表示するものではありません。表示には別オプション `strata launch --show-key` を使います。parser は `launch` の parser にこのフラグを登録しています（`terminal/strata_cli/launch/cmd.py:139`）。

## 使い方

```sh
# 既存の共有用キーを更新して起動する
strata launch --preset Office --new-key

# モデルを指定してネットワーク共有を開始し、新しいキーを使う
strata launch --model <model> --access lan --new-key

# 変更内容を計画表示する（キーは保存されない）
strata launch --preset Office --new-key --plan
```

## 値と既定値

値や別名はありません。`argparse` の `store_true` として定義され、未指定では `False` です（`terminal/strata_cli/launch/cmd.py:139`）。このフラグ固有の値検証はありません。

実際のキーは `sk-strata-` に `secrets.token_urlsafe(24)` の結果をつないで生成します（`terminal/strata_cli/launch/access.py:366-368`）。生成値を固定する処理や、ユーザーがキー値をこのフラグに渡す処理はありません。

## 実行時の動作

まず `settings_from_args` は `--preset` から読み込んだ設定を基礎に CLI の指定を重ねます。`--api-key` や `--api-key-env` が指定されればその値を設定し、`--no-api-key` だけが指定されれば鍵を外して `no_key` を真にします。共有設定で鍵がなく、鍵なし指定でもない場合は、以前の launch 設定から鍵を探し、見つからなければ通常の新規鍵を作ります（`terminal/strata_cli/launch/cmd.py:215-220,288-301,402-411`）。

その後 `--new-key` が真なら、選択済みの鍵を `access.new_key()` の新しい値で置き換え、`no_key` を偽にします（`terminal/strata_cli/launch/cmd.py:890-892`）。したがって `--api-key`、`--api-key-env`、プリセットの鍵、`--no-api-key` と同時指定しても、この後段の処理が鍵を新規生成して鍵なし状態を解除します。これらの組合せを拒否する専用 validation はありません。

生成した鍵は launch の実行設定に `api_key` として書き込まれます。設定は launch ディレクトリ内の `<name>.json` へ private write されます（`terminal/strata_cli/launch/runner.py:724-739,2234-2239`）。通常起動では、その設定を書いた後でのみ「新しいキーを作った」という通知を出す設計です（`terminal/strata_cli/launch/runner.py:2198-2202,3323-3327`）。実行成功時の通常表示はキーをマスクし、JSON 出力もキー自体ではなく `api_key: "set"` を返します（`terminal/strata_cli/launch/cmd.py:975-991`）。

## 適用条件と副作用

- `--plan` では同じ設定組み立て経路で新しい鍵がメモリ上に設定され、計画表示には「API key on」と出ることがありますが、計画後は「Nothing was changed.」として終了します。launch 設定ファイルへの保存は行いません（`terminal/strata_cli/launch/cmd.py:890-924`）。
- 計画表示以外でも、実行設定を書き込む前に失敗・拒否・キャンセルとなれば、新しい鍵はその launch 設定ファイルに保存されません。キー作成通知も実際の書き込み後に限って発行されます（`terminal/strata_cli/launch/runner.py:2198-2202,3322-3327`）。
- `--new-key` は起動設定の組み立て時に無条件で鍵を割り当てます。`--access local` のときにサーバーがこのキーを認証にどう適用するかは、このオプションの処理箇所だけからは確認できません。
- `--new-key` と `--no-api-key` の併用では、新しいキーが設定され `no_key` が解除されます。`--no-api-key` の警告・最終的な無鍵共有を期待する組合せにはなりません（`terminal/strata_cli/launch/cmd.py:295-301,890-892`）。
- 既存キーを再利用する経路で `kept_key` が見つかった場合、先に「以前のキーを保持した」という通知を追加した後に `--new-key` が鍵を置き換えます。通知文と最終設定が食い違う可能性があります（`terminal/strata_cli/launch/cmd.py:402-411,890-892`）。

## 出力とエラー

このフラグ単独のエラー経路はありません。launch 全体の設定処理で `ValueError` が発生した場合はエラー文を出して終了コード `2` となり、実行中の `LaunchError` はそのエラーに付随するコードで報告されます（`terminal/strata_cli/launch/cmd.py:950-962,1011-1014`）。このフラグ自体に追加の終了コードは定義されていません。

生成した鍵の実値を確認する場合は、保存後に `strata launch --show-key` を使います。成功時の通常出力はマスクされた値です（`terminal/strata_cli/launch/cmd.py:990-991`）。

## 根拠

- `terminal/strata_cli/launch/cmd.py:139` — launch parser への `--new-key` 登録と真偽値指定。
- `terminal/strata_cli/launch/cmd.py:215-220,288-301,402-411` — preset と API key 関連オプションの反映、共有時の既存鍵探索と既定生成。
- `terminal/strata_cli/launch/cmd.py:890-892` — `--new-key` が既存設定の後に鍵を生成し `no_key` を解除する箇所。
- `terminal/strata_cli/launch/access.py:366-368,379-415` — 新規キーの生成形式と既存 launch 設定からの鍵探索。
- `terminal/strata_cli/launch/runner.py:724-739,2234-2239` — API キーを含む実行設定の組み立てと private write。
- `terminal/strata_cli/launch/runner.py:2198-2202,3322-3327` — 設定書き込み後の鍵作成通知。
- `terminal/strata_cli/launch/cmd.py:897-924,975-991,1011-1014` — `--plan` の非変更終了、成功時のマスク表示、一般的なエラー処理。

調査は指定 revision の parser と実装箇所を対象にしました。`--access local` でのサーバー側認証の扱いなど、ここで追った CLI 側コードから確認できない実行時仕様は断定していません。
