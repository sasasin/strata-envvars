# `STRATA_HIP_ARCHS`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。対象は Strata 所有ソースと同梱ビルド・パッケージ用ツール。外部ライブラリの環境変数は対象外。

## 役割

Windows の HIP エンジンを `tools/hip/build_windows.bat` でビルド・パッケージするとき、対象 GPU アーキテクチャ（`gfx...`）の一覧を指定します。アーキテクチャごとの ROCm device wheel、HIP コンパイル対象、GPU 用 vision reader、配布 ZIP の ROCm カーネルやメタデータに影響します。

この変数を Strata の通常実行時に読むコードはありません。CMake の `STRATA_HIP_ARCHS` は環境変数ではなく、`cmake/hip_backend.cmake` が `CMAKE_HIP_ARCHITECTURES` から生成してコンパイル定義に埋め込む文字列です。実行時の GPU 対応判定は、この埋め込み値を使います。

## 値と判定

値は `gfx1100;gfx1201` のようなセミコロン区切りのアーキテクチャ名です。Strata のバッチファイル自身は値を数値や名前として検証せず、セミコロンを空白に置換して `device-<arch>` の ROCm wheel 指定にし、同じ一覧を `-DCMAKE_HIP_ARCHITECTURES=...` とパッケージャーの `--archs` に渡します。

| 状態 | `tools/hip/build_windows.bat` の動作 |
|---|---|
| 未設定または空 | デフォルト `gfx1100;gfx1101;gfx1102;gfx1200;gfx1201;gfx1030;gfx1031;gfx1151` を設定 |
| 非空 | その値を対象一覧として使う。例: `gfx1150`、`gfx1030;gfx1031` |
| 不正・未対応の項目 | バッチ側の事前検査はない。ROCm wheel の導入、HIP 構成、または後続パッケージ処理で失敗し得る。HIP 構成に到達した場合、CMake は未対応名を fatal error にし、既知の未検証名には warning を出す |

大文字小文字の正規化や Strata 独自の環境変数 parse はありません。CMake 側は `CMAKE_HIP_ARCHITECTURES` 中の空白を区切りとして扱い、`gfx1100:xnack-` のようなコロン以降の属性をアーキテクチャ名から除き、重複を削除します。検証済み (`gfx1100`, `gfx1201`) とコミュニティ報告あり (`gfx1101`, `gfx1200`) は通常の status 表示、ビルド可能だが未検証の候補は warning、一覧が空または未知の名前は configure error です。区分はこの HEAD の `cmake/hip_backend.cmake` のリストに基づきます。

## 有効になる条件

- `tools/hip/build_windows.bat` を実行する場合にだけ、この環境変数を直接読みます。既定では Windows 用 HIP ビルドが有効です。Windows 以外の CMake ビルドでは、この名前ではなく CMake cache 変数 `CMAKE_HIP_ARCHITECTURES` を指定します。
- エンジンの CMake 構成は `build-hip-win/build.ninja` がない場合だけ実行されます。既にそのファイルがあると、バッチは環境変数の値を `CMAKE_HIP_ARCHITECTURES` に再設定しません。
- 同じ実行で `STRATA_VISION_HIP_ARCHS` が未設定または空なら、この値が GPU 用 vision reader の対象にもなります。`STRATA_VISION_HIP_ARCHS` を指定すれば reader の対象一覧は別になります。CPU reader はこの一覧の対象外です。
- `STRATA_NO_VISION=1` なら vision reader のビルドとパッケージをスキップしますが、エンジンの HIP 対象一覧には影響しません。

## 実行時の詳細

バッチファイルは一覧から `device-<arch>` の ROCm wheel 依存を作り、ROCm SDK の stamp と比較して必要なら SDK を導入します。続いて、ビルドフォルダーがまだ構成されていない場合に `CMAKE_HIP_ARCHITECTURES` へ一覧を渡して CMake を実行します。CMake はリストを正規化し、重複を除いたカンマ区切りの `STRATA_HIP_ARCHS` を生成します。この文字列は HIP ターゲットのコンパイル定義となり、エンジンに組み込まれます。CMake の完了時には `Strata: HIP enabled, arch ...` を表示します。

実行時、HIP エンジンは現在の GPU の `gcnArchName` からコロン以降を除き、埋め込み一覧の項目と完全一致するか確認します。対応一覧にない GPU、または wave size が 32 でない GPU には「cannot run」の理由を作ります。`strata generate` は使用する GPU のいずれかが対象外なら stderr に `strata generate: <理由>` を出して終了コード 1 で戻ります。`strata-device --list-devices` は該当 GPU の下に `cannot run: <理由>` を表示します。ここで参照されるのはビルドに埋め込まれた一覧であり、プロセス実行時に環境変数を変更しても結果は変わりません。

注意点として、既存の `build-hip-win/build.ninja` を使いながら値を変更してバッチを再実行すると、エンジンは以前のアーキテクチャで構成・ビルドされる一方、パッケージャーには今回の環境変数の一覧が渡ります。パッケージャーはその一覧を `BUILD.json`、アーキテクチャ別 ROCm kernel、kpack、tuning table の収録対象に使うため、ビルド済み engine と ZIP の表示・同梱物が食い違う可能性があります。値を変えて再ビルドするときは、既存 build folder の CMake cache も更新する必要があります。

## 根拠

- `tools/hip/build_windows.bat:13-26,41-52`: 対象用途、デフォルト値、ROCm device wheel の選択。
- `tools/hip/build_windows.bat:72-80,87-115`: build folder がない場合の CMake 設定、vision 用の既定値、パッケージャーへの引き渡し。
- `cmake/hip_backend.cmake:13-43,94-99,137`: 対応アーキテクチャの分類、正規化・重複除去・エラー、実行ファイルへ埋め込む値。
- `src/core/device.cu:29-64,70-75,224-240`: 埋め込み一覧と GPU の照合、wave32 条件。
- `src/program/generate.cpp:3110-3124`, `src/core/device_main.cpp:43-62`: engine の終了動作と `--list-devices` の表示。
- `tools/hip/package_windows.py:82-92,139-182`: `--archs` を用いた kernel、kpack、BUILD.json の組み立て。
- 関連資料 `docs/AMD_HIP.md:92-100,195-199,793-815`: Windows HIP ビルド指定例と gfx1030/gfx1031/gfx1032 の記述。これは利用例・報告であり、ビルド可能性の現行判定は CMake のコードに基づきます。
