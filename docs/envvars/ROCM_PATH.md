# `ROCM_PATH`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリや GPU ドライバーが読む値の意味は対象外。

## 役割

ソース checkout から HIP backend のエンジン、HIP 画像 reader、HIP を使う画像生成器をビルドするときに、システム ROCm のルートディレクトリを指定します。`setup.py` の `rocm_root()` は値をシステム ROCm の候補として調べ、条件を満たせばそのパスを使います。使えない場合は GPU architecture に応じた AMD TheRock wheel を `.venv` に導入して使います。

この変数は実行時の Strata engine ではなく、セットアップ・ビルド処理が読むものです。

## 値と判定

| 値 | `setup.py` の扱い |
|---|---|
| 未設定 | `/opt/rocm` をシステム ROCm 候補にする |
| 空文字 | Python の `or` により未設定と同じく `/opt/rocm` を候補にする |
| 空でない文字列 | そのまま `pathlib.Path` に渡し、システム ROCm 候補にする |
| 存在しないパス、必要ファイルのないパス | システム ROCm として採用せず、TheRock wheel の経路へ進む |

前後空白の除去、文字列全体の書式検査、パスの環境変数展開はありません。空白だけの値も非空文字列としてパスに使われます。

システム候補を採用するには、少なくとも `bin/hipcc` と `lib/libhipblas.so*` が存在し、HIP の開発ファイルがそろっている必要があります。`rocm-core/rocm_version.h` からバージョンを読めた場合は 7.0 以上が必要です。バージョンヘッダーがなくバージョンを取得できない場合でも、他の要件を満たせば採用されます。古い、または開発ファイルが不足する場合は警告を出し、wheel 側へ進みます。

## 有効になる条件

- ROCm SDK を必要とする HIP ビルド経路で `rocm_root()` が呼ばれる場合に評価されます。主な呼び出し元は HIP エンジン構築、GPU HIP 画像 reader 構築、HIP backend の画像生成器構築です。
- HIP エンジンが既に構築済みでも、`--vision gpu` で GPU 画像 reader を追加構築する経路では ROCm 環境を復元するため `rocm_root()` が呼ばれます。
- システム候補を利用できない場合は GPU architecture ごとの TheRock wheel に fallback します。複数 GPU family に対応する単一の wheel index がない場合は `fail()` でセットアップを中止し、システム ROCm 7 を使うよう案内します。
- ビルド関数は選択した root を `ROCM_PATH` と `HIP_PATH` に設定し、関連する `HIP_PLATFORM`、`HIP_COMPILER`、`HIP_RUNTIME`、`PATH`、`LD_LIBRARY_PATH` も更新します。これは `setup.py` が後続ビルド用に行う環境設定です。

## 実行時の詳細

`rocm_root(archs)` は `os.environ.get("ROCM_PATH") or "/opt/rocm"` で一度値を取り、システム ROCm のファイルを確認します。未設定・空文字以外はすべてパス候補として扱います。候補の存在確認に失敗しても、その時点ではエラーにせず TheRock wheel 選択へ進みます。

システム ROCm が古い場合は `the ROCm in <path> is M.m; Strata needs 7.0 or newer: using AMD's wheels in .venv instead` の警告を出します。HIP 開発ファイルが不足する場合も不足項目を示す警告を出します。wheel の導入が必要な場合は `Installing ROCm ... for AMD GPUs into .venv (AMD's TheRock wheels, ~10 GB, no sudo) ...` と出力し、インストール先は `.venv` 内です。システムの標準位置 `/opt/rocm` 以外を指定する場合に使う値ですが、不適切な値を受け取ったこと自体を専用エラーとして報告するのではなく、通常は wheel 経路に移ります。

GPU 画像 reader の復元処理では `vision == "gpu"` かつ `hipconfig` が見つからず、かつ `ROCM_PATH` が未設定または空のときにだけ `rocm_root()` を呼んで `ROCM_PATH` などを再設定します。非空値が設定済みならこの復元分岐は通りませんが、その後の画像 reader のビルド処理でも `rocm_root()` が呼ばれるため、設定値は改めて候補として評価されます。

## 文書との照合

`docs/AMD_HIP.md` はシステム ROCm 7 を `/opt/rocm` または `$ROCM_PATH` から使い、条件が合わない場合は TheRock wheel を `.venv` に導入すると説明しています。コードではシステム ROCm の判定に `hipcc`、hipBLAS、開発ファイル、および取得可能な場合のバージョン確認も行います。ドキュメントの概要と整合しています。

## 根拠

- `setup.py:3480`: システム ROCm の最低バージョンを `(7, 0)` と定義。
- `setup.py:4482-4497`: ROCm バージョンと開発ファイルの判定。
- `setup.py:4500-4520`: `ROCM_PATH` の読み取り、`/opt/rocm` の既定値、採用条件、fallback と警告。
- `setup.py:4522-4553`: TheRock wheel の選択・導入、および wheel SDK root の取得。
- `setup.py:4619-4637`: HIP engine ビルドで root を選び、ビルド環境を設定して CMake に渡す。
- `setup.py:4690-4710`: GPU HIP 画像 reader の環境復元とビルド。
- `setup.py:4842-4847`: HIP 画像生成器ビルドで root を選び、環境を設定。
- `docs/AMD_HIP.md:98-109`: セットアップ時のシステム ROCm / TheRock wheel の説明。
