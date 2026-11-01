# `STRATA_NO_PATH`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

Windows 用 PowerShell installer `packaging/install.ps1` が、インストール先の `terminal\current\bin` をユーザー PATH と installer プロセスの PATH に追加する処理を省くための変数です。Strata CLI やエンジンが読む設定ではありません。候補一覧 `000_envvers.md` に名前がありますが、実際に値を読むのはこの installer です。

## 値と判定

値を数値・真偽値として parse せず、文字列 `'1'` と等しいかを比較します。

| 環境変数の値 | PATH 追加処理 |
|---|---|
| 未設定 | 行う |
| 空文字 | 行う |
| `'1'` | 省略する |
| その他（例: `'0'`, `'true'`, `'01'`, `' 1'`） | 行う |

判定は installer のインストール処理終盤で行われます。CLI 引数、設定ファイル、別の環境変数による上書きや優先順位はありません。既定値として別の値を設定する処理もなく、未設定は比較上 `'1'` ではないため追加側に進みます。

## 有効になる条件

- Windows 用 `packaging/install.ps1` を実行した場合に限ります。スクリプトは Windows 以外で `Die` により停止します。
- 展開・署名確認後、インストール先への移動と `terminal\current` の junction または代替 launcher の作成が済んだ後に評価されます。ここまでの処理を省略する変数ではありません。
- Linux/macOS 用 installer、Strata CLI、サーバー、エンジンでこの名前を読む箇所は確認できません。

## 実行時の詳細

値が `'1'` 以外なら、installer は Windows のユーザー環境変数 `Path` を読み、`;` 区切りの項目に `$bin`（`terminal\current\bin`）が含まれていない場合にだけユーザー `Path` へ追加します。空のユーザー `Path` は空文字として扱い、追加先を `$bin` にします。さらにこの分岐では、既にユーザー `Path` に `$bin` があっても、installer プロセスの `$env:Path` に `$bin` を追加します。

値が `'1'` なら、ユーザー `Path` の読み書きも installer プロセスの `$env:Path` の変更も行いません。インストール自体は続行し、標準出力に `Installed. Run: strata launch` と `(the program is <bin>\strata.cmd)` を表示します。それ以外の値では完了後に `Installed. Run: strata launch` と `(open a new terminal window if the command is not found yet)` を表示します。

設定はユーザー PATH の変更を永続化するかどうかに作用します。実行中の installer でも PATH 追加を反映するため、判定はインストール処理終盤の読み取りです。スクリプト内にキャッシュはなく、同じ値を行142と151で参照します。行142の `SetEnvironmentVariable` が失敗した場合の専用ログや fallback はありません。スクリプト先頭で `$ErrorActionPreference = 'Stop'` に設定されているため、例外は通常の installer 処理を停止させ、成功メッセージには到達しません。

## 根拠

- `packaging/install.ps1:18-19` は `STRATA_NO_PATH='1'` を任意設定として説明し、PATH を変更しない目的を記載しています。
- `packaging/install.ps1:20-24,34` はエラー設定と Windows 専用 installer の停止経路を定義します。
- `packaging/install.ps1:122-141` は PATH 判定より前にインストール先へ移動し、`terminal\current` と起動経路を用意することを示します。
- `packaging/install.ps1:142-152` は完全一致の判定、ユーザー PATH の重複確認・追加、プロセス PATH への追加、および結果メッセージを実装しています。
- `tests/terminal/test_tui2_023_install.py:56-64` は installer のテスト実行環境に `'1'` を設定しています。これは値が使われることの補助的な確認であり、実装上の挙動の根拠は installer 本体です。
