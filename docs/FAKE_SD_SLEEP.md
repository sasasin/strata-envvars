# `FAKE_SD_SLEEP`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

画像生成サーバーのテストで使う fake Stable Diffusion CLI (`serve/fixtures/fake_sd_cli.py`) に、画像生成処理を始める前の待ち時間を与えます。`serve/test_images.py` の `test_chat_waits_for_the_image` は値を `1.5` にして、画像ジョブの実行中に送った chat 要求が画像ジョブの後まで待つことを確認するために使っています。

この変数を読むコードは fixture にだけあります。Strata の本番サーバーや実際の `sd-cli` の動作を制御する環境変数ではありません。調査手順ではテスト専用コードを実装根拠から除外していますが、この候補には fixture 以外の読み取り実装が見つからなかったため、以下は fixture の挙動に限って記録します。本番機能についての説明ではありません。

## 値と判定

fixture は `float(os.environ.get("FAKE_SD_SLEEP") or 0)` を `time.sleep()` に渡します。値を独自に範囲検証したり clamp したりしません。

| 環境変数の状態 | fixture が行う処理 |
|---|---|
| 未設定 | `0` を浮動小数点数に変換し、実質待たずに続行 |
| 空文字 | `or 0` により `0` と同じ扱い |
| `0`、`1.5`、指数表記など | Python の `float()` で変換した値を秒数として `time.sleep()` に渡す |
| 数値に変換できない文字列 | `float()` が例外を送出し、後続の通常ログ・処理には進まない |
| 負数 | 値をそのまま `time.sleep()` に渡す。fixture 側に負値の補正はなく、sleep 呼び出しが例外になる |

`float()` による変換なので文字列全体が数値として解釈できる必要があります。前後空白や Python が認識する指数表記は受け付けますが、数値の後ろに任意の文字を付けた値は変換できません。`nan` / `inf` などの特殊値に対する独自処理もありません。最終的な扱いは `time.sleep()` に渡される値に依存します。

## 有効になる条件

この変数が効くのは、`serve/fixtures/fake_sd_cli.py` を起動するテスト経路だけです。fixture は `main()` の冒頭で引数を処理した後、成功・失敗ログの出力や PNG 書き込みより前に sleep します。画像生成サーバー本体はこの名前を参照しません。

fixture を `serve/images.py` 経由で起動する場合、`image_env()` は起動時点の `os.environ` をコピーし、その後に設定ファイルの `images.env` を上書き適用します。そのため、環境から渡した値は設定項目 `images.env.FAKE_SD_SLEEP` があればそちらに置き換わります。実際の `sd-cli` にこの値をどう扱うかは Strata のソースからは確認できず、ここでは扱いません。

## 実行時の詳細

各 fixture 起動で `FAKE_SD_SLEEP` を読み直します（プロセス内 static cache はありません）。正の値なら待ち終わった後に `[INFO ] loading tensors completed, taking 0.10s` を出し、その後 `FAKE_SD_FAIL` が設定されている場合は失敗ログを出して終了コード 1 を返します。通常は続けて進捗ログと PNG を出力します。

fixture の例外・終了コードは画像ジョブの失敗判定に入ります。`serve/images.py` は子プロセスのログを `sd-cli.log` にまとめ、終了コードが 0 でない場合はジョブを失敗として扱います。テストで設定する `1.5` 秒は、fixture がこの待機中である間に chat 要求を出すためのものです。

## 根拠

- `serve/fixtures/fake_sd_cli.py:1-4,25-42` — fixture の用途、環境変数の変換・sleep、および sleep 後のログと失敗分岐。
- `serve/test_images.py:23-40,321-337` — fake CLI を使うテスト構成と `FAKE_SD_SLEEP=1.5` による chat 待ちのテスト。
- `serve/images.py:131-149,220-237,267-283` — 子プロセス環境の構築・上書き、起動、非ゼロ終了の失敗処理。
