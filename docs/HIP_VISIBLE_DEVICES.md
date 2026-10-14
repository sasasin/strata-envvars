# `HIP_VISIBLE_DEVICES`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。対象は Strata 所有ソース。HIP runtime 自身による値の解釈は対象外。

## 役割

AMD/HIP 実行時に Strata がプロセスへ渡す GPU 選択環境変数です。Strata 本体はこの値を GPU 番号リストとして独自に parse しません。HIP runtime が列挙する GPU の番号を `HIP_VISIBLE_DEVICES` の設定に合わせる前提で、Strata のサーバーは設定ファイルの GPU 選択を子エンジンへ渡します。エンジンの `--gpu` オプションも、GPU runtime の初期化前にこの環境変数を設定します。

## 値と判定

| 経路 | Strata が設定する値 | 判定・優先順位 |
|---|---|---|
| 既存プロセス環境からエンジンを起動 | 原則、継承した値をそのまま保持 | Strata のサーバーは `os.environ` のコピーから子環境を作る。HIP backend で config の GPU 選択がなければ、この変数を server 側では書き換えない。 |
| Server の HIP backend、config に GPU 選択あり | `hip_visible(cfg)` が返す整数をカンマ区切りにした文字列（例: `1,0`） | 1 GPU 以下で有効な `hip_ordinal` があればそちらを優先。空白を除いた整数へ変換し、整数でなければ config の通常の GPU 選択へ fallback。通常選択は `ordered_gpus(cfg)`。その後 config の `env` が同名キーを持てば文字列化して上書きする。 |
| エンジン起動時に `--gpu VALUE` を指定 | `VALUE` をそのまま設定 | 既存値と異なり、既存値が空でなければ warning を stderr に出す。POSIX では `setenv(..., 1)`、Windows では `_putenv_s` で上書き。 |
| 画像生成の HIP backend、画像 config に `gpu` あり | config の `gpu` を `str()` した値 | `image_env()` が継承環境へ設定し、その後 config の `env` が同名キーを上書きできる。 |

エンジンの `--gpu` 設定処理は空文字・数値範囲・リスト形式を検証せず、引数文字列を環境へ設定します。サーバーが生成する値は整数のカンマ区切りですが、環境から直接渡された値と画像 config の値について、Strata は `HIP_VISIBLE_DEVICES` 固有の文字列検証を行いません。どの値を HIP runtime が受け付け、どう列挙へ反映するかは外部 runtime の仕様なので、ここでは断定しません。

## 有効になる条件

- Strata エンジンの `--gpu` 経路は HIP または `STRATA_HIP_GFX906` の build で `HIP_VISIBLE_DEVICES` を選びます。CUDA build では同じコードが `CUDA_VISIBLE_DEVICES` を選びます (`src/program/generate.cpp:1843-1864`)。
- Server 側の設定は `cfg["backend"] == "hip"` の場合に限られます。選択済み `gpu`/`gpus` を runtime の番号へ変換し、子エンジン起動時の env として渡します (`serve/server.py:2668-2681,2788-2805,6700-6702,6736-6754`)。
- Windows では setup が記録した `hip_ordinal` が、単一 GPU config の `gpu` より優先されます。これは setup が HIP engine の `strata-device --list-devices` 出力から得る runtime 番号です。Linux では setup の KFD 順と HIP の順が一致する前提で config の GPU 番号を使います (`setup.py:2654-2675,2761-2779`; `serve/server.py:2668-2681`)。
- Server config の `env` に同名キーがある場合、サーバーが GPU 選択から作った値を上書きします。画像生成も同様に GPU 指定後に `env` を適用します (`serve/server.py:2791-2805`; `serve/images.py:131-149`)。
- setup の HIP device probe は親の環境をコピーし、`PATH` のみ追加して `strata-device --list-devices` を起動します。したがって、既に設定されている `HIP_VISIBLE_DEVICES` は probe 子プロセスにも継承されます (`setup.py:2658-2671`)。

## 実行時の詳細

通常の server 起動では `child_env()` が `os.environ` をコピーし、HIP config が GPU を選んでいれば `HIP_VISIBLE_DEVICES` を組み立てます。config の `env` を反映した後に HIP 用ライブラリ／一時ディレクトリ環境の調整を行います。得られた env は `StrataEngine` に渡されます。replica 起動でも各 replica config に対して `child_env()` を作ります (`serve/server.py:2788-2805,6535-6552,6700-6754`)。

エンジンの起動コードは GPU runtime への最初の呼び出しより前に引数列を走査します。`--gpu` があれば既存の `HIP_VISIBLE_DEVICES` を調べ、値が非空かつ引数と異なる場合に `warning: --gpu ... overrides HIP_VISIBLE_DEVICES=... from the environment` を stderr へ出し、環境を上書きします。空の既存値では warning は出ません。引数は後の option loop でも消費されます。Qwen3.6-35B 系の経路も、この共通 startup が先に `--gpu` を適用してから family runner へ移ります (`src/program/generate.cpp:1843-1865`; `src/qwen35/q36_engine.cu:2359-2365`)。

`strata-device --list-devices` は共通 device API の列挙結果を表示します。device API のコメントも、列挙番号は HIP/CUDA の visible-device 変数が決める番号として扱っています。`STRATA_HIP_GFX906` build では、列挙された全 GPU の wave size を調べ、wave32 の GPU があれば `HIP_VISIBLE_DEVICES` で隠すよう案内して終了コード 2 を返します (`include/strata/core/device.hpp:41-44`; `src/core/device_main.cpp:43-62`; `src/program/generate.cpp:2275-2290`)。

## 根拠

- `serve/server.py:2668-2681` — `hip_visible()` の `hip_ordinal` 優先と config GPU fallback。
- `serve/server.py:2788-2805,2849-2862` — 子エンジン用環境、config `env` の適用順、vision encoder の環境設定。
- `serve/server.py:6535-6552,6697-6754` — replica と通常 engine への env 引き渡し。
- `serve/images.py:131-149,220-235` — HIP 画像 config の GPU 設定、config `env` による上書き、`sd-cli` への env 引き渡し。
- `src/program/generate.cpp:1843-1865` — `--gpu` による起動前の環境上書きと warning。
- `src/program/generate.cpp:2275-2290` — gfx906 build での GPU 列挙と非対応 wave size の診断。
- `include/strata/core/device.hpp:41-47`, `src/core/device_main.cpp:43-62` — device 番号の扱いと `--list-devices`。
- `setup.py:2654-2675,2761-2779` — HIP runtime device probe と Windows の HIP ordinal 対応。
