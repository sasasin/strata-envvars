# `--retune`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata launch` |
| オプション | `--retune` |
| 別名 | なし |
| 値 | 値を取らないフラグ。指定すると真になる（既定値は偽） |

## 役割

`strata launch` の通常のチューニング結果再利用を避け、同じモデル・このコンピューターで既に測定済みでも再測定する。`--tune` を省略するか `--tune skip` を指定した場合、CLI は `quick` に切り替えてから実行する。`--tune quick` / `--tune thorough` と併用すると、そのモードで再測定する（`terminal/strata_cli/launch/cmd.py:121,143-145,874-877`、`terminal/strata_cli/launch/settings.py:29,141`）。

## 使い方

```sh
strata launch --model q2_0 --retune --no-tui
strata launch --preset "IQ3_XXS 128K" --tune thorough --retune
```

モデルまたはプリセットを指定して起動する例。2つ目は `thorough` モードで測定する。値は付けない（parser は `action="store_true"`、`terminal/strata_cli/launch/cmd.py:143-145`）。

## 値と既定値

値の変換・範囲検証はなく、フラグの有無だけを扱う。未指定時は偽で、既定の `--tune` は `skip`（`terminal/strata_cli/launch/cmd.py:121,143-145`、`terminal/strata_cli/launch/settings.py:141`）。ただし `--retune` があると `s.tune == "skip"` を `quick` に置換するため、明示的な `--tune skip` もスキップ指定としては残らない（`terminal/strata_cli/launch/cmd.py:874-875`）。

## 実行時の動作

launch runner は `--retune` がない場合に限り、設定済みの tuning preset、過去に標準設定が最速と確認された記録、または同じモデルと選択内容の保存結果を見つけると、測定を省略する。`--retune` があるとこれらの再利用判定を通らず、`quick` または `thorough` を使って `strata tune auto <profile> ...` を子プロセスとして呼び出す（`terminal/strata_cli/launch/runner.py:2373-2407`）。チューナーの結果は共有 preset store に保存され、成功結果の preset ID / 測定日が launch 設定に反映される。結果が標準設定の確認なら測定日が記録される（`terminal/strata_cli/launch/runner.py:2431-2439`）。

通常の launch ではモデル設定を書いて profile を保存した後、チューニングし、その後サーバーを起動する（`terminal/strata_cli/launch/runner.py:3323-3339`）。既に同じ launch が同じ設定で動いていても、`--retune` があると「既に動作中なので再利用して終了」の分岐を通らない。チューニング時にこの launch 自身のサーバーが動作中なら停止し、測定後の通常の起動経路で再起動する（`terminal/strata_cli/launch/runner.py:2443-2464,2554-2570`）。

## 適用条件と副作用

- `--tune skip` でない測定処理は、Hy4-Flash と Inkling-2-Mini では実行されない。これらは native Strata family として tuning knobs がないため runner の `tune()` が早期 return する（`terminal/strata_cli/launch/runner.py:2373-2376`）。
- 測定前に `<launch-dir>/<profile-name>.tune.json` を削除しようとし（失敗は無視）、子チューナーへ status file として渡す（`terminal/strata_cli/launch/runner.py:2395-2407`）。
- この launch 自身の実行中サーバーは測定のため停止し、測定後に launch の通常経路で再起動する。他のエンジンは停止しない。自身のサーバーを停止できない場合は `LaunchError`（終了コード 6）となり、`strata launch --stop` を案内する（`terminal/strata_cli/launch/runner.py:2443-2464`）。
- チューナーが測定中にキャンセルされると子プロセスを停止し、launch もキャンセル扱いになる（`terminal/strata_cli/launch/runner.py:2411-2415`）。チューナーが結果を返せない・失敗する場合は `tune_words()` が「測定未完了なので標準設定で実行、変更なし」とするが、runner は結果を警告として出した後、通常の起動処理を続ける（`terminal/strata_cli/launch/runner.py:229-245,2431-2439,3333-3339`）。
- 既存サーバーが同じポートで別 profile を使用中の場合の確認・拒否は別途適用される。`--retune` 単独では他 profile のサーバーを置き換える指定にならず、画面なしでは `--restart` がないと終了コード 6 で拒否される（`terminal/strata_cli/launch/runner.py:2554-2588`）。

## 出力とエラー

測定中は「速度向上のため測定中」のイベントと status file に基づく進捗が通知され、完了後は測定結果が情報または警告レベルで出る（`terminal/strata_cli/launch/runner.py:2405-2422,2431-2439`）。このオプション自体に専用の値エラーはない。サーバー停止失敗や競合中サーバーによる拒否は上記の条件で起こる。

## 根拠

- `terminal/strata_cli/launch/cmd.py:143-145` — parser 定義と help 上の再測定・既定動作。
- `terminal/strata_cli/launch/cmd.py:874-877`、`terminal/strata_cli/launch/settings.py:29,141` — skip から quick への補正、runner への引き渡し、tuning 既定値。
- `terminal/strata_cli/launch/runner.py:2373-2407,2431-2439` — 対象 family の早期 return、保存結果の再利用抑止、チューナー呼び出し、結果反映。
- `terminal/strata_cli/launch/runner.py:2443-2464,2554-2588,3323-3339` — サーバー停止・競合条件と、設定保存・測定・起動の順序。
