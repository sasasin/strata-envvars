# `VARIANT`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

`VARIANT` は実行時の Strata エンジン設定ではなく、Linux CUDA/HIP エンジン用パッケージを作るシェルスクリプトの入力です。選択したビルド系列に応じて CUDA toolkit の系列、GPU architecture の既定値、パッケージの variant 名などを決めます。エンジン本体の C++、Python サーバー、セットアップ処理が環境変数 `VARIANT` を読む箇所は確認できませんでした。

## 値と判定

| 読み取り箇所 | 未設定・空文字 | 受け付ける値 | その他の値 |
|---|---|---|---|
| CUDA Linux (`packaging/build_cuda_linux.sh`) | `VARIANT:-cuda13` のため `cuda13` として扱う | 大文字小文字を区別して `cuda12` または `cuda13` | stderr に `build_cuda_linux.sh: VARIANT must be cuda12 or cuda13` を出し、終了コード 2 |
| HIP Linux (`packaging/build_hip_linux.sh`) | `${VARIANT:?...}` により必須。未設定または空文字なら parameter expansion が失敗し、スクリプトが終了 | `rx9070`, `rx7900`, `rx6000`, `halo`, `igpu`。これら以外も `ARCHS` が非空で設定されていれば任意の名前として進行 | 未知の値で `ARCHS` も未設定または空文字なら `${ARCHS:?...}` が失敗して終了。値と `ARCHS` の組み合わせ自体の整合性検査はしない |
| HIP DeepSeek-V4.1 Linux (`packaging/build_dsv41_hip_linux.sh`) | `${VARIANT:?...}` により必須。未設定または空文字なら終了 | `rx9070`, `rx7900` は既定 architecture がある。その他の名前も `ARCHS` が非空なら使用可能 | 未知の値で `ARCHS` が未設定または空文字なら parameter expansion が失敗して終了 |

CUDA Linux では `cuda12` が CUDA 12 toolkit、既定 architecture `60;61;70;75;80;86;89`、最低 driver `575.51`、CMake option `STRATA_EXPERIMENTAL_SM60=ON` に対応します。`cuda13` は CUDA 13 toolkit、既定 architecture `75;86;89;120`、最低 driver `580.65`、同 option `OFF` に対応します。さらに `nvcc --version` から得た toolkit 系列が値と一致しなければ、stderr に `build_cuda_linux.sh: <variant> needs the matching CUDA toolkit; nvcc here is <version|missing>` を出して終了コード 2 になります。`ARCHS` が設定されていると既定 architecture を置き換えますが、variant に紐づく toolkit 系列、最低 driver、CMake option は変わりません。根拠: `packaging/build_cuda_linux.sh:15-28,31-36,63-65`。

HIP Linux の既定 architecture は `rx9070` → `gfx1200;gfx1201`、`rx7900` → `gfx1100;gfx1101;gfx1102`、`rx6000` → `gfx1030;gfx1031`、`halo` → `gfx1151`、`igpu` → `gfx1103;gfx1150` です。`ARCHS` を設定すると各既定値を置き換えます。HIP DeepSeek-V4.1 Linux は `rx9070` → `gfx1200;gfx1201`、`rx7900` → `gfx1100;gfx1101;gfx1102` で、他の variant は `ARCHS` が必要です。これらは文字列の分類であり、大文字小文字の変換や GPU 検出は行いません。根拠: `packaging/build_hip_linux.sh:23,33-40`; `packaging/build_dsv41_hip_linux.sh:15,25-29`。

## 有効になる条件

- 値が使われるのは上記のビルドスクリプトを起動したときだけです。OS/backend はスクリプト自体が Linux CUDA または Linux HIP 向けであることで限定されます。すでにビルド済みのエンジンを起動する際の runtime 条件ではありません。
- CUDA Linux では、値に合う CUDA toolkit が `nvcc` として見つかる必要があります。選択 variant と toolkit の系列が不一致、または `nvcc` の系列を抽出できない場合は終了コード 2 になります。
- HIP の未知 variant は、明示的な `ARCHS` があれば許容されます。したがって `VARIANT` 自体は GPU architecture の妥当性を判定せず、`ARCHS` は CMake の architecture 設定やパッケージ metadata へ渡されます。
- HIP エンジンの `rx9070` では、`DSV41` が未設定または空文字なら DeepSeek-V4.1 エンジンも既定でビルド・同梱されます。他 variant ではその既定は無効です。`DSV41` を明示するとこの既定を置き換えます。これは `VARIANT` と別の環境変数による相互作用です。
- Windows の `packaging/build_vision_windows.bat` にも `VARIANT` というローカル名がありますが、環境からは読みません。第1コマンドライン引数 `%~1` から設定し、`cuda12`/`cuda13` のみを大文字小文字を区別せず受け付けます（`packaging/build_vision_windows.bat:21-32`）。

## 実行時の詳細

シェルスクリプトは起動時に環境から値を取り込み、その後はシェル変数 `variant` または `V` として使います。実行中に親プロセスの環境を変更して再読込するコードや、サーバー・リクエストごとの評価、値の cache はありません。

CUDA Linux は `VARIANT` を使って既定 architecture、build/output directory 名、ビルド macro、最低 driver を選び、`cmake` と `package_engine.py --variant` に設定を渡します。最終 package metadata と build id にも値が含まれます（`packaging/build_cuda_linux.sh:15-23,34-36,63-65`）。

HIP Linux は variant 名を既定 architecture の選択、出力先既定値、ビルド状態ログ、`BUILD.json`、`package_engine.py --variant` と package notes に渡します（`packaging/build_hip_linux.sh:23-44,58,93-96,122-125`）。DeepSeek-V4.1 のスクリプトでも既定 architecture、出力先、status log、`BUILD.json` と package metadata に渡します（`packaging/build_dsv41_hip_linux.sh:15-32,43,63-65,79-81`）。

値の不足や不一致は parameter expansion のエラー、または CUDA スクリプトの明示的な stderr と終了コード 2 で観測できます。後段の configure/build/package 失敗は各スクリプトのログや標準エラー、HIP では `build.status` の `ABORT ... failed (rc=...)` 行にも記録されます。これはビルド処理の結果であり、実行中エンジンの警告や終了経路ではありません。

## 根拠

- `packaging/build_cuda_linux.sh:14-29,31-36,39-45,58-66` — 既定値、許容値、toolkit 系列照合、architecture と macro、package 引数。
- `packaging/build_hip_linux.sh:22-44,58-72,91-96,118-125` — 必須値、variant/architecture 対応、`DSV41` の既定、有効時の metadata と package 引数。
- `packaging/build_dsv41_hip_linux.sh:14-32,43-60,63-81` — 必須値、architecture 選択、status、metadata と package 引数。
- `packaging/build_vision_windows.bat:21-40,51-64,67-69` — 同名のローカル変数は環境変数ではなく位置引数に由来。
- `packaging/ENGINE-COMPONENT.md:106-113`、`packaging/README.md:31-33` — package variant とビルド系列の資料上の説明。現行スクリプトの判定根拠は上記ソース行。
- `strata_control/driver_floor.py:19-22,51-64` にも定数名 `VARIANT` がありますが、これは文字列 `cuda12` のコード定数であり、環境変数の読み取りではありません。
