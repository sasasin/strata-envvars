# `setup.py --gpu`

調査対象: Strata commit `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-02 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（`setup.sh` / `START-HERE.bat` などから呼び出し） |
| オプション | `--gpu` |
| 別名 | なし |
| 値 | GPU 番号を表す10進整数。NVIDIA は `nvidia-smi` の番号、AMD は setup が列挙する番号 |

## 役割

モデルの setup で使う GPU を1枚に指定します。複数 GPU で1モデルを動かす指定は `--gpus`、カードごとの役割指定は `--gpu-roles` です。既存モデルを通常起動する場合にも使えますが、その場合は起動時だけの選択として処理されます（AMD の DeepSeek には選択を記憶する例外があります）。parser の help にもこの違いが記載されています（`setup.py:9111-9117`）。

## 使い方

Linux で NVIDIA GPU 1 を setup に指定する例:

```sh
./setup.sh --setup --gpu 1
```

既に導入済みのモデルを GPU 1 で一度だけ起動する例:

```sh
./setup.sh --gpu 1
```

`setup.sh` は引数を `setup.py` に渡し（`setup.sh:8-12`）、Windows の `START-HERE.bat` も同様に転送します（`START-HERE.bat:44-54`）。`SETUP.bat` と `UPDATE.bat` もそれぞれ `--setup` / `--update` を加えて同じ入口を呼びます（`SETUP.bat:3`、`UPDATE.bat:79`）。

## 値と既定値

- 値は必須です。parser は型変換をせず文字列として受け取り、後段で `strip().isdigit()` を確認して整数化します（`setup.py:9111-9112, 9232-9238`）。負数、符号付き数値、文字列は拒否されます。空値は `argparse` の引数エラーです。
- 番号は NVIDIA では `nvidia-smi` の番号、AMD では setup の GPU 一覧番号です（`setup.py:9111-9112`）。指定した番号が実機にない、または Strata が使えないカードの場合は後段のカード検査で失敗します（NVIDIA: `setup.py:1957-1959, 1853-1879`、AMD: `setup.py:9424-9428`）。
- 省略時、NVIDIA では使えるカードが複数あれば組み合わせ可能なカード選択を尋ね、組み合わせられるカードがなければ VRAM が最大の使用可能カードを選びます（`setup.py:1950-1970`）。AMD では使用可能なカードから setup の順位で選択し、単独 GPU と UMA APU が混在する場合は専用メモリを持つカードを優先します（`setup.py:9429-9436`）。
- `--gpu 0,2` のようにカンマを含む値は互換入力として `--gpus 0,2` に移され、単一 GPU 指定ではなくなります（`setup.py:9232-9235`）。複数カード指定の件数・重複・`all` の扱いは `--gpus` 側の処理です（`setup.py:1836-1850`）。`--gpu-roles` と `--gpu` / `--gpus` は同時指定できません（`setup.py:9240-9247`）。
- 数値の `--gpu` と `--gpus` を併記した場合、setup のカード選択は `--gpus` を先に採用します（`setup.py:1953-1959`）。カンマ形式の `--gpu` と `--gpus` を併記した場合も、既に指定された `--gpus` は変換処理で保持されます（`setup.py:9232-9235`）。

## 実行時の動作

setup 経路では、指定した NVIDIA カードを `choose_gpus()` が検査して選択し、setup の GPU 情報・CUDA toolkit 選択・VRAM に基づく設定に使います（`setup.py:1950-1959, 9462-9485`）。複数 GPU が見つかった場合などは、選択カード番号をモデル設定の `gpu` に保存し、次回の起動で再質問しないよう `gpus_asked` も記録します（`setup.py:9464-9469, 10338-10346`）。明示した NVIDIA カードは `GPU_PICK` にも設定され、engine 更新時のカード選択より優先されます（`setup.py:9466-9468, 5468-5474`）。

AMD setup では、指定番号を使用可能な AMD GPU 一覧から引きます。未指定時の自動選択とは別に、setup 内部で選んだ GPU 番号も後続処理向けに `a.gpu` に設定される場合があります。明示指定か自動選択かはその代入前に `_cards_named` へ記録されます（`setup.py:9420-9446`）。

既存モデルの通常起動では `--gpu N` は選択した GPU を検査した後、起動する engine の引数 `--gpu N` に渡されます。NVIDIA のこの分岐ではモデル設定の選択を保存しません（`setup.py:9312, 7191-7209`）。AMD の HIP 起動でも engine に渡し、DeepSeek の場合は明示したカード選択をモデル設定に記憶できたとき、その旨を出力します（`setup.py:7153-7176`）。一方、既存モデル起動で `--gpus` を使うと複数カードを設定に保存し、以後そのモデルで使います（`setup.py:7157-7168, 7198-7205`）。

`--gpu` は `--gpu-roles` や `--gpus` と値の意味が異なります。`--gpu-roles` との併用はエラーです。`--gpus` との併用は parser で一律拒否されず、両方が存在すると setup は `--gpus` を優先するため、意図しないカード選択を避けるには片方だけ指定します（`setup.py:9232-9247, 1953-1959`）。

## 適用条件と副作用

- 対象は `setup.py` の root parser です。setup wrapper は引数を委譲します。Apple Silicon で `STRATA_CONTROL_INSTALL=1` なしに `setup.py` を起動すると、冒頭で `metal/setup_mac.py` に委譲するため、このページの parser 検証経路とは異なります（`setup.py:9068-9070`）。
- setup 時はカード選択によりモデルごとの設定ファイルを書きます（`setup.py:10338-10346, 10436-10454`）。既存モデル起動時の NVIDIA `--gpu` は、その起動プロセスに対する選択です。AMD DeepSeek での記憶動作は `gpu_pick.remember()` が設定ファイルを更新できた場合に限られます（`setup.py:7169-7176`）。
- 選択 GPU の VRAM はモデル適合判定や設定値の算出にも使われます。`--gpu` 自体が GPU を有効化したり、異なるメーカーの GPU を同時利用したりするものではありません。setup は選択したカードについて必要な engine 対応等を確認し、満たさない場合は停止します（例: NVIDIA の選択・CUDA 判定 `setup.py:9462-9485`）。

## 出力とエラー

- 数字以外の値（カンマを含む互換値を除く）は `ArgumentParser.error()` によりエラーとなり、エラーメッセージに形式例が示されます（`setup.py:9232-9238`）。
- 選択した GPU が見つからない、または利用できない場合は、GPU 一覧と利用可能な選択肢を示して setup を停止します（`setup.py:1858-1879`）。AMD の番号が利用可能一覧にない場合も利用可能番号を案内します（`setup.py:9424-9428`）。通常の `fail()` は `[X]` と修正案を出し、終了コード 1 で終了します（`setup.py:904-909`）。
- setup の NVIDIA でカードを複数検出し、指定カードが8 GB未満など共有利用時だけの VRAM 条件にかかるケースは、この単一 GPU 指定の検査とは別です。`--gpus` の複数カード検査が同条件を確認・質問します（`setup.py:1853-1869`）。

## 根拠

- parser 定義と値の説明: `setup.py:9111-9117`
- 入力の数値検査、カンマ値の互換変換、`--gpu-roles` との排他: `setup.py:9232-9259`
- NVIDIA setup の選択・検証と既定選択: `setup.py:1853-1879, 1950-1970, 9462-9485`
- AMD setup の選択・適用: `setup.py:9420-9446`
- 起動時の選択と engine への転送、AMD DeepSeek の記憶: `setup.py:7153-7176, 7191-7210`
- 設定ファイルと engine 更新への影響: `setup.py:5468-5474, 10338-10346, 10436-10454`
- この調査は現行 checkout の parser と Strata ソースを確認したものです。同 revision の `--help` 実行、ビルド、実機 GPU での動作確認は行っていません。
