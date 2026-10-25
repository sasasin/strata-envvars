# `--force`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components update` |
| オプション | `--force` |
| 別名 | なし |
| 値 | 取らないフラグ。省略時は `false` |

## 役割

現在の PC 向けにフィードが選んだエンジン版について、以前のテスト起動失敗または rollback による再試行抑止を解除して、更新を試みます。通常の新規・通常更新を強制的に別版へ変えたり、検証を省略したりするオプションではありません。

## 使い方

```sh
strata components update --force
```

フィードを確認するだけなら `--check` と併用できます。この場合、判定上の抑止が解除された表示になりますが、コンポーネントのダウンロードやインストールは行いません。

```sh
strata components update --check --force
```

## 値と既定値

値や別名はありません。`argparse` の `store_true` で定義され、未指定では `false`、指定すると `true` になります。繰り返しても真のままです。値を付けて渡す形式は定義されていません。専用の値検証や範囲検証はありません（`strata_cli/update_cmd.py:30-40`）。

## 実行時の動作

`strata components update` の parser は `--force` を共通引数として登録し、CLI はこのサブコマンドを `update_cmd.run` に渡します（`strata_cli/update_cmd.py:36,50-56`、`strata_cli/cli.py:139-140,2135-2137`）。実行時に `a.force` が `updater.Context.force` にコピーされます（`strata_cli/update_cmd.py:174-184`）。

エンジン更新の候補版がインストール済み版より新しく、通常なら状態ファイル上の失敗記録と同じ manifest の版がテスト起動に失敗している場合、または rollback 済みの版として `skipped` に記録されている場合、通常は更新を抑止します。`--force` があるとその抑止判定を行わず、更新可能な候補として扱います（`strata_control/updater.py:595-614`）。失敗記録は24時間を過ぎると古いものとして無視されます（`strata_control/updater.py:1135-1142`）。

実際の更新経路でも `failed-before` / `skipped` の場合に `Context.force` が真ならエンジン更新を続行します（`strata_control/updater.py:926-937`）。成功した更新では失敗記録と該当する skipped 記録を除去します（`strata_control/updater.py:1010-1015`）。一方 `--check` は feed と状態を読んで判定・記録するだけの別経路で、更新処理を呼びません（`strata_cli/update_cmd.py:203-209`、`strata_control/updater.py:624-640`）。

このフラグが作用するのはエンジン版の再試行抑止です。Control や `--app` で追加されるデスクトップアプリ installer の処理を強制する実装はありません。`--no-engine` を指定すればエンジン更新処理自体が実行されず、`--no-control` は Control の処理を省略します（`strata_cli/update_cmd.py:45-55,213`、`strata_control/updater.py:1274-1285`）。

## 適用条件と副作用

- フィードに PC 向け候補がなく、候補が現在版と同じか古い場合は、`--force` でも更新対象になりません。古い版への downgrade は抑止されます（`strata_control/updater.py:581-602`）。
- フラグは署名・パッケージ検証、GPU make 適合、engine test-start、serving 中の busy 判定を迂回しません。通常の更新はダウンロード後に stage してテスト起動し、成功時に切り替えます（`strata_control/updater.py:931-960,977-1009`）。
- 更新はネットワークから署名済み feed とパッケージを取得し、コンポーネントディレクトリ内に展開・切り替えます。更新成功時は直前のエンジンを rollback 用に保持し、古い版を整理します（`strata_control/updater.py:926-948,980-1024`）。
- テスト起動に失敗した場合、busy が原因でない失敗は版と manifest hash 等を状態に記録します。現在のエンジンは変更されず、ログは後から確認できるよう保持されます（`strata_control/updater.py:967-976`、同 `:775`）。
- `--force` は共通 parser にあるため `strata update` と `strata components rollback` にも構文上受理されます。ただしこの文書の対象は `strata components update` です。rollback 実装は `Context.force` を参照せず、強制を必要とする場合の案内として `strata update --force` を表示しています（`strata_cli/update_cmd.py:42-59,185-196`、`strata_control/updater.py:1033-1078`）。

## 出力とエラー

`--force` 専用の出力はありません。通常の human 出力では更新結果を表示し、JSON / JSONL 指定時は機械可読形式で結果を出します（`strata_cli/update_cmd.py:62-84,213-224`）。

強制再試行後もネットワーク・署名・検証・テスト起動などの失敗は通常どおりエラーになります。human 出力では `strata: <理由>` を stderr に出し、JSON / JSONL ではエラーオブジェクトを stdout に出します。終了コードは失敗種別に従い、署名・acquisition 拒否は 5、更新中の失敗は updater が返すコード（テスト起動失敗は 6）、serving 中は 7、割り込みは 130 です（`strata_cli/update_cmd.py:165-172,225-234`、`strata_control/updater.py:79-113,1274-1297`）。

## 根拠

- `strata_cli/update_cmd.py:30-59` — 共通 parser 定義と `components update` の引数登録。
- `strata_cli/update_cmd.py:174-184,203-224` — `Context` への値の引き渡し、check/update 経路と出力。
- `strata_cli/cli.py:139-140,2135-2137` — parser 登録とコマンド dispatch。
- `strata_control/updater.py:595-614,926-937` — 失敗済み・rollback 済み候補の判定と `force` による抑止解除。
- `strata_control/updater.py:967-976,1010-1024,1135-1142` — 失敗記録、成功時の状態更新、記録の有効期間。
- `strata_control/updater.py:624-640,1274-1297` — check の非更新性、更新実行、結果と失敗コード。

調査は上記 checkout のソースに限定しました。同一 revision の既存配布物や実行 CLI help は照合していません。
