# `DIST_DIR`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`DIST_DIR` は Windows 用 HIP ビルドスクリプト `tools/hip/build_windows.bat` 専用の出力先指定です。環境から値を読み、未定義なら Strata checkout の `dist` を既定値にします。その値を同梱パッケージャーの `--out` に渡し、`strata-windows-x64-hip.zip` と展開用ステージングディレクトリの配置先に使います。Strata の実行時エンジンや通常の CLI はこの名前を読みません。

## 値と判定

| 状態 | 動作 |
|---|---|
| 未定義または空値 | `if not defined DIST_DIR` により `%SRC%\dist` を設定します。 |
| 定義済み | 値をそのまま保持し、引用符で囲んで `package_windows.py --out` に渡します。 |

値を数値・真偽値として変換したり、空白除去、パス正規化、範囲制限、CLI 引数との優先順位判定を行う処理はありません。スクリプトに `DIST_DIR` 用の CLI 引数はなく、ビルド開始時に環境値を確認して既定値を補います。Windows バッチの `setlocal` 内での設定なので、このスクリプト内の既定値などは呼び出し元環境へ永続化しません。

## 有効になる条件

Windows 上で `tools/hip/build_windows.bat` を実行し、ビルド工程がパッケージ工程まで到達した場合に使われます。バッチの説明でも任意の設定項目として列挙されています。OS/backend の実行時分岐やモデル状態には依存しません。

## 実行時の詳細

バッチはリポジトリのルートを `SRC` に設定し、`DIST_DIR` が未定義なら `%SRC%\dist` を割り当てます。続くエンジンと（設定に応じた）画像 reader のビルドが成功した後、`package_windows.py` に `--out "%DIST_DIR%"` として渡します。パッケージャーはその下に `strata-windows-x64-hip` ステージングディレクトリを作り、ZIP を `<DIST_DIR>\strata-windows-x64-hip.zip` に書きます。ZIP と同名の既存ファイルは作成直前に削除されます。

出力先の値に対する事前検証や fallback はありません。パッケージャーのディレクトリ作成・ファイル操作が失敗すれば Python の失敗出力が発生し、バッチは `|| exit /b 1` により非ゼロ終了します。成功した場合は `Done: <DIST_DIR>\strata-windows-x64-hip.zip` を表示します。スクリプト内で `DIST_DIR` を読み取るのは既定値の設定とパッケージャー呼び出し・成功表示の箇所で、実行中に値を再読込・キャッシュする helper はありません。

## 根拠

- `tools/hip/build_windows.bat:13-24` — Windows HIP ビルドの任意設定として `DIST_DIR` を列挙。
- `tools/hip/build_windows.bat:25-32` — バッチのローカル環境を開始し、未定義時に `%SRC%\dist` を既定値として設定。
- `tools/hip/build_windows.bat:114-118` — パッケージャーへ `--out` として渡し、成功表示に使用。
- `tools/hip/package_windows.py:82-97` — `--out` を必須の `Path` 引数として受け取り、ステージング先を作成。
- `tools/hip/package_windows.py:190-199` — `<out>/strata-windows-x64-hip.zip` を置き、同名 ZIP を削除してから生成・表示。

候補一覧 `docs/envvars/000_envvers.md` に掲載されている名前ですが、確認できた参照は上記の Windows HIP ビルド用バッチと、それが呼ぶパッケージャーへの値の転送です。Strata のランタイム環境変数としての実装は確認できません。
