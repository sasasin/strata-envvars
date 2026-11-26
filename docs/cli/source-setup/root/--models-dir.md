# `--models-dir`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（root。`setup.sh`、`START-HERE.bat` 等からも渡される） |
| オプション | `--models-dir` |
| 別名 | なし |
| 値 | 1 個のディレクトリパス文字列。parser に型・選択肢・パス形式の制約はない |

## 役割

モデルの GGUF ファイルを置くルートディレクトリを指定する。既定はデータフォルダ内の `models` で、通常の GGUF モデルではさらにモデル識別用ディレクトリを下に使う。NVFP4 の ready-made pack ではリポジトリ別ディレクトリを下に使う。既存のモデルファイルを移動する指定ではなく、配置先を変える指定である。

## 使い方

```sh
# モデルの GGUF を大容量ドライブ配下に置き、モデルを導入して終了する
python terminal/setup.py --family qwen --model IQ3_S --models-dir /mnt/large/strata-models --no-start
```

## 値と既定値

`--models-dir` は値を取る引数で、既定値は parser には設定されていない。通常の setup 経路では省略時に `data / "models"` が設定される。値そのものに対する存在確認、ディレクトリ形式の検証、ホームディレクトリ展開は parser と利用箇所には見当たらない。値は `Path(...)` に渡され、ディレクトリが必要になった時点で `mkdir(parents=True, exist_ok=True)` を呼ぶ経路がある。無効なパスや作成権限がない場合の個別エラー処理は確認できない。

## 実行時の動作

- 通常の GGUF モデルでは、配置先を `Path(a.models_dir) / tag` として shard のパスを組み立てる。モデルファイルが未完了ならダウンロードし、準備工程では同じモデル配置先を参照する。
- NVFP4 ready-made pack では `--models-dir` が pack ファイルの配置ルートとなり、その下に `<owner>--<repo>` と pack 内の相対パスを作る。
- `--gguf-dir` が同時に指定された通常 GGUF モデルでは、`--gguf-dir` が既存 GGUF の読み込み元として使われ、`--models-dir` 配下のモデル別ディレクトリは shard の参照先にならない。ready-made pack に `--gguf-dir` を指定した場合は警告を出して `--gguf-dir` を無効化する。
- 指定先に必要な通常モデルの shard が揃っていない場合、Strata が把握している別のデータルートも検索し、そこに全 shard があればそちらを使用する。ready-made pack でも別ルートに検証済みファイルがあればそちらを選ぶ。
- 起動専用の既存インストール経路では、モデルの実パスは保存済み run config から読み込まれる。`--models-dir` はその経路の判定条件に含まれず、指定値を使った移動・再配置は行わない。

## 適用条件と副作用

このオプションは setup 時のモデルファイル配置に作用する。通常経路ではディスク空き容量を配置先で確認し、不足すれば setup を失敗させる。必要になった配置先ディレクトリは作成され、モデルのダウンロードや変換・準備ファイルの書き込みが行われる場合がある。低 RAM 用の expert コピー先はデータフォルダの `packs` であり、`--models-dir` とは別に空き容量を確認する。

Mac では `terminal/setup.py` が引数を `engine/metal/setup_mac.py` に転送する。Mac 側も `--models-dir` を受理し、省略時にデータフォルダの `models` を使う。通常モデルはその下にモデル別ディレクトリを作る。

## 出力とエラー

空き容量が不足した場合、通常の setup は不足している配置先と必要量・空き容量を含むエラーを出し、別の `--models-dir` を選ぶよう案内する。ダウンロード中の書き込み失敗では partial ファイルの再開情報を保存し、空き容量を確保するか別の `--models-dir` を選んで再実行するよう案内する。ディレクトリ作成やアクセス拒否など、これ以外の OS エラーの表示・終了経路はこの調査では特定できなかった。

## 根拠

- `terminal/setup.py:11434-11437` — macOS の通常 root setup を `engine/metal/setup_mac.py` に委譲する条件と引数転送。
- `terminal/setup.py:11510-11518` — root parser の `--models-dir` 宣言と説明（GGUF の保存先、既定は data folder の `models`）。
- `terminal/setup.py:11680-11691` — setup 経路での `data / "models"` 既定値の設定。
- `terminal/setup.py:12295-12312` — ready-made pack と通常 GGUF での配置先・shard パス構築、および別ルート検索。
- `terminal/setup.py:2741-2757` — 空き容量確認時の配置先ディレクトリ作成と不足時の失敗情報。
- `terminal/setup.py:3307-3310` — ダウンロード書き込みエラー時の再開情報保存と案内。
- `terminal/setup.py:3886-3890` — ready-made pack のルート下に配置パスを構築する処理。
- `engine/metal/setup_mac.py:386-390`, `414-415`, `497-501` — Mac parser、既定の models root、通常モデルの配置先。
- `docs/cli/README.md:1661-1698` — `source-setup` の root scope と `--models-dir` の索引項目。
