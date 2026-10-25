# `--backend`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh`、`START-HERE.bat` 等からも同じ parser を使用） |
| オプション | `--backend` |
| 別名 | なし |
| 値 | `cuda`、`hip`、`sycl` のいずれか。省略時は `None` |

## 役割

モデルの setup 時に使う GPU backend を選びます。`cuda` は NVIDIA、`hip` は AMD、`sycl` は Intel Arc の実験的な経路です。GPU 選択後は、選んだ backend に応じて GPU 検出・モデル適合判定・engine の取得またはビルドが行われます（`setup.py:8548-8551`、`setup.py:8697-8710`、`setup.py:9263-9275`）。

## 使い方

Linux で AMD 経路を明示して setup する例です。

```sh
./setup.sh --setup --backend hip
```

`setup.sh` は引数を `setup.py` に渡します。Windows の `START-HERE.bat` も同じく引数を渡し、`SETUP.bat` は `--setup` を付けて委譲します（`setup.sh:6-13,76`、`START-HERE.bat:48-54`、`SETUP.bat:1-3`）。

## 値と既定値

parser は `choices=["cuda", "hip", "sycl"]` として宣言し、既定値は明示せず `None` です。値の省略は許可されますが、値の欠落やそれ以外の文字列は `argparse` の parser error になります。短縮別名はありません（`setup.py:8548-8553`）。

- `cuda`: NVIDIA 経路を選びます。省略時に NVIDIA と利用可能な AMD GPU の両方が見つかった場合に出る vendor 選択質問を通らず、NVIDIA 側へ進みます。
- `hip`: AMD 経路を選びます。省略時も、利用可能な NVIDIA GPU がなく利用可能な AMD GPU があれば AMD が自動選択されます。
- `sycl`: SYCL 専用 setup に引数を転送します。

選択値は一つです。`argparse` の通常の単一値 action なので、同じオプションを繰り返した場合は最後の値が残ります。

## 実行時の動作

`hip` の場合、setup は AMD GPU を調べ、対応 GPU がなければ「no AMD GPU Strata can use」として終了します。複数カード指定 `--gpus` は Windows では拒否されます。利用可能なカードがあれば、選択カードの architecture を集め、HIP engine の既製品取得（Windows）またはソースビルド（Linux）に進みます（`setup.py:8708-8709,8731-8776`、`setup.py:9263-9275`、`setup.py:4510-4553`）。HIP 選択時はモデルの画像 reader も HIP 用の判定経路を使い、保存する run config に `backend: hip` を記録します（`setup.py:9112-9115,9597-9605`）。一部 NVIDIA 専用扱いのモデルは AMD では警告・確認を経て続行する実装です（`setup.py:8996-9003`）。

`cuda` または backend 省略で NVIDIA 経路に入る場合、NVIDIA GPU が検出されなければ失敗します。`cuda` は CUDA toolkit の版を指定する値ではなく、toolkit の選択は別オプション `--cuda` が扱います（`setup.py:8787-8812`、`setup.py:8804-8806`）。backend 省略で利用可能な NVIDIA と AMD の両方がある場合は質問を表示し、`--yes` または `--check` の場合は既定の NVIDIA 選択になります（`setup.py:8710-8729`）。

`sycl` は通常の CUDA/HIP の setup に入る前に `sycl/setup_intel.py` へ引数を転送します。転送時には `--backend` とその値（または `--backend=sycl`）を取り除き、それ以外の引数を残します。Windows では未対応として失敗し、スクリプトが checkout に存在しない場合も失敗します（`setup.py:8561-8564,7321-7344`）。

## 適用条件と副作用

- `--backend hip` は AMD GPU の選択を固定します。対応 GPU がない場合に NVIDIA へ fallback せず失敗します。逆に `--backend cuda` で NVIDIA が見つからない場合も AMD へ fallback しません（`setup.py:8731-8750,8787-8791`）。
- AMD の engine は Linux ではローカルで CMake build され、Windows では ready-made HIP engine を使う経路です。明示的な `--build` がなくても AMD/Linux の初回 engine 準備でビルドに進むコードがあります（`setup.py:4510-4553`、`setup.py:4320-4355`）。
- `--backend sycl` は実験的な Intel Arc 経路で、専用スクリプトを起動します。コードの説明では Linux で oneAPI を使ってソースから構築するとされています（`setup.py:7321-7332`）。
- `--update` と併用した場合、`sycl` は先に SYCL 専用 setup へ分岐します。一方 `cuda` / `hip` は `update_install(have, a)` に入った後、`a.backend` の参照がなく、更新処理に backend を選ばせる効果は確認できません（`setup.py:8563-8564,8617-8619`、`setup.py:6682`）。
- macOS の `CONTROL` 経路では、backend の `sycl` 分岐より先に `mac_control_setup(a)` へ戻ります。同関数内に `a.backend` の参照はなく、Metal engine component を使うモデル準備経路なので、この条件下では `--backend` は GPU backend の選択に使われません（`setup.py:8561-8564,8236-8241`）。

選択により GPU 検出、既製 engine の取得、engine のビルド、モデル/設定ファイルの準備へ進む場合があります。setup 全体の実行にはダウンロードやローカルファイル作成等も伴い得ますが、このオプション単独の影響範囲として特定できるのは backend 分岐です（`setup.py:8697-8776,9263-9275`）。

## 出力とエラー

利用可能な NVIDIA と AMD の両方があり backend を省略したときは GPU vendor 選択を表示します。明示した backend に対応する GPU がないと `fail()` が案内文を表示して終了コード 1 で止めます。`fail()` は `[X]` メッセージと「Setup stopped」案内を出力します（`setup.py:825-830,8710-8729,8749-8750,8787-8791`）。

`--backend sycl` は `subprocess.call()` の終了コードを返します。Windows 非対応、専用 setup ファイル欠落は `fail()` による終了コード 1 です（`setup.py:7328-7344`）。不正な選択肢や値の欠落では `argparse` が usage と parser error を出します（`setup.py:8548-8553`）。

## 根拠

- parser 定義・choices・既定値: `setup.py:8548-8553`
- 早期分岐、update 経路、backend 自動選択と GPU 条件: `setup.py:8561-8564,8617-8619,8697-8791`
- AMD engine の構築と実行設定: `setup.py:4510-4564,9263-9275,9597-9614`
- AMD model/vision の条件: `setup.py:8996-9003,9112-9115`
- Intel Arc の委譲と失敗条件: `setup.py:7321-7344`
- wrapper の引数委譲: `setup.sh:6-13,76`、`START-HERE.bat:48-54`、`SETUP.bat:1-3`

この調査では checkout 内のソースと文書索引を確認しました。同一 revision の `--help` は実行しておらず、Release 配布物も照合していません。
