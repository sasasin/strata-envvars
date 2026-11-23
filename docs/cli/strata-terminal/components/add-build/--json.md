# `--json`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components add-build` |
| オプション | `--json` |
| 別名 | なし（`--output json` は同じ JSON 出力を選ぶ別指定） |
| 値 | 値を取らないフラグ。指定すると JSON 出力を選ぶ |

## 役割

ローカルビルドを追加して使用エンジンに切り替える処理の結果を、機械処理しやすい JSON 1 行で出力する。進捗・対話質問などの人向け出力は抑えられる。JSON 出力を選んでも操作自体は実行されるため、成功時はビルドをコンポーネント領域へコピーし、そのエンジンを選択する。

## 使い方

```sh
strata components add-build ./build --json
```

`--json` は `add-build` のサブコマンド用オプションとして登録されている。`--output json` でも同じ JSON モードになる。

## 値と既定値

値は不要で、未指定時は `false`（既定の出力形式は `human`）。parser は `store_true` で受理し、値の validation はない。複数回指定しても真のまま。`--json` が指定されると、CLI の共通処理が `output` を `json` に設定する。`--output jsonl` との併用は拒否され、終了コード 2 の JSONL 失敗イベントになる。

## 実行時の動作

成功時は `schema_version: 1`、`ok: true`、追加内容を表す `added` と、エンジン切替結果を含む JSON オブジェクトを標準出力へ 1 行出す。JSON モードでは進捗イベントを標準出力へ出さず、実行中エンジンがある場合の対話質問も行わない。`--wait` が指定されていればその待機時間は利用される。

`--json` は表示形式を選ぶもので、処理を dry-run にはしない。追加に成功したビルドは、`<components>/engine/` 以下へコピーされ、ローカル・未署名として記録された後、現在使用するエンジンに切り替わる。

## 適用条件と副作用

JSON モードでも `add-build` の通常処理が走る。適切なビルドフォルダー、実行可能な `strata`、バックエンド情報および必要な GPU architecture 情報が必要。成功時は実行ファイル、同じフォルダー直下の共有ライブラリ・所定の `strata-vision` helper・`BUILD.json` をコンポーネント領域にコピーし、manifest を書き込み、コンポーネントの使用状態を更新する。ダウンロードは行わない。

実行中モデルがあるとき、`--json` によって対話確認を省略する。`--wait` がなければ切替処理は待たず、ビジーエラーになり得る。ローカルビルドは未署名で、`STRATA_REQUIRE_SIGNED_COMPONENTS=1` の場合はエンジン切替の署名検証で拒否される。この検証はローカルパッケージを追加した後に行われるため、その場合はパッケージが追加済みのまま切替が失敗する。

## 出力とエラー

成功時の JSON は標準出力に出る。`AddBuildError` は `UpdateError` に変換され、JSON モードでは `{"schema_version":1,"ok":false,"error":{"code":<数値>,"message":"..."}}` の形式で標準出力に出力され、終了コードはそのエラーコードになる。たとえば対象フォルダーやビルド情報の不備はコード 2、実行・互換性上の拒否はコード 5。engine 切替時の `UpdateError` も同じエラー経路を通る。

parser が認識しない引数など、処理開始前の argparse usage error は通常の parser エラー経路であり、`--json` の JSON エラー形式にはならない。

## 根拠

- `terminal/strata_cli/cli.py:539-547` — one-shot コマンド群のうち `add_parsers` が返す parser に `--json`（`store_true`）を登録。
- `terminal/strata_cli/cli.py:2325-2339` — 引数解析後、`--json` 指定時に `output` を `json` へ切り替え（`jsonl` 併用はエラー）。
- `terminal/strata_cli/cli.py:2210-2212` — `components add-build` を `update_cmd.run` に委譲。
- `terminal/strata_cli/update_cmd.py:47-56,117-126` — 共通 `--output` の値と、JSON/JSONL で人向け進捗を抑制する処理。
- `terminal/strata_cli/update_cmd.py:303-321,374-386` — machine 出力の判定、JSON 失敗 envelope、例外の終了コード処理。
- `terminal/strata_cli/update_cmd.py:425-442` — `add-build` の JSON 成功出力、追加後の engine 選択。
- `terminal/strata_control/local_engine.py:127-177` — ビルド検査、コピー対象、manifest 作成、ローカルパッケージ配置と失敗条件。
- `terminal/strata_control/engine_library.py:211-228,296-312` — エンジン切替、稼働中モデルの待機または拒否、署名検証と切替。
- `terminal/strata_control/engine_component.py:386-405` — `STRATA_REQUIRE_SIGNED_COMPONENTS` が有効なとき未署名エンジンを拒否する条件。
