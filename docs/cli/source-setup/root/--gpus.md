# `--gpus`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat` などから起動する root |
| オプション | `--gpus` |
| 別名 | なし |
| 値 | 2 枚以上の GPU 番号をカンマ区切りで指定するか、`all`。例: `0,2` |

## 役割

モデルを複数 GPU にまたがって使うカードを指定します。通常の NVIDIA / AMD のセットアップでは、選んだ GPU にモデルのレイヤーを分割する設定として保存され、既存モデルの起動時に指定した場合もそのモデルの設定へ保存されます。GPU を省略したときは、対応カードが複数あれば選択を尋ねる経路があり、複数 GPU を明示するこの指定とは動作が異なります。単一 GPU を選ぶ場合は [`--gpu`](--gpu.md) を使います（`terminal/setup.py:2298-2319, 11503-11508`）。

## 使い方

```sh
# 新しいモデルを2枚のGPUに設定し、設定後の自動起動はしない
./setup.sh --setup --family qwen --model Q2_0 --gpus 0,1 --no-start

# 対応する複数 GPU 全てを選ぶ（NVIDIA / AMD の通常セットアップ）
./setup.sh --setup --family qwen --model Q2_0 --gpus all --no-start

# すでに登録済みのモデルを指定した2枚で起動し、その選択を保存する
./setup.sh --gpus 0,1
```

GPU 番号は NVIDIA では `nvidia-smi` の番号、AMD では Strata の GPU 一覧の番号です。Intel Arc の SYCL 経路では setup が列挙する Arc 番号が使われます（`terminal/setup.py:11273-11275, 4976-5007, 9213-9236, 9239-9264`）。

## 値と既定値

- parser は文字列をそのまま受け取り、数値型や選択肢の検査を parser では行いません。カンマ区切りの番号または `all` に既定値はなく、省略時の GPU 選択は他のセットアップ規則に従います（`terminal/setup.py:11273-11275, 2298-2319`）。
- 通常の NVIDIA 経路では、空白だけの要素を捨てて残りを整数化します。2 個未満、または重複番号があれば失敗します。`all`（大文字小文字を問わず）は、モデルを一緒に使えるカードを選びます。空要素を捨てるため `0,,1` も番号 `0,1` として解釈されます（`terminal/setup.py:2184-2198`）。
- NVIDIA の明示番号は検出済みカードと利用条件を照合します。番号が存在しない、またはその GPU が Strata で使えない場合は停止します。複数利用時に VRAM 条件だけを満たさないカードを明示した場合はリスク確認を出し、既定の回答は「いいえ」です（`terminal/setup.py:2201-2227, 7144-7153`）。
- AMD 経路でもカンマ区切りの番号または `all` を使い、2 個以上の重複しない番号が必要です。指定カードは検出済みで AMD backend が対応する必要があります。`all` は通常、利用可能な専用メモリ GPU が 2 枚以上あればそれらを選び、UMA/APU は除外します（`terminal/setup.py:4976-5007`）。
- Intel Arc の app/control SYCL 経路は `_select_sycl_cards` で選択します。`all` は列挙カード全て、番号列は各要素を整数として認識できるものだけを探し、見つかったものがあればその部分集合、ひとつもなければ先頭カードを返します。この経路は一般の NVIDIA / AMD 用検査より前に分岐するため、未知番号や不正要素が通常経路と同じ形式で拒否されるとは限りません（`terminal/setup.py:11414-11417, 9239-9264`）。

## 実行時の動作

通常の NVIDIA セットアップでは指定 GPU を確認し、複数枚なら `multi` として後続のモデル適合・エンジン準備へ渡します。選択順はそのまま保持され、GPU ロール指定がなければ先頭カードが代表 GPU になります（`terminal/setup.py:2298-2304, 11660-11670`）。AMD のセットアップでは指定順で `chosen` を作り、複数枚ならそれらをレイヤー分割対象にします（`terminal/setup.py:11619-11643`）。

構成生成では複数 GPU の番号配列を run config の `gpu` に保存し、`layer_split` を指定値または `auto` にします。実行時のレイヤー分割引数は server が構成を見て追加します。GPU ロールも併せて指定した場合は Main GPU が最後になるようカード順を作り、`gpu_order: as_given` とロール情報を保存します（`terminal/strata_control/setup_config.py:476-516`; 引数追加は `terminal/serve/server.py:3614-3615`）。

既存モデルを通常起動する経路でも、`--gpus` の値を GPU 配列に変換して `start()` に渡します。CUDA の NVIDIA 経路では既存モデル設定にカード配列、`gpus_asked`、`layer_split` を保存してから起動し、AMD の HIP 経路でも同様に AMD 番号として検証して設定を更新します（`terminal/setup.py:2281-2295, 11503-11508, 8522-8533, 8554-8563`）。

他の GPU 指定との関係:

- `--gpu` と `--gpus` は同時指定を意図した構文ではありません。`--gpu 0,2` のように `--gpu` にカンマが入る場合は互換処理で `--gpus 0,2` に読み替えます（`terminal/setup.py:11424-11430`）。
- `--gpu-roles` と `--gpu` / `--gpus` を同時に指定すると parser error になります。ロール指定単独では、Main / Helper の順を `--gpus` 相当の内部値に組み立てます（`terminal/setup.py:11431-11451`）。
- `--layer-split` は複数 GPU の各後続 GPU に割り当てる開始レイヤーを指定します。省略時は `auto` です（[`--layer-split`](--layer-split.md)、`terminal/setup.py:11278-11280`; 保存は `terminal/strata_control/setup_config.py:479-484`）。
- 既存のセットアップを `--setup` で再実行し、保存済み設定が複数 GPU を使っている場合、明示値がなければ保存済みの GPU 番号を再利用します（`terminal/setup.py:11497-11502`）。
- 指定 GPU は常に最終構成に残るとは限りません。モデル固有の複数 GPU 適合判定や low-RAM の選択で複数 GPU 経路を採らない場合、代表 GPU 1 枚に切り替える分岐があります（`terminal/setup.py:11885-11888, 11900-11904`）。

## 適用条件と副作用

- 指定先は同じベンダー / backend の複数 GPU です。通常のセットアップは NVIDIA 同士か AMD 同士で選択し、NVIDIA と AMD を一つのモデルに混ぜる構成にはなりません（`terminal/setup.py:11574-11592, 11619-11643`）。
- `all` の対象範囲は backend ごとに異なります。NVIDIA ではモデルを一緒に実行できるカード、AMD では利用可能カード（専用メモリ GPU が十分ある場合は UMA を除外）、Intel SYCL control 経路では列挙された Arc 全てです（`terminal/setup.py:2184-2191, 4980-4989, 9251-9258`）。
- 明示した GPU がモデルに必要なメモリを持たない場合でも、単に複数 GPU を指定したことを理由に無条件で中断するのではなく、条件によってはリスク警告と確認を行います。`--yes` と明示的な GPU 指定を併用すると、その確認を承諾として続行する場合があります（`terminal/setup.py:2201-2217, 7144-7153`）。
- カード選択は永続化される設定変更です。通常の複数 GPU 構成では `gpu` 配列およびレイヤー分割設定が保存され、既存モデル起動時の `--gpus` もそのモデルの利用カードを更新します（`terminal/strata_control/setup_config.py:476-484, terminal/setup.py:8523-8533, 8556-8562`）。
- Apple Silicon のモデル別分岐は通常の NVIDIA / AMD 共通セットアップ処理より前に委譲されます。Apple 用の `setup_mac.py` scope は索引上別文書群です（`terminal/setup.py:11407-11413`; scope は `docs/cli/README.md:1652-1740`）。
- `--backend sycl` の source-build 経路は引数を `sycl/setup_intel.py` に委譲し、app/control 経路は `intel_control_setup` で run config を作成します。上記の NVIDIA / AMD の共通 validation と同じ動作を全 SYCL 経路へ一般化できる根拠は確認できません（`terminal/setup.py:9213-9236, 11414-11417, 9267-9365`）。

## 出力とエラー

不正な形式・GPU 数不足・重複番号や、選択 GPU が見つからない / 利用できない場合、通常経路では `fail()` がメッセージと案内を標準出力へ出し、終了コード 1 で停止します。GPU 不足時は検出 GPU の表や選択可能な GPU の案内を先に表示する場合があります（`terminal/setup.py:997-998, 1049-1056, 2184-2197, 2218-2227`）。`--gpu-roles` との競合など共通 parser の `ap.error()` は argparse の usage とエラー終了（通常コード 2）になります（`terminal/setup.py:11431-11442`）。

## 根拠

- `terminal/setup.py:11270-11280` — root parser 上の `--gpu` / `--gpus` / `--gpu-roles` / `--layer-split` の定義。
- `terminal/setup.py:2184-2227, 2298-2319, 4976-5007` — NVIDIA の値解析・選択・利用可否確認と、AMD の値解析。
- `terminal/setup.py:11414-11417, 9213-9236, 9239-9264` — SYCL 経路の分岐、委譲、control 経路のカード選択。
- `terminal/setup.py:11424-11451, 11497-11508, 11619-11670` — 別 GPU オプションとの競合・互換読み替え、既存設定の再利用、通常セットアップの選択。
- `terminal/setup.py:8522-8563` — 既存モデル起動で GPU リストを保存する CUDA / HIP 経路。
- `terminal/strata_control/setup_config.py:476-516`, `terminal/serve/server.py:3614-3615` — 複数 GPU / role の run config への保存と layer-split 引数の組み立て。
- `terminal/setup.py:997-998, 1049-1056, 7144-7153` — 出力先、一般失敗時の終了コード、リスク確認と `--yes` の扱い。
