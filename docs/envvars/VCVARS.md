# `VCVARS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。Strata の Windows packaging script にある読み取りを対象とし、外部ツールの挙動は対象外。

## 役割

`VCVARS` は `packaging/build_vision_windows.bat` が Visual Studio の `vcvars64.bat` の場所を保持し、必要時に呼び出すための環境変数です。このスクリプトが作る Windows CUDA engine package 用の `strata-vision.exe` に関係します。Strata の engine 実行時設定ではありません。

## 値と判定

スクリプトは値を数値や真偽値として parse せず、パスとして `call` に渡します。

| 状態 | 処理 |
|---|---|
| 最初の `where cl` が成功 | Visual Studio 環境をすでに使えると判定し、`VCVARS` は参照されず、値にかかわらずこの用途では無視される |
| `where cl` が失敗し、`VCVARS` が定義済み | 自動探索では上書きせず、値を `call` する |
| `where cl` が失敗し、`VCVARS` が未定義または空 | 3か所の Visual Studio 2022 候補から `vcvars64.bat` を探し、最初に見つけたパスを設定して `call` する |
| `where cl` が失敗し、定義済みの値も探索結果もない | 呼び出しを行わず、後段の `where cl` が失敗すれば終了コード 1 で終了する |

自動探索の順序は `%ProgramFiles%\Microsoft Visual Studio\2022\BuildTools`、`%ProgramFiles%\Microsoft Visual Studio\2022\Community`、`%ProgramFiles(x86)%\Microsoft Visual Studio\2022\BuildTools` です。各候補に `VC\Auxiliary\Build\vcvars64.bat` が存在する場合だけ採用します。先に `VCVARS` が定義済みなら候補が見つかってもその値を保ちます。明示値そのものは事前に存在確認されず、呼び出し後に `cl.exe` が見つかるかで成否を確認します。

## 有効になる条件

この読み取りは Windows packaging 用バッチ `packaging/build_vision_windows.bat` を実行し、かつ冒頭の `where cl` が失敗した場合に限られます。スクリプトの引数 `cuda12` / `cuda13` と stage folder の検証後、CUDA toolkit と llama.cpp の確認を経てから MSVC 環境を調べます。すでに `cl` が PATH 上にある場合は、その環境を使い `VCVARS` は見ません。

`VCVARS` を呼び出した後も `where cl` が失敗する場合は `cl.exe not found: run this from an x64 Native Tools prompt` を表示して `exit /b 1` します。成功すれば CUDA architecture を設定し、CMake configure、`strata-vision` の build、stage folder へのコピー、package metadata の記録へ進みます。それぞれの失敗はバッチの `|| exit /b 1` で終了します。これは setup の環境変数 `STRATA_VCVARS` とは別名・別経路です。

## 実行時の詳細

`setlocal` の後に評価されるため、このバッチ内の自動設定はバッチのローカル環境に限られます。`VCVARS` が事前に設定されていて、かつ `cl` が見つからない場合は `call "!VCVARS!" >nul` を実行します。`vcvars64.bat` の標準出力は捨てられます。その後の `where cl` が環境初期化を確認する判定点です。スクリプトは `VCVARS` の値に関する独自の警告や成功ログを出しません。最終成功時は生成した `strata-vision.exe` のパス、variant、architecture を表示します。

この変数を読むのは build script の実行中です。Strata engine / server の起動時やリクエストごとの読み取りは確認できません。また、このスクリプトから別プロセスへ `VCVARS` 自体を転送する処理もありません。

## 根拠

- `packaging/build_vision_windows.bat:1-19` は、このスクリプトが Windows CUDA engine package 用の画像 reader を作り、成果物を stage folder にコピーする用途であることを示します。
- `packaging/build_vision_windows.bat:43-49` は、`cl` が見つからない場合だけ Visual Studio 2022 の候補を探索し、`VCVARS` が未定義のとき候補を設定して `call` し、その後の `where cl` 失敗でエラー表示と終了コード 1 にする処理です。
- `packaging/build_vision_windows.bat:57-65` は、環境確認後の CMake build・コピー・metadata 記録と、成功時の出力を示します。
- `setup.py:2357-2363` は setup が別変数 `STRATA_VCVARS` を読み、明示パスを確認する処理です。これは `VCVARS` の読み取りではありません。

