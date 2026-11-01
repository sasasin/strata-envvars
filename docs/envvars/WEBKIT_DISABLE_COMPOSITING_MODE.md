# `WEBKIT_DISABLE_COMPOSITING_MODE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数動作は対象外。

## 役割

Strata のデスクトップ診断情報に、この変数が設定されていれば値を記録します。Strata の描画処理を切り替える環境変数としての読み取りや判定は見つかりませんでした。値の意味や WebKitGTK 側での効果は、この Strata ソース調査からは説明できません。

## 値と判定

この変数に対する値の parse や有効・無効判定はありません。共通の `graphics_environment()` が名前リスト中の変数を `std::env::var(n)` で読み、読み取りに成功した値を `  {名前}={値}` の文字列にします。

| 状態 | Strata の診断情報での扱い |
|---|---|
| 未設定 | 出力されない |
| 空文字 | `  WEBKIT_DISABLE_COMPOSITING_MODE=` として出力される |
| Unicode 文字列の値 | 文字列全体をそのまま出力する。数値化、真偽値判定、大小文字変換はしない |
| Unicode でない値 | `std::env::var` がエラーとなるため出力されない |

## 有効になる条件

描画機能を有効化する条件は Strata 側にはありません。診断情報を生成する経路で、生成時点のプロセス環境に値が設定されていると、その値が記録対象になります。ソース中のトラブルシュート文書は、空白または白色のウィンドウに対する手動起動例として `WEBKIT_DISABLE_COMPOSITING_MODE=1 ./@APPIMAGE@` を案内していますが、これは Strata が値を解釈する実装の根拠ではありません。

## 実行時の詳細

値は `graphics_environment()` が呼ばれるたびに環境から取得され、static cache はありません。クラッシュレポート生成時には `crash_report()` がこの関数の結果を `Graphics session` 欄に追加します。`--save-logs` 用のログ生成でも同じ情報が出力されます。対象変数について、Strata が値を書き換える処理、警告、終了・失敗分岐は確認できませんでした。

## 根拠

- `apps/desktop/src-tauri/src/desktoplog.rs:186-194` — 描画環境変数名の一覧と、`std::env::var` による読み取り・文字列化。
- `apps/desktop/src-tauri/src/desktoplog.rs:250-259,281-289` — クラッシュレポートの `Graphics session` 欄への追加。
- `apps/desktop/src-tauri/src/desktoplog.rs:310-320` — `--save-logs` の出力への追加。
- `apps/desktop/tester/common-troubleshoot.txt:19-24` — ウィンドウが白い場合の手動起動例。この記載は外部側の効果を Strata の実装として示すものではありません。
