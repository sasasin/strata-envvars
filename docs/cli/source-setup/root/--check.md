# `--check`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（source setup、トップレベル） |
| オプション | `--check` |
| 別名 | なし |
| 値 | 取らないフラグ。省略時は `False`、指定すると `True`。 |

## 役割

通常の CUDA/HIP セットアップ経路では、この PC の CPU、RAM、GPU と各モデルのメモリ目安を表示して、セットアップやモデル起動へ進まず終了する。これは現在の PC で全モデルが実行可能かを測定するベンチマークではなく、Strata の適合判定ルールに基づく目安である。Intel SYCL と Apple Silicon は別経路へ委譲され、それぞれの判定内容・副作用が異なる。

## 使い方

Strata checkout のルートから実行する例:

```sh
python3 terminal/setup.py --check
```

トップレベルの `setup.sh` や Windows の `START-HERE.bat` も引数を `setup.py` に渡す入口である（`setup.sh:6-17`、`START-HERE.bat:49-65`）。

## 値と既定値

値は不要で、parser は `action="store_true"` として登録する。指定なしでは通常モードの選択に従い、`--check` を指定したときだけ検査モードになる。同じフラグを複数回指定しても真偽値が増えることはない。数値範囲など `--check` 固有の値 validation はない（`terminal/setup.py:11552`）。

## 実行時の動作

通常の CUDA/HIP 経路では、既存モデルの通常起動を抑止し、GPU 選択・ハードウェア情報の取得後に各モデルの必要ファイル量と RAM + GPU メモリを比べて結果を表示する。モデル一覧は `MODELS` を走査し、結果に `EXPERIMENTAL` や AMD 側の NVIDIA 専用注記を付ける場合がある（`terminal/setup.py:11681-11688`、`terminal/setup.py:11761-11766`、`terminal/setup.py:11877-11912`、`terminal/setup.py:11960-11971`）。

適合ラベルはモデルファイル量（PLE 等の lookup table を除く）と RAM・カードメモリを比較し、収まれば `fits`、収まらなければ `may run slower` とする。ここではカードの VRAM reserve は差し引かれない。最終的に「`fits` かつ通常モデル（`mem_total` でない）が1つ以上あるか」を確認し、1つもなければ終了コード `1`、あれば `0` を返す（`terminal/setup.py:7042-7054`、`terminal/strata_control/fit_label.py:40-58`、`terminal/setup.py:11960-11979`）。

ただし `--check` は全経路で純粋な読み取り専用とは限らない。main は検査より先に旧ディレクトリ配置の移行を試み、条件が合えばファイルを移動して設定内パスを書き換える（`terminal/setup.py:11607-11610`、`terminal/setup.py:8436-8493`）。また通常経路はモデルデータの置き場所を解決する際、既定データフォルダーを作成し、既存データの移動・設定保存を行う場合がある（`terminal/setup.py:11681-11690`、`terminal/setup.py:7428-7444`、`terminal/setup.py:7475-7510`）。

## 適用条件と副作用

- `--update` を同時に指定すると、main は検査分岐より前に update 処理へ進むため、`--check` のモデル適合一覧は出ない（`terminal/setup.py:11692-11698`）。`--prepare-pack` と `--inspect` も `--check` の判定より前に処理される（`terminal/setup.py:11622-11627`）。
- `--calibrate` と併用した場合、通常経路では「`--check` と同時なので calibration は何もしない」という警告を出す（`terminal/setup.py:11730-11733`）。
- `--backend sycl` は Linux の Intel Arc 経路へ委譲され、Windows では未対応として停止する。SYCL 側は `--check` の判定前に `engine-sycl` の reader ディレクトリを作成し、`BUILD.json` を書く。表示も Intel 向けに置き換わる（`terminal/setup.py:11635-11638`、`terminal/setup.py:9297-9320`、`engine/sycl/setup_intel.py:461-492`）。
- Apple Silicon では `setup.py` が `metal/setup_mac.py` へ引数を渡す。macOS 側の `--check` は Mac 情報・問題・空きディスクを表示し、検出した問題があれば `1`、なければ `0` を返す。この分岐では通常経路のモデル別適合一覧を作らない（`terminal/setup.py:11434-11437`、`terminal/setup.py:9290-9294`、`engine/metal/setup_mac.py:372-430`）。Mac 側も先にデータフォルダーを解決するため、通常経路と同様にフォルダー作成や既存データの整理が起こり得る（`engine/metal/setup_mac.py:411-414`、`terminal/setup.py:7428-7510`）。
- 通常経路で NVIDIA GPU が見つからない、利用可能な AMD GPU がない、CPU が必要命令セットを満たさない、ドライバーが古い等の場合は `fail()` 経由で停止し、終了コード `1` となる（例: `terminal/setup.py:1049-1056`、`terminal/setup.py:11838-11839`、`terminal/setup.py:11877-11901`、`terminal/setup.py:11939-11942`）。CLI parser の引数エラーは `argparse` が usage とエラーを出して終了する。

## 出力とエラー

通常経路は `say()` で標準出力に PC 情報、警告、モデルごとの `needs ~N GB of RAM + VRAM` と判定を出す。合格時は「この PC で Strata を実行できる。インストールするには `--check` なしで再実行」と案内し、終了コード `0`。適合モデルがない場合は不足 RAM と `--model NAME --yes` での続行可能性を案内し、終了コード `1`（`terminal/setup.py:997-999`、`terminal/setup.py:11960-11979`）。Mac 経路の出力・終了コードは上記の別実装に従う。

## 根拠

- `terminal/setup.py:11552` — `--check` の parser 定義。
- `terminal/setup.py:11607-11610`、`terminal/setup.py:11622-11638`、`terminal/setup.py:11681-11698` — 初期処理、他モードとの優先関係、通常起動の抑止とデータ場所解決。
- `terminal/setup.py:11730-11733`、`terminal/setup.py:11877-11979` — calibration 相互作用、PC 情報確認、モデル判定と終了コード。
- `terminal/setup.py:7042-7054`、`terminal/strata_control/fit_label.py:40-58` — モデルファイル量と適合ラベルの計算。
- `terminal/setup.py:8436-8493`、`terminal/setup.py:7428-7444`、`terminal/setup.py:7475-7510` — check 前に起こり得る配置移行、データフォルダー作成・移動・設定保存。
- `terminal/setup.py:9290-9320`、`engine/metal/setup_mac.py:372-430`、`engine/sycl/setup_intel.py:461-492` — macOS / Intel SYCL の委譲先、分岐固有の判定と副作用。
- `setup.sh:6-17`、`START-HERE.bat:49-65` — ラッパーから `setup.py` への引数転送。

調査範囲は上記 commit の Strata 所有ソース。CLI の実行や build は行っていない。特に、データフォルダーの移動は既存設定・配置に依存するため、この文書では実行される条件をソース上で確認できた範囲に限定して記載した。
