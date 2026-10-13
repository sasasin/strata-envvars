# `LOW_RAM`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

Docker イメージの entrypoint が初回セットアップ時に `LOW_RAM` を `setup.py --low-ram` へ渡し、モデルの expert を通常どおり RAM に全量コピーするか、pack の `experts.bin` から読み込む低 RAM モードにするかを選びます。`LOW_RAM` 自体を読む箇所は `docker-entrypoint.sh` のみです。エンジンはこの環境変数を直接読みません。セットアップが生成する config の `args` に `--resident-experts` または `--mmap-experts` が記録され、その設定で後続起動します（`docker-entrypoint.sh:31,76-86,96-106`; `setup.py:5619-5632,5733-5735`）。

## 値と判定

entrypoint は `${LOW_RAM:-auto}` を使います。シェルの規則により、未設定または空文字は `auto` に置き換わります。それ以外は文字列を加工せず `--low-ram` に渡します。大文字小文字の変換や空白除去はありません。`setup.py` の argparse は次の5値だけを受け付け、ほかの値では setup が引数エラーになります（`docker-entrypoint.sh:31,76-78`; `setup.py:4905-4909`）。

| 値 | セットアップの判定 |
|---|---|
| `auto` | `MODELS[model]["budget"]` があるモデルでは無効。それ以外はモデルの expert arena と約10 GBの余裕の合計が検出 RAM を超えると低 RAM モード。 |
| `on` | budget モデル以外で低 RAM モードを強制。 |
| `off` | 低 RAM モードを無効化。RAM 不足時は通常モードのまま続けるか確認・警告する経路がある。 |
| `resident` | budget モデル以外で低 RAM モードを強制し、GPU が保持しない expert を RAM にコピーする variant を要求。複数 GPU で layer split 非対応のエンジンでは mmap 側に切り替わる。 |
| `mmap` | budget モデル以外で低 RAM モードを強制し、GPU が保持しない expert を pack のファイルから mmap 経由で読む variant を要求。 |

低 RAM の自動条件は `ram < MODELS[model]["arena_gb"] + 10` です。10 GB は OS や engine などのための余裕として定義されています。判定関数は `choice` とモデル情報を使い、RAM の数値はセットアップ中の `ram_gb()` から取得します（`setup.py:426,3461-3476,3507-3516,5147`）。

## 有効になる条件

- `docker-entrypoint.sh` がセットアップを実行するときだけ値が反映されます。該当するのは選択モデルの `/data/config/strata-<tag>.json` がまだない場合、または `REINSTALL=1` の場合です。既存 config を使う通常起動では `LOW_RAM` は `setup.py` に渡されず、環境変数を変えても保存済み設定は変わりません（`docker-entrypoint.sh:41-53,57-86,89-106`）。
- `auto` はモデルごとに決まります。`MODELS[model]` に `budget` があるモデルでは `low_ram_wanted()` が常に false を返します。`on`、`resident`、`mmap` もこのモデルではモードを有効にせず、`auto` と `off` 以外なら「このモデルには適用されない」という warning が出ます（`setup.py:3507-3516,5283-5293`）。
- `on` などで低 RAM モードになっても、expert cache と VRAM、GPU 数、context、KV 方式などで resident/mmap variant と実行可能性が変わります。低 RAM モードでは setup がモデルの `experts.bin` を作成し、config に `--resident-experts` または `--mmap-experts` を加えます。既存の `experts.bin` がある場合は再作成を省きます（`setup.py:5385-5417,5584-5588,5627-5632`）。
- Docker entrypoint は setup を `--yes` で実行します。Dockerfile と INSTALL 文書はメモリ上限のあるコンテナでは `LOW_RAM=on` を指定するよう案内しています。setup が見る RAM はコンテナの制限ではなくホスト RAM になり得るため、`auto` の判定だけではコンテナ上限を検出できない、という理由が entrypoint に記載されています（`docker-entrypoint.sh:76-86`; `Dockerfile:30-34`; `docs/INSTALL.md:122-125`）。

## 実行時の詳細

低 RAM モードでは pack の `experts.bin` がなければ、setup が元 GGUF から作成します。続けて config の engine 引数に variant を記録します。resident variant は GPU に載らない expert を一度 RAM にコピーし、mmap variant はその部分をファイルから読みます。旧 engine で自動選択された resident variant を使えない場合、setup は mmap に fallback し、その理由を表示します。一方 `resident` を明示した場合、この旧 engine 向け fallback 条件は適用されず、setup は `--resident-experts` を config に記録します。setup のコードからは、その engine が引数を受理するかまでは確認できません（`setup.py:5584-5587,5627-5632`）。

複数 GPU では setup の engine version が `RESIDENT_SPLIT_ENGINE` 以上かどうかも影響します。entrypoint から `GPUS` を指定した場合、setup は複数 GPU のまま低 RAM モードを選べますが、GPU が保持しない expert は OS file cache から読む経路になります。INSTALL 文書も、低 RAM モードは通常1 GPUで、`GPUS` を複数指定すると残りの expert を file cache から読むと説明しています（`setup.py:3462-3470,3555-3587,5391-5405`; `docs/INSTALL.md:122-125`）。

実際の状態はセットアップ時に `low-RAM mode` のログとして説明され、GPU が保持する expert の割合や resident/mmap の選択が表示されます。低 RAM モードにするため pack 用のディスク容量も追加で必要です（`setup.py:5462-5474,5399-5417`）。

## 根拠

- `docker-entrypoint.sh:31,50-53,76-86,89-106` — 既定値、セットアップ時の引き渡し、config がある場合の通常起動経路。
- `setup.py:4905-4909,3507-3516` — CLI が受け付ける値と低 RAM モードの選択条件。
- `setup.py:3461-3476,5147` — 自動判定の RAM 条件と RAM 値の取得。
- `setup.py:5283-5300,5385-5417,5584-5588,5627-5632` — budget モデルの例外、GPU/RAM 条件、pack 準備と実行引数。
- `Dockerfile:25-40`, `docs/INSTALL.md:118-125` — Docker 環境での設定案内。
