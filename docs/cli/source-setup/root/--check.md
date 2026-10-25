# `--check`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` / update wrappers |
| オプション | `--check` |
| 別名 | なし |
| 値 | 値を取らない boolean flag。省略時 `False` |

## 役割

PC のハードウェア・メモリ条件を調べ、Strata のモデルが動作可能かを表示して終了します。通常の Linux/Windows 経路では、RAM、GPU の適合性、CPU 命令セットなどを確認し、各モデルのおおよその適合状況を列挙します（`setup.py:8515`, `setup.py:8697-8709`, `setup.py:8816-8859`, `setup.py:8860-8909`）。

## 使い方

リポジトリのルートで実行します。

```sh
python3 setup.py --check
```

Linux の `./setup.sh --check`、Windows の `START-HERE.bat --check` でも引数は `setup.py` に渡されます（`setup.sh:6-13, 76`, `START-HERE.bat:48, 53`）。ただし wrapper は Python 環境がない場合に venv や Python の準備を先に行うため、確認だけの用途ではその副作用も考慮してください（`setup.sh:14-75`, `START-HERE.bat:14-39`）。`update.sh` / `UPDATE.bat` は `--update` を付けて setup に渡し、`--update` の分岐は `--check` の判定より先に処理されるため、更新用 wrapper に `--check` を渡しても check-only 実行にはなりません（`update.sh:62`, `UPDATE.bat:79`, `setup.py:8617-8619, 8860`）。

## 値と既定値

値は不要です。`argparse` の `store_true` で定義され、指定すると `a.check` が `True`、省略すると `False` です。同じ flag を複数回指定しても効果は変わりません（`setup.py:8515`）。値を付けた形式は parser のエラーになります。

## 実行時の動作

- 既存モデルがあっても通常起動へ進まず、PC 検査の経路を選びます（`setup.py:8602-8620`, `setup.py:8677-8692`）。
- 通常の CUDA/HIP 経路では GPU・RAM・CPU などを調べ、モデルごとに `fits` / `tight` / `does not fit` や低 RAM モード、既定の Unsloth RAM 予算に基づく説明を表示します。DeepSeek-V4.1-Flash の一部サイズも別の計画結果として表示します（`setup.py:8697-8709`, `setup.py:8816-8859`, `setup.py:8860-8901`）。この一覧はセットアップ時の推定で、実際のモデル起動を保証するものではありません。
- `--check` 中は、低 RAM を理由とする通常の確認停止を抑止し、判定一覧まで進みます（`setup.py:8819-8834`）。ただし GPU が見つからない、NVIDIA ドライバーが古い、CPU が SSE4.2 未満など、検査続行に必要な条件を満たさない場合は失敗します（`setup.py:8787-8812`, `setup.py:8845-8858`）。
- NVIDIA と AMD の両方が使える場合の選択質問は、`--check` または `--yes` があると回答待ちをせず NVIDIA を選びます。AMD を検査したい場合は `--backend hip` を指定します（`setup.py:8710-8729`）。`--gpu` / `--gpus`、backend、`--low-ram` など他の指定は検査対象や表示に影響し得ます。`--resident-budget-gib` は check 一覧の計算へ渡されず、表示には既定の予算が使われます（`setup.py:8868-8877, 8973`; `resident_budget_gib` の定義は `setup.py:3095`）。
- `--check` と `--calibrate` を同時に指定すると、チューニングは実施せず警告を出します（`setup.py:8652-8656`）。
- Apple Silicon の通常の Metal 経路では `setup.py` から `metal/setup_mac.py` に引数を転送し、そちらの parser が `--check` を定義します。Mac では unified memory と macOS 要件を表示し、問題があれば終了コード 1、なければ 0 です（`setup.py:7314-7318`, `setup.py:8418-8419`, `metal/setup_mac.py:350-356, 373-385`）。Control mode の Mac 経路は `mac_control_setup` 側で同様に問題の有無を判定します（`setup.py:8561-8562`, `setup.py:8236-8259`）。
- Intel SYCL backend を指定すると `setup.py` は引数を `sycl_setup` に渡して Intel 用 setup 経路へ委譲します。`--check` の個別動作はその経路の別実装に依存し、この文書では確認していません（`setup.py:8563-8564`, `setup.py:7321-7335`）。

## 適用条件と副作用

通常の check 分岐に到達した後はモデルのインストール、取得、engine build、起動へ進みません。ただし通常の `setup.py` 経路では、その分岐より前に `data_folder_for(a)` が呼ばれます。これはデータディレクトリを作成し、同じドライブ上の既存モデルファイルを集約・移動し、設定ファイルを付け替えたり `settings.json` を保存したりすることがあります（`setup.py:8602-8612`, `setup.py:6136-6139`, `setup.py:6042-6066, 6100-6133`）。したがって `--check` は常に読み取り専用ではありません。Mac の `setup_mac.py` と Control mode の Mac 経路でも `data_folder_for(a)` は check 判定前に呼ばれます（`metal/setup_mac.py:356-367, 373-383`, `setup.py:8251-8257`）。

Windows では `main()` の冒頭で `adopt_user_defaults()` も呼ばれます。これは管理者実行時に、プロセスが今後作るファイルの owner と default DACL を現在ユーザー向けに設定する処理です。`--check` のハードウェア判定とは別ですが、プロセス内の token 設定に触れます（`setup.py:8412-8419`, `strata_control/private_files.py:349-385`）。

## 出力とエラー

結果や警告は `say()` / `warn()` を通じて標準出力に表示されます（`setup.py:808-823`）。通常経路では、少なくとも一つの対象モデルが適合すると「This PC can run Strata...」を表示して終了コード `0`、適合するモデルがない場合はその旨を表示して終了コード `1` です（`setup.py:8902-8909`）。Mac の各経路も問題なしなら `0`、問題ありなら `1` を返します（`metal/setup_mac.py:377-385`, `setup.py:8248-8259`）。GPU 不在、利用できない GPU/driver、対応 ISA 不足など `fail()` に到達した場合は説明を標準出力へ出し、`sys.exit(1)` します（`setup.py:825-830`, `setup.py:8787-8812`, `setup.py:8845-8858`）。引数の型・未知 option など parser エラーは `argparse` が処理します（`setup.py:8420`, `setup.py:8553`）。

## 根拠

- option 定義と parser: `setup.py:8420-8425, 8513-8517, 8553`
- 通常経路の mode 判定と PC 検査: `setup.py:8602-8620, 8697-8709, 8816-8859`
- モデル適合一覧、DeepSeek の追加情報、終了コード: `setup.py:8860-8909`
- check 前に行われるデータディレクトリ処理: `setup.py:6042-6066, 6100-6139, 8602-8612`
- Mac/SYCL の委譲と別経路: `setup.py:7314-7335, 8236-8259, 8412-8419, 8561-8564`; `metal/setup_mac.py:350-385`
- wrapper の引数委譲・bootstrap: `setup.sh:6-13, 14-75`; `START-HERE.bat:14-53`; `update.sh:62`; `UPDATE.bat:79`
