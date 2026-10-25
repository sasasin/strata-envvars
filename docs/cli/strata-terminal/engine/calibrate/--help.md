# `--help`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata engine calibrate` |
| オプション | `--help` |
| 別名 | `-h` |
| 値 | なし |

## 役割

`calibrate` コマンドの使用法と、この parser が受け付ける引数を表示して終了します。`--help` は Strata の個別オプションとして定義されず、`argparse.ArgumentParser` が標準で追加するヘルプ action です。`calibrate` parser は `engine` の下に作られています（`strata_cli/cli.py:41-42,174-176`）。

## 使い方

```sh
strata engine calibrate --help
```

短縮形も同じです。

```sh
strata engine calibrate -h
```

## 値と既定値

値は取りません。`-h` と `--help` は同じヘルプ action の表記です。`calibrate` の parser には `--profile` と、必須の相互排他 action（`--plan`、`--measure`、`--review-result`、`--apply-result`、`--review-rollback`、`--rollback-result`）がありますが、ヘルプ表示ではこれらの実行時指定は不要です（`strata_cli/cli.py:177-186`）。

## 実行時の動作

ヘルプには `calibrate` の usage と、その parser に登録されたオプションが表示されます。加えて、one-shot parser 群へ後から加えられる `--json` と `--quiet` もこのコマンドのスコープに含まれます（`strata_cli/cli.py:176-189,508-515`）。`help="measure, review and apply engine tuning"` は親の `strata engine --help` におけるサブコマンド一覧用の説明です（`strata_cli/cli.py:176`）。

CLI は parser を構築して引数を解析します。ヘルプ action は表示後に argparse の parser を終了させるため、校正処理 `_calibration` へは進みません（`strata_cli/cli.py:2217-2225,2142-2143`）。通常のエラー形式ではなく、argparse のヘルプ出力として標準出力に表示され、終了コードは `0` です。ヘルプ action 自体は `--profile` などの必須指定を検証する前に終了します。

## 適用条件と副作用

このヘルプは `strata engine calibrate` に対するものです。`strata` や `strata engine` のヘルプとは parser scope が異なります。

起動時、引数解析より前に `main` は `strata_control.private_files.adopt_user_defaults()` を呼びます（`strata_cli/cli.py:2217-2224`）。この関数は Windows では現在のユーザーをプロセスの既定 owner とし、既定 DACL を設定しようとします。POSIX では何もしません。関数は失敗時に `False` を返す設計で、この呼び出し位置では戻り値も使われません（`strata_control/private_files.py:349-390`）。したがってヘルプ表示でも Windows のプロセストークン設定を試みます。

ヘルプ action からは校正計画の読込、エンジン起動、レポート書込、設定変更は行われません。これらは `_calibration` の各 action に分岐した後の処理です（`strata_cli/cli.py:1059-1126`）。

## 出力とエラー

正常なヘルプ表示は標準出力に usage とオプション説明を出し、終了コード `0` で終了します。未知の引数や必須指定不足など、ヘルプ action 以外の parser エラーは `main` が `ap.error(...)` に渡します（`strata_cli/cli.py:2223-2231`）。その場合は argparse が usage/error を標準エラーへ出し、終了コード `2` で終了します。

この調査では同一 revision の CLI を実行して実際の表示を採取していません。上記の表示内容と終了動作は parser 定義および起動・dispatch 経路から確認したものです。

## 根拠

- `strata_cli/cli.py:40-45` — トップレベル parser の構築と argparse の利用。
- `strata_cli/cli.py:174-189` — `engine calibrate` parser、必須引数/action、その他の option 定義。
- `strata_cli/cli.py:508-515` — one-shot parser に対する `--json` / `--quiet` の追加。
- `strata_cli/cli.py:2217-2231` — 起動前処理、parser 解析、未知引数のエラー経路。
- `strata_cli/cli.py:2142-2143,1059-1126` — `engine` dispatch と校正 action の処理。
- `strata_control/private_files.py:349-390` — Windows の既定 owner/DACL 設定と POSIX での no-op。
