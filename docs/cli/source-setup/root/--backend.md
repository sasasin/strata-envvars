# `setup.py --backend`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（トップレベル） |
| オプション | `--backend` |
| 別名 | なし |
| 値 | `cuda`、`hip`、`sycl` のいずれか。省略時は自動選択 |

## 役割

利用する GPU backend を指定します。`cuda` は NVIDIA、`hip` は AMD、`sycl` は Intel Arc を選びます。`cuda` / `hip` は PC の GPU 検出結果とエンジンの取得・ビルド経路に反映されます。`sycl` は通常の CUDA/HIP セットアップを通らず、checkout では SYCL セットアップスクリプトへ委譲します（`terminal/setup.py:11601-11604`, `11635-11638`, `11781-11818`, `9597-9631`）。

## 使い方

```sh
# Linux: AMD GPU を明示してセットアップ
./setup.sh --setup --backend hip

# Windows: Intel Arc 用セットアップ（Linux 専用のため Windows では停止する）
START-HERE.bat --setup --backend sycl
```

通常の checkout での `sycl` は Linux で実行します。たとえば `./setup.sh --setup --backend sycl --family qwen --model Q2_0` のように指定できます。`sycl` の Windows 対応はなく、Intel Arc の setup は実験的とコードに記されています（`terminal/setup.py:9297-9320`, `11635-11638`）。

## 値と既定値

- parser は `choices=["cuda", "hip", "sycl"]` で値を制限し、既定値は指定していません（値なしは `None`）。（`terminal/setup.py:11601-11606`）
- 未指定時は、利用可能な NVIDIA GPU がなければ利用可能な AMD GPU を選びます。両方に利用可能な GPU があれば選択を尋ね、`--yes` または `--check` のときは質問の既定値（NVIDIA）を使います。（`terminal/setup.py:11783-11815`）
- 値の省略や `cuda` / `hip` / `sycl` 以外の値は `argparse` の parser で拒否されます。`terminal/setup.py` に独自の backend 値補正処理はありません（`terminal/setup.py:11444`, `11601-11606`）。

## 実行時の動作

- **`cuda`**: AMD への自動切り替えを抑止し、NVIDIA の GPU 検出・選択・CUDA toolkit 判定に進みます。Strata が使える NVIDIA GPU が見つからなければ停止します。`--cuda` は別オプションで、選択した GPU に対する CUDA toolkit の選択を制御します（`terminal/setup.py:11787-11795`, `11876-11898`, `11646-11649`）。
- **`hip`**: AMD GPU の検出・選択へ進みます。NVIDIA GPU も搭載されていても AMD を選び、Strata が使える AMD GPU がなければ停止します。複数 GPU 指定時は選択した AMD GPU の architecture 群を用いてエンジンを用意します（`terminal/setup.py:11795`, `11817-11818`, `11838-11860`）。Linux ではエンジンをローカルでビルドし、Windows では用意済み HIP エンジンを取得します。Linux のビルドは `engine/` と `build-hip/` を使い、`engine/BUILD.json` に `backend: hip` 等のメタデータを書きます（`terminal/setup.py:5656-5708`, `9597-9631`）。
- **`sycl`**: 通常の CUDA/HIP GPU 選択へ進む前に分岐します。checkout では `--backend` の値を引数列から取り除き、残りの引数を `engine/sycl/setup_intel.py` に渡します。同スクリプトがない checkout では案内を出して終了します（`terminal/setup.py:11635-11638`, `9297-9320`）。アプリ内の CONTROL モードでは Intel Arc 向けセットアップに分岐し、既存のモデルファイルを前提に pack と run 設定を準備します（`terminal/setup.py:9351-9356`, `9383-9420`）。
- `hip` / `cuda` の選択は、モデル設定に記録される backend とも連動します。HIP または SYCL の経路では生成する run config に `backend` を設定します（`terminal/setup.py:10386-10391`, `10925-10930`）。

## 適用条件と副作用

- `hip` は AMD GPU が検出されても Strata が利用可能と判定した GPU がなければ失敗します（`terminal/setup.py:11827-11839`）。Linux では AMD エンジンのビルドに C++ compiler、git、ROCm が必要です。Windows では用意済み engine が見つからないと停止し、Windows 上でのビルドは案内されません（`terminal/setup.py:5678-5699`, `9606-9612`）。
- `sycl` の checkout 経路は Windows で未対応として停止し、Linux で oneAPI（`icpx` と oneMKL）を使う別スクリプトへ委譲します。CONTROL モードも Linux のみです（`terminal/setup.py:9297-9308`, `9359-9362`）。Intel 経路のサポート範囲はコード上で実験的とされ、記載の動作確認対象は Arc Pro B70 と Arc A750 です（`terminal/setup.py:9301-9308`）。
- `sycl` は macOS の CONTROL 処理より後に判定されます。通常の macOS 起動では `terminal/setup.py` が parser を構築する前に `engine/metal/setup_mac.py` に委譲し、その parser に `--backend` は定義されていません。このため本書の parser による値の説明は通常の macOS 経路には適用できません（`terminal/setup.py:11436-11437`, `engine/metal/setup_mac.py:372-402`）。
- `--backend` は GPU の種類を選ぶもので、異なる vendor の GPU を同じモデルに混在させる指定ではありません（自動選択時の案内: `terminal/setup.py:11806-11807`）。

## 出力とエラー

- 不正値または値なしは `argparse` の使用法エラーになります。独自の backend 固有エラー表示処理はありません（parser: `terminal/setup.py:11444`, `11601-11606`）。
- `hip` 選択後に利用可能な AMD GPU がない場合、`fail()` が理由と案内を表示し、終了コード 1 で終了します（`terminal/setup.py:11838-11839`, `1049-1056`）。
- Windows の `sycl` は未対応メッセージと Linux での案内を表示し、同じく `fail()` 経由で終了コード 1 になります（`terminal/setup.py:9304-9308`, `1049-1056`）。

## 根拠

- `terminal/setup.py:11601-11606` — `--backend` の parser 定義、値の choices、既定値なし。
- `terminal/setup.py:11635-11638` — `sycl` の早期分岐と CONTROL / checkout の振り分け。
- `terminal/setup.py:11781-11818` — GPU 検出、未指定時の選択、HIP 経路の決定。
- `terminal/setup.py:11838-11898` — AMD GPU 不在時の停止と NVIDIA 経路。
- `terminal/setup.py:5656-5708`, `9597-9631` — HIP engine のビルド・取得経路と生成物。
- `terminal/setup.py:9297-9320`, `9351-9362`, `9383-9420` — SYCL の委譲、Windows / OS 条件、CONTROL モードの処理。
- `terminal/setup.py:10386-10391`, `10925-10930` — 生成 run config への backend 設定。
- `engine/metal/setup_mac.py:372-402` — macOS 側 parser の引数定義（`--backend` は含まない）。
