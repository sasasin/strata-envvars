# `setup.py` の `--cuda`

- 対象: `source-setup`（`setup.py`。`setup.sh`、`START-HERE.bat` などの委譲 wrapper も同じ引数を渡す）
- 調査対象 Strata revision: `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`
- 調査日: 2026-10-25

## 概要

NVIDIA GPU を使うモデルの engine に CUDA 12 または CUDA 13 のどちらを選ぶか指定する。値は `12`、`13`、`auto`。コマンドラインで省略した場合は環境変数 `STRATA_CUDA` の値が既定値となり、その環境変数も未設定または空なら自動選択になる。parser は環境変数由来の値にも同じ choices 検査を適用する（`setup.py:8509-8512`）。

| 値 | 動作 |
| --- | --- |
| `auto` または省略 | CUDA 13 を選ぶ。ただし選択された GPU に CUDA 13 非対応の Pascal / Volta（compute capability が `sm_75` 未満）が含まれる場合は CUDA 12 の experimental engine を選ぶ。 |
| `12` | GPU 世代にかかわらず CUDA 12 の experimental engine を選ぶ。 |
| `13` | GPU 世代にかかわらず CUDA 13 を選ぶ。CUDA 13 非対応 GPU が含まれても拒否はせず、そのカードでは engine が動かない旨を警告する。 |

選択は1つのモデルの engine に対して行われ、複数 GPU でモデルを動かす場合は選択 GPU のうち最も古い世代が自動選択を決める（`setup.py:238-248, 1583-1598, 8800-8806`）。CUDA 13 の compile 対象最小値は `sm_75`。Pascal / Volta は CUDA 13 で compile できないため CUDA 12 経路に分けられている（`setup.py:238-248`）。

## 適用条件と相互作用

- この指定が engine 選択に反映されるのは、セットアップ処理が NVIDIA GPU を選び、`cuda_choice()` を呼ぶ経路。明示的な `--backend hip` など AMD の経路では NVIDIA の CUDA engine 選択は行わない（`setup.py:8703-8709, 8787-8812`）。
- 新規セットアップでは `--cuda 12` は Pascal / Volta の利用許可にもなり、該当 GPU を選択可能にする（`setup.py:1542-1570, 8702-8707`）。一方、`--cuda 13` は自動選択を CUDA 13 に上書きするだけで、非対応 GPU の組み合わせを拒否しない（`setup.py:1583-1598`）。
- 選択された toolkit に合う ready-made engine があれば利用し、なければソースから compile する。`--build` は ready-made engine の利用を止めて compile 経路にする（`setup.py:7383-7415`）。CUDA 12 compile には CUDA 12.x toolkit と C++ build tools が必要で、GPU が `sm_120` なら少なくとも CUDA 12.8 が必要。これらが不足するとセットアップは自動導入を提案または実行し得る（Windows は `winget`、対応する Ubuntu/Debian は `sudo apt-get` 等）（`setup.py:5376-5461`）。
- CUDA 12 選択時は Windows 528 以上、Linux 525 以上の NVIDIA driver を要求する。CUDA 13 経路では 580 以上を要求し、不足時は更新案内を出して停止する（`setup.py:237-247, 8804-8812`）。
- `--check` でも GPU と CUDA 選択、driver 条件を確認するが、その後の engine compile/install には進まない（`setup.py:8804-8812, 8860-8909`）。
- `--rollback-engine` は `--cuda 12` なら CUDA 12 engine、それ以外なら CUDA 13 engine を対象にする（`setup.py:8614-8615`）。`--update` の経路は `update_install()` に入り、toolkit を `--cuda` から渡さず既存 engine を更新するため、このオプションによる engine 選択変更は行わない（`setup.py:8617-8619, 6682-6709`）。
- インストール済みモデルの通常起動は既存の設定と engine を使い、新しい CUDA 選択を計算し直さない。既存設定を使って別コピーを自動セットアップする場合、設定が CUDA 12 で、`--cuda` が未指定なら CUDA 12 を引き継ぐ（`setup.py:8603-8608, 8638-8640, 8677-8692`）。
- macOS では `setup.py` は独自 parser より先に Metal 用 `setup_mac.py` に処理を渡す。同 parser は未知引数をエラー終了ではなく「not used on a Mac」と警告するため、`--cuda` は macOS の engine 選択には使われない（`setup.py:8412-8420`, `metal/setup_mac.py:327-358`）。

## 効果と副作用

CUDA 12 / 13 の選択は ready-made engine の候補ディレクトリ、compile 時の toolkit と GPU architecture、依存する CUDA runtime library、モデル設定に記録する engine の選択を変える。CUDA 12 engine は `engine-cuda12/` に置かれ、設定には `cuda: 12` が保存される（`setup.py:1601-1608, 5577-5614, 7383-7415, 9597-9602`）。セットアップは通常どおりモデル設定を書き、CUDA 12 の compile が必要なら build tools の導入、ダウンロード、ビルドなどを行う。オプション単独でこれらの処理を実行するわけではなく、セットアップの実行経路に入った場合に発生する。

## 出力と失敗

- 選択理由は通常出力または警告として表示される。`--cuda 13` と古い GPU の組み合わせでは、CUDA 13 にその GPU 向けコードがなく engine が動作しない旨を警告する（`setup.py:821-829, 1583-1598, 8804-8806`）。
- `12`、`13`、`auto` 以外の値（`STRATA_CUDA` 由来を含む）は `argparse` の choices 検査で拒否される。標準 `argparse` の usage/error 表示と終了コード 2 の経路となる（parser: `setup.py:8509-8512, 8553`）。
- 必要な toolkit / compiler が見つからない、導入を拒否した、対応しない Linux package manager / distribution である、または driver が最低版未満の場合、`fail()` は理由と可能なら対処案を表示して終了コード 1 で停止する（`setup.py:825-830, 5376-5459, 8807-8812`）。
- CUDA 12 toolkit の自動導入は外部 package manager を使い得るため、システムにパッケージを追加する副作用がある。Windows では `winget`、Linux の対応 Ubuntu/Debian では CUDA repository の keyring 導入、apt update、toolkit install が行われる（`setup.py:5413-5453`）。

## 例

```sh
./setup.sh --setup --cuda auto
./setup.sh --setup --cuda 12
```

```bat
START-HERE.bat --setup --cuda 13
```

既存モデルの設定と通常起動には影響しない。CUDA 12 engine の対象条件と制約は Strata の `docs/OLDER_GPUS.md` を参照。

## 根拠と関連文書

- 索引上の scope と予定リンク: [`docs/cli/README.md`](../../README.md) の `source-setup` 節。対象は setup wrappers が委譲する `setup.py` の共通オプション。
- 配置・調査基準: [`docs/cli/001_investigation.md`](../../001_investigation.md)。
- parser、選択処理、GPU 世代・driver 条件、engine build / install、設定記録: Strata `setup.py` の上記行。
- macOS の委譲と別 parser: Strata `setup.py:8412-8420`、`metal/setup_mac.py:327-358`。

調査時にソース変更、build、GPU 実行、性能測定、テストは行っていない。`setup.py --help` は `main()` の parser 実行前に user-owned file adoption 処理があるため実行せず、parser 定義を根拠にした。
