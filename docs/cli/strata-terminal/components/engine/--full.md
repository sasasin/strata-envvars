# `--full`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。対象リポジトリの状態は `main...origin/main` で、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata components engine` |
| オプション | `--full` |
| 別名 | なし |
| 値 | 値を取らない真偽フラグ |

## 役割

ローカル component フォルダーにある、この PC で起動可能なエンジンパッケージを調べるとき、manifest に登録されたファイルすべての SHA-256 を検証します。省略時は入口実行ファイルだけをハッシュ検証する簡易確認です。どちらの場合も、パッケージの選定・状態表示を行う読み取り専用コマンドで、エンジンをダウンロードしたり展開したりしません。

## 使い方

```sh
strata components engine --full
```

## 値と既定値

`argparse` の `store_true` で定義され、値は不要です。既定値は `false`、指定時は `true` です。値を後置する形式ではありません。CLI 側でこのフラグ固有の範囲検証や補正はありません（`strata_cli/cli.py:132-138`）。同じコマンドには `--backend`、`--components-dir`、`--output` も定義されています。

## 実行時の動作

コマンド処理は `a.full` を `engine_component.status(..., full=a.full)` に渡し、status は選定処理 `resolve(..., full=full)` に渡します（`strata_cli/cli.py:2014-2020`、`strata_control/engine_component.py:969-985`）。

`--full` の有無にかかわらず、検査対象の各 manifest 登録ファイルについて存在、通常ファイルであること、component フォルダー外を指さないこと、manifest 記載サイズとの一致を確認します。加えて署名検証も行います。省略時は入口ファイルだけ、指定時はその package の全登録ファイルについて SHA-256 を照合します（`strata_control/engine_component.py:402-427, 911-918`）。

ハッシュ対象はフォルダー内の全ファイル一般ではなく、manifest の `files` に列挙されたファイルです。また、OS/platform、backend、runtime version、GPU architecture、必要な NVIDIA driver の適合条件を通過した候補だけが署名・ファイル検証へ進みます。複数の適合候補がある場合はそれぞれを検証してから使用可能候補を選びます。`--backend` は適合候補を変え、`--components-dir` は調べる component ルートを変えるため、間接的に検証対象も変わります（`strata_control/engine_component.py:859-918`）。

ハッシュ読み取りが失敗するか manifest の digest と異なる場合、一度 0.5 秒待って再試行します（`strata_control/engine_component.py:386-399`）。

## 適用条件と副作用

このオプションは `strata components engine` の状態確認にのみ適用され、エンジン起動処理には渡されません。起動経路の `engine_component.expand` は `full=True` で `resolve` を呼ぶ実装です（`strata_cli/cli.py:2014-2020`、`strata_control/engine_component.py:957-966`）。

指定時は manifest 登録ファイル全体を読むため、既定時より読み取り I/O が増えます。ソース上、このオプションによるファイル書き込み、ネットワークアクセス、エンジンプロセス起動はありません。CLI は処理後も「nothing was downloaded or changed」と表示します（`strata_cli/cli.py:2027-2041`）。

## 出力とエラー

- 有効なエンジンが見つかった場合、終了コードは `0` です。人間向け出力では component フォルダー、PC の platform/backend、インストール済み package、選択エンジンのパスと version を表示します。
- 適合エンジンがない場合や、唯一の適合候補で完全性検査に失敗した場合、`status` は `usable: false` と notice を返し、CLI は notice を stderr に出して終了コード `5` を返します。破損した候補があっても別の有効候補が残れば、その候補を選んで `0` になります（`strata_control/engine_component.py:919-936, 982-988`、`strata_cli/cli.py:2021-2041`）。
- `--output json` を併用すると、同じ report を JSON で stdout に出力します。成功可否は `ok` と `usable` に反映され、終了コードは人間向け出力と同じです（`strata_cli/cli.py:2023-2026`）。

## 根拠

- 索引上の配置とコマンド scope: `docs/cli/README.md:197-205`。調査基準と文書配置規約: `docs/cli/001_investigation.md:15-22, 51-69, 71-115`。
- parser 定義と CLI 呼び出し: `strata_cli/cli.py:132-138, 2014-2041`。
- ファイル検証・候補選定・status report: `strata_control/engine_component.py:386-427, 859-936, 969-988`。

調査範囲は上記 commit の checkout に含まれる Terminal CLI と `strata_control/engine_component.py` です。CLI の `--help`、Release 配布物、各 OS/backend の実機挙動は確認していません。記述は同一 revision の parser と処理実装に基づきます。
