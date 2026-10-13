# `ROCM_PATH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。対象は Strata 所有のコード。

## 役割

Linux で AMD GPU 用 HIP エンジンをビルドするとき、システムにある ROCm のルートディレクトリを指定します。ここにある `bin/hipcc`、hipBLAS、HIP 開発ファイルが条件を満たせばその ROCm を使います。使えなければ、GPU のアーキテクチャに対応する AMD TheRock の ROCm wheel を `.venv` に導入して使います。

## 値と判定

| 値 | Strata の処理 |
|---|---|
| 未設定 | `/opt/rocm` をシステム ROCm の候補にする |
| 空文字 | `os.environ.get("ROCM_PATH") or "/opt/rocm"` により、未設定と同じく `/opt/rocm` を候補にする |
| 空でない文字列 | その文字列を `Path` に渡して候補ルートにする |

文字列の trim、環境変数や `~` の展開、絶対パスへの変換はこの読み取り箇所では行いません。候補ルートに `bin/hipcc` と `lib/libhipblas.so*` の両方がある場合に、システム ROCm のバージョンと開発ファイルを確認します。ROCm バージョンは `include/rocm-core/rocm_version.h` の major/minor 定義から読みます。ヘッダーがないなどでバージョンを読めない場合は `None` となり、必要な開発ファイルがそろっていればバージョン条件を通ります。

根拠: `setup.py:2525-2531,2543-2553`。

## 有効になる条件

`ROCM_PATH` の読み取りは `rocm_root()` 内にあり、HIP エンジンの再ビルドが必要な場合に `build_engine_hip()` から呼ばれます。既存 HIP エンジンがソース、対象 GPU アーキテクチャ、CPU ISA 条件を満たし、必要な vision バイナリもそろっていれば、`build_engine_hip()` は早期 return するため、この実行では値を読みません。通常のセットアップで Windows の AMD は用意済み HIP エンジンを使う経路であり、Linux のようにこの変数でシステム ROCm を選ぶ経路ではありません。一方、同梱の `tools/hip/build_windows.bat` は TheRock wheel から得たルートを `ROCM_PATH` に設定してから Windows 用ビルドを実行します。このスクリプトは開始時点の利用者の `ROCM_PATH` を読みません。

候補のシステム ROCm は次の条件を満たす場合に選ばれます。

- `bin/hipcc` と `lib/libhipblas.so*` が存在する。
- 読み取れたバージョンが ROCm 7.0 以上である（バージョンを読めない場合も可）。
- `lib/cmake/hip-lang/hip-lang-config.cmake`（確認する複数の lib 配下のいずれか）と `include/hip/hip_runtime.h` が存在する。

条件に合わないと TheRock wheel 側に進みます。読み取れた ROCm が 7.0 未満なら必要バージョンと wheel への切替を警告し、HIP 開発ファイルが足りなければ不足ファイル名と wheel への切替を警告します。hipcc または hipBLAS がない場合は、このシステム ROCm の検査ブロックに入らず wheel 側へ進みます。wheel のインデックスは対象 GPU アーキテクチャから選ばれ、二つの GPU ファミリーにまたがる場合はシステム ROCm 7 が必要としてエラーになります。

根拠: `setup.py:2534-2564`。呼び出し経路と Windows の分岐: `setup.py:5433-5456`。Windows 用スクリプトの設定: `tools/hip/build_windows.bat:48-62`。

## 実行時の詳細

環境変数は `rocm_root()` が呼ばれた時点で読み取られ、プロセス内に値をキャッシュしません。セットアップの途中で値を変えた場合、後続の呼び出しはその時点の環境を読みます。

システム ROCm が採用された場合、`rocm_root()` は選んだルートと `lib` を返します。TheRock wheel が採用された場合は `.venv` に wheel を導入し、`rocm-sdk path --root` から得たルートと GPU ファミリー用ライブラリディレクトリを返します。`build_engine_hip()` はどちらの場合も、ビルドに使うルートに合わせて `ROCM_PATH` と `HIP_PATH` をプロセス環境へ設定し直し、`LD_LIBRARY_PATH` と `PATH` に関連ディレクトリを追加します。また、ルートを CMake の HIP compiler root、prefix path、HIP flags にも渡します。したがって、入力した `ROCM_PATH` がシステム ROCm 条件を満たさず wheel に切り替わった場合、後のビルドで使われる `ROCM_PATH` は wheel 側のルートになります。

根拠: `setup.py:2550-2596,2655-2673`。CMake の configure/build は同じプロセス環境を継承して `subprocess.run` から実行されます（`setup.py:374-382,3289-3311`）。

## 文書との照合

`docs/AMD_HIP.md:31-38` は、Linux セットアップで `/opt/rocm` または `$ROCM_PATH` にあるシステム ROCm 7 を使い、それ以外では TheRock wheel を使うと説明しています。実装では、システム ROCm に hipcc、hipBLAS に加えて HIP 開発ファイルが必要です。また、バージョンヘッダーが読めない場合はバージョン比較を通過し得るため、文書の説明は実装の全条件を列挙してはいません。

## 根拠

- `setup.py:2543-2559` — `ROCM_PATH` の読み取り、`/opt/rocm` 既定値、システム ROCm の採用条件と警告。
- `setup.py:2534-2540` — HIP 開発ファイルの確認。
- `setup.py:2560-2596` — TheRock wheel の選択・導入とルート／ライブラリディレクトリの決定。
- `setup.py:2632-2673` — エンジン再ビルドの早期 return、変数の再設定、CMake への ROCm パス引き渡し。
- `setup.py:5433-5456` — AMD の Windows 用意済みエンジン経路とビルド呼び出し。
- `tools/hip/build_windows.bat:48-62` — wheel のルートを `ROCM_PATH` に設定して Windows ビルドへ渡す処理。
- `docs/AMD_HIP.md:22-41` — Linux AMD セットアップについての文書説明。
