# `STRATA_ROCM_VERSION`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリ自身の環境変数動作は対象外。

## 役割

Strata の HIP エンジンをビルドするため setup が AMD TheRock の ROCm Python wheel を選ぶとき、インストールする `rocm` パッケージのバージョンを指定します。Strata エンジンの実行時設定ではありません。

Linux の `setup.py` では、システム ROCm を使用できず、かつ HIP エンジンのビルドが必要な場合に wheel 選択へ使われます。Windows の `tools/hip/build_windows.bat` では、Windows 向け HIP ビルド用の wheel バージョン指定にも使われます。

## 値と判定

| 呼び出し経路 | 未設定 | 空文字 | その他の設定値 |
|---|---|---|---|
| Linux `setup.py` | GPU ファミリー別の推奨版を選び、配布 index から必要なら同じ 7.x 系、次に同じ major の最新へ fallback | `os.environ.get(...) or None` のため未設定と同じ | 文字列をそのまま指定版として使い、index の一覧確認や推奨版への fallback を行わない |
| Windows `tools/hip/build_windows.bat` | `10.2.0a20260930` を設定 | `if not defined` により通常は未定義扱いとなり、同じ既定値を設定 | 文字列をそのまま `rocm[...] ==値` の pip 要求と package metadata の引数に使う |

Linux では空白除去、大小文字変換はありません。空白だけの値も空文字ではないので override として扱われます。TheRock index にその指定版がなければ setup 側では別版を探さず、pip のインストールエラーになります。`gfx1151` 用では、`rocm_vkey()` が版を認識し、その major/minor が 7.11 未満の場合に Strix Halo の注意警告が追加されます。認識できない形式はこの比較で `(9, 0)` とみなされるため、この警告条件には該当しません。

## 有効になる条件

- Linux `setup.py` が HIP エンジンを新規作成または再ビルドし、`rocm_root()` で使えるシステム ROCm が見つからないときに wheel バージョンへ適用されます。システム ROCm の `hipcc`、hipBLAS、必要な開発ファイルが揃い、検出版が 7.0 以上（または版を読めない）ならシステム版が先に使われ、この変数は wheel 選択に関与しません。
- Linux で既存のローカル HIP エンジンのソース hash、対象 GPU arch、CPU ISA 条件が一致すると、ビルド関数は「既にビルド済み」として戻ります。この場合も ROCm の再選択は行われません。既定の wheel キャッシュを再利用する最適化も、override がない場合に限られます。
- Windows の通常の `setup.py` は AMD 向け既成エンジンを扱い、この変数で engine 用 ROCm を選びません。Windows 用ソースビルドスクリプト `tools/hip/build_windows.bat` を実行する場合は、そのスクリプトが変数を読みます。
- GPU ファミリーごとの index 選択は別変数 `STRATA_ROCM_INDEX` が override できます。`STRATA_ROCM_VERSION` は index URL や GPU architecture、エンジンの起動時設定を変更しません。

## 実行時の詳細

Linux では `setup.py` のモジュール読み込み時に `ROCM_VERSION_OVERRIDE` として一度読み取ります。wheel が必要なビルドでは `rocm_wanted()` が override の有無を判定し、override がある場合は指定文字列をそのまま返します。なければ index にある `rocm` package のバージョン一覧を取得し、GPU ファミリーの pin を基準に版を選びます。index を読めなければ pin を維持して後続の pip 処理へ進みます。選んだ版と index が既存 stamp と異なる場合、setup は「Installing ROCm ...」を表示して `.venv` に `rocm[libraries,devel]` をインストールし、選択した版と index を stamp に保存します。

Windows の `build_windows.bat` は、環境変数の値と必要な device architecture extras を組み合わせて venv 内の stamp と比較します。一致しなければ「Installing ROCm ...」を表示し、pip に厳密な `rocm[extras]==version` を要求してから engine をビルド、配布 zip 作成時にも同じ値を渡します。pip、ビルド、package 処理が失敗するとバッチは非ゼロ終了します。

## 根拠

- `setup.py:1834-1839`: Linux の既定版、環境変数の読み取り、override 値。
- `setup.py:1884-1920`: index における版選択、override の優先、gfx1151 の警告。
- `setup.py:2543-2581`: システム ROCm を優先する条件、wheel の選択・インストール・stamp。
- `setup.py:2632-2673`: エンジン再ビルド条件と、ROCm 選択後の HIP ビルド経路。
- `tools/hip/build_windows.bat:13-23,36-46,82-84`: Windows ビルドでの既定値、厳密 pin、stamp 判定、package への引き渡し。
- `docs/AMD_HIP.md:31-38`: Linux setup の GPU ファミリー別 wheel pin と override の記述。上記の条件差は現行ソースで確認した。
