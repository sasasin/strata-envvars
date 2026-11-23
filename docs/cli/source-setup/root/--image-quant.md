# `--image-quant`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（source setup、root） |
| オプション | `--image-quant` |
| 別名 | なし |
| 値 | `Q4_K_M`、`Q6_K`、`Q8_0` のいずれか |

## 役割

画像生成モデル Qwen-Image-2.1-Turbo の denoiser quant を明示するための引数として parser に登録されています。ただし、現行 checkout では `setup_images()` の呼び出しがなく、`terminal/setup.py` 本体の通常の実行経路から `a.image_quant` が画像設定へ渡される箇所も確認できません。このため、source setup にこの引数を渡しても quant の選択・ダウンロード・設定への反映は起きないと判断できます。画像設定 helper 内には quant を使う実装がありますが、現行ソース上で同 helper を呼ぶ経路は別の画像 install ツールです。

## 使い方

```sh
./setup.sh --image-quant Q6_K
```

上記は parser が受理する形式の例です。現行 `setup.py` では当該値は画像設定処理に利用されないため、quant を変更する操作としては機能しません。

## 値と既定値

- 値は `Q4_K_M`、`Q6_K`、`Q8_0` に限定されます。別の値は `argparse` の choices 検証で拒否されます。parser は既定値を指定していないため、未指定時の属性値は `None` です（`terminal/setup.py:11255-11256`）。
- 画像設定 helper の実装では、明示値がなければ GPU メモリ量から quant を選びます。backend が CPU の場合は `Q4_K_M`、それ以外は GPU メモリが 8 GB 以下で `Q4_K_M`、12 GB 以下で `Q6_K`、それを超えると `Q8_0` です（`terminal/setup.py:5888-5891`、`terminal/tools/image/qimage.py:65-71`）。これは helper の規則であり、現行 `setup.py` CLI で実行される規則ではありません。
- 重複指定時の明示的な独自処理はありません。`argparse` の通常の単一値引数として扱われます。

## 実行時の動作

`setup.py` の parser はこの引数を `help=argparse.SUPPRESS` で登録しているため、通常の `--help` 一覧には表示しません（`terminal/setup.py:11252-11256`）。しかし、parser への登録だけでは値は反映されません。現行 `terminal/setup.py` 内で `setup_images()` は定義されていますが、その呼び出しは見つからず、`a.image_quant` の参照は `image_backend_choice()` 内の quant 選択箇所だけです（`terminal/setup.py:5891-5895, 5898-5904`）。従って source setup でこのオプションを指定しても、現状は選択値が使われません。

同じ共通 helper は `terminal/tools/image/install.py` からも利用されますが、そちらは別 CLI であり、受け付ける引数名は `--quant` です。同ツールは `a.quant` を `image_quant` として helper に渡します（`terminal/tools/image/install.py:44-49, 69-71`）。この別 CLI の値規則を source setup の `--image-quant` の実行効果と混同しないでください。

helper が呼ばれる経路では、指定 quant が GPU メモリ量に対する推奨より大きい場合に警告を出し、指定値を維持します。コメントと警告文は、stable-diffusion.cpp が一部を RAM に置くため遅くなる可能性を述べています（`terminal/setup.py:5884-5895`）。画像設定処理まで進む場合は quant をモデルファイルの選択に使い、モデルのダウンロードと SHA-256 検証を行い、生成された `images` 設定に quant と denoiser のパスを記録します（`terminal/setup.py:5907-5927`、`terminal/tools/image/qimage.py:235-242`）。これらも source setup からは現在到達しない helper の処理です。

## 適用条件と副作用

現行 `setup.py` の parser は値を受理しますが、画像 setup への接続が確認できないため、このオプション自体による画像モデルのダウンロード、ビルド、設定ファイル変更、GPU 利用は確認できません。無効値は parser の choices 検証で拒否されます。標準 `argparse` のエラー表示・終了コードの細部は本調査では実行していません。

将来または別経路で `image_backend_choice()` が利用された場合、helper は推奨 quant を超える指定値を強制的に下げず、警告のみ出します。CPU backend の推奨は `Q4_K_M` です（`terminal/setup.py:5888-5895`）。

## 根拠

- `terminal/setup.py:11252-11256` — source setup parser における非表示の引数登録と choices。
- `terminal/setup.py:5884-5895` — quant の既定選択、明示値の採用、および推奨より大きい場合の警告。
- `terminal/setup.py:5898-5927` — `setup_images()` 内の条件、ダウンロード、設定生成。現行 checkout で呼び出し元は確認できず、`a.image_quant` は `image_backend_choice()` 内でのみ参照される。
- `terminal/tools/image/qimage.py:56, 65-71, 235-242` — quant の一覧、GPU メモリによる推奨、および設定オブジェクトへの値の記録。
- `terminal/tools/image/install.py:44-49, 69-71` — 別 CLI が `--quant` を受け付け、共通 helper へ渡す経路。
