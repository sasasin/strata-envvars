# `VCToolsRedistDir`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。対象は Strata 所有ソースと同梱ツール。

## 役割

Windows 向け HIP エンジンの ZIP を組み立てる同梱ツール `tools/hip/package_windows.py` が、同梱対象の Microsoft C++ ランタイム DLL を探す基準ディレクトリとして読みます。エンジンの実行時設定ではなく、配布 ZIP の作成時だけ使われます。

## 値と判定

`crt_dir()` は `os.environ.get("VCToolsRedistDir")` で値を読みます。値を数値や別形式へ変換せず、Python の真偽値判定を行います。

| 値 | 処理 |
|---|---|
| 未設定 | `None` を返す |
| 空文字 | 偽として扱い、`None` を返す |
| 空でない値 | `<値>/x64` の直下で `Microsoft.VC*.CRT` に一致するパスを列挙し、パス文字列の昇順で並べた最後のものを返す |
| 空でないが一致するパスがない | `None` を返す |

バージョンの数値比較、環境変数値の trim、候補ディレクトリ内の DLL の事前検証はしません。たとえば末尾の空白も値に含まれ、そのままパスの一部になります。複数候補がある場合は文字列順で選ぶため、バージョン順に選ぶ実装ではありません。

根拠: `tools/hip/package_windows.py:59-65`。

## 有効になる条件

`tools/hip/build_windows.bat` が Windows HIP エンジンの配布用 ZIP を作る段階で `package_windows.py` を呼びます。スクリプトは MSVC の `vcvars64.bat` を呼び出してから、同じバッチ内でパッケージャーを起動します。`VCToolsRedistDir` は `vcvars` が設定する変数としてパッケージャーに記載されています。通常の Strata エンジン実行や、他の backend ではこの変数を読むコードは確認できません。

根拠: `tools/hip/build_windows.bat:53-58,82-84`、`tools/hip/package_windows.py:59-61`。

## 実行時の詳細

パッケージャーはまず `strata.exe` と `strata-device.exe`、および DLL import の依存関係をたどり、Microsoft CRT DLL のうち必要な名前を `crt` 集合に集めます。ROCm DLL をステージングした後に `crt_dir()` を一度呼びます。結果が `None` なら `SystemExit` で終了し、次の文言を出します。

```text
VCToolsRedistDir is not set: run this from a Visual Studio x64 developer prompt (vcvars64.bat)
```

パスが得られた場合、依存関係から必要と判断した CRT DLL だけを、そのディレクトリからステージング先の `rocm/bin` へコピーします。ディレクトリは見つかっても必要な DLL が欠けていれば、`shutil.copy2` の失敗が伝播します。ビルド用バッチではパッケージャーが失敗すると `|| exit /b 1` によりバッチも失敗します。

根拠: `tools/hip/package_windows.py:86-107`、`tools/hip/build_windows.bat:82-84`。

## 文書との照合

`docs/AMD_HIP.md` は `tools/hip/build_windows.bat` が HIP 用の配布 ZIP を作る手順を案内しています（118-122 行）。`VCToolsRedistDir` 自体の値の選択規則や DLL コピー条件は説明しておらず、その詳細はパッケージャーの実装に基づきます。性能測定値はありません。

## 根拠

- `tools/hip/package_windows.py:59-65` — 環境変数の読み取りとディレクトリ選択。
- `tools/hip/package_windows.py:86-107` — import 依存から必要 CRT を集め、値を検査し、コピーする処理。
- `tools/hip/build_windows.bat:53-58,82-84` — vcvars の呼び出しとパッケージャーの起動。
- `docs/AMD_HIP.md:118-122` — Windows HIP 配布物のビルド手順。
