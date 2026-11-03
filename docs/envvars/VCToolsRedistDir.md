# `VCToolsRedistDir`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この変数は、Windows HIP エンジンの配布 ZIP を組み立てる `tools/hip/package_windows.py` が、Visual C++ runtime DLL の場所を得るために読みます。`crt_dir()` は値の下にある `x64/Microsoft.VC*.CRT` ディレクトリを探し、見つかったディレクトリから実行ファイルが import する CRT DLL を ZIP の staging directory にコピーします（`tools/hip/package_windows.py:43-48,73-79,105-127`）。通常の Strata エンジン実行時の設定ではありません。

## 値と判定

| 環境の状態 | Strata の判定と結果 |
|---|---|
| 未設定 | `os.environ.get()` は `None` を返し、`if not base` により `crt_dir()` は `None`。パッケージ作成はエラー終了します。 |
| 空文字 | 空文字も偽として同じく `None` を返し、エラー終了します。 |
| 空でないパス | `Path(base, "x64").glob("Microsoft.VC*.CRT")` で一致するディレクトリを列挙し、ソート後の最後のパスを返します。文字列の追加 parse、大小文字変換、数値・版番号の比較はしません。 |
| パスは設定済みだが一致するディレクトリがない | `hits` が空なので `None` となり、未設定時と同じエラー終了です。 |

根拠: `tools/hip/package_windows.py:73-79,122-124`。

## 有効になる条件

対象は Windows HIP の ZIP packaging 経路です。`tools/hip/build_windows.bat` は `vcvars64.bat` を呼び出してから HIP build を行い、最後に `package_windows.py` を起動します（`tools/hip/build_windows.bat:59-68,114-118`）。その実行経路では `vcvars64.bat` が設定した環境を Python プロセスが継承します。スクリプトを直接呼び出す場合は、起動側がこの変数を環境に用意する必要があります。

必須 CLI 引数 `--build`、`--rocm`、`--archs`、`--rocm-version`、`--out` に、この値を置き換える CRT ディレクトリ指定はありません（`tools/hip/package_windows.py:82-91`）。候補名の全参照を検索した範囲では、この packaging script 以外に Strata が読む箇所はありません。

## 実行時の詳細

`crt_dir()` は package 作成中に呼ばれ、CRT import の収集後に返されたディレクトリから必要な DLL をコピーします。戻り値が `None` の場合、`sys.exit("VCToolsRedistDir is not set: run this from a Visual Studio x64 developer prompt (vcvars64.bat)")` を実行します。メッセージは標準エラーに出力され、プロセスは終了コード 1 で終了します。バッチ経由なら呼び出し行の `|| exit /b 1` によりバッチも失敗終了し、完了メッセージには進みません（`tools/hip/package_windows.py:122-127`; `tools/hip/build_windows.bat:115-118`）。

パスが存在することだけでは足りず、`x64/Microsoft.VC*.CRT` に一致するディレクトリが必要です。複数一致時は文字列順で最後のパスを選びます。選んだディレクトリ内の DLL が欠けている場合は、そのファイルの `shutil.copy2` が失敗します（`tools/hip/package_windows.py:78-79,125-127`）。

## 根拠

- `tools/hip/package_windows.py:73-79` — 環境読み取り、空値判定、CRT ディレクトリ探索。
- `tools/hip/package_windows.py:82-91` — CLI 引数。CRT パスを上書きする引数はありません。
- `tools/hip/package_windows.py:105-127` — import DLL の収集、環境値不成立時の終了、CRT DLL のコピー。
- `tools/hip/build_windows.bat:59-68,114-118` — Visual Studio 環境の初期化、packaging 起動と失敗伝播。
