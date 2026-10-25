# `STRATA_USE_HIP`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

この名前は `000_envvers.md` の候補に含まれていますが、調査した Strata ソースでは環境変数として読み取られていません。`getenv`、Python の `os.environ`、JavaScript の `process.env` などによる値の参照は見つからず、実装中の参照は C/C++ の `#if defined(STRATA_USE_HIP)` 等のコンパイル時条件です。

HIP バックエンド用のコンパイル定義として、ビルド時に HIP 固有の実装を選ぶ名前です。通常の起動環境に `STRATA_USE_HIP=1` などを設定しても、このマクロの有無は変わりません。

## 値と判定

環境変数としての値の判定、既定値、空文字や無効値の扱いはありません。実行時に値を parse するコードがないため、プロセス起動後の環境変更も Strata のこの名前の処理には影響しません。

関連するビルド設定は別名の CMake オプション `STRATA_ENABLE_HIP` です。これは CMake 上で既定 `OFF` で、`ON` のときに `cmake/hip_backend.cmake` が読み込まれます。同ファイルは `strata_hip_runtime` interface target に `STRATA_USE_HIP=1` を compile definition として付与します。したがって、意味を持つのは実行時環境の値ではなく、ビルド構成とコンパイル対象に伝播した定義の有無です。

## 有効になる条件

`STRATA_ENABLE_HIP` を有効にしたビルドで `strata_hip_runtime` をリンクするターゲットに対して定義されます。Strata の CMake はこの設定を CUDA バックエンドと別の wave32 HIP バックエンドとして扱い、両者の同時有効化を拒否します（gfx906 向けの互換ビルドは別経路です）。

## 実行時の詳細

コンパイル時条件は GPU runtime を扱うコードなどで HIP と CUDA の実装を分けます。たとえば `src/core/device.cu` は定義時に HIP デバイスの arch 情報を参照し、`src/core/device_main.cpp` は定義時に compute capability ではなく HIP arch を表示します。これらはビルド済みバイナリに組み込まれる分岐であり、環境変数の設定で切り替わる分岐ではありません。

この候補名が環境変数として実際に Strata の処理を変える値域、ログ、CLI との優先順位や子プロセスへの伝播は確認できません。ここではコンパイル定義として確認できる範囲だけを説明しています。

## 根拠

- `CMakeLists.txt:82-83,109-116` — 別名の CMake オプション `STRATA_ENABLE_HIP` は既定 `OFF`。有効時に HIP backend の CMake ファイルを include する。
- `cmake/hip_backend.cmake:95-108` — `strata_hip_runtime` を作成し、`STRATA_USE_HIP=1` を interface compile definition として設定する。
- `CMakeLists.txt:220-228` — `STRATA_ENABLE_HIP` 経路で runtime target として `strata_hip_runtime` を選択する。
- `src/core/device.cu:29-32,71-73,101-106` — マクロでコンパイル時に HIP 向けの arch 情報処理・表示を選ぶ。
- `src/core/device_main.cpp:65-73` — マクロ定義の有無に応じて HIP arch または CUDA compute capability を出力する。
- `src/core/device.cu:296-305` — gfx906 互換ビルドは `STRATA_USE_HIP` を使わない別分岐である旨と、HIP 分岐を確認できる。
