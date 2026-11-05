# `--model`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py`（Apple Silicon の通常実行では `metal/setup_mac.py` に委譲） |
| オプション | `--model` |
| 別名 | なし |
| 値 | `MAC_MODELS` にあるモデル名。値は必須。 |

## 役割

Mac 用 setup が選ぶモデルを明示します。指定モデルはメモリ量に応じた推薦値で置き換えられず、収まらない場合も警告を出して選択を維持します。モデルごとにダウンロード元のファイル、モデル family、pack、起動設定が決まります。

## 使い方

Strata checkout のルートで実行します。次の例は `IQ3_XXS` を選び、設定と起動スクリプトを作成した後、サーバーを自動起動しません。

```sh
./setup.sh --model IQ3_XXS --no-start
```

Mac では `setup.py` が `STRATA_CONTROL_INSTALL=1` でない場合に引数を `metal/setup_mac.py` へ渡します。したがって、この文書の値規則はその Mac parser に対するものです。`STRATA_CONTROL_INSTALL=1` の Control モードや Windows/Linux の `setup.py` parser は別スコープです。

## 値と既定値

値は必須で、現行 parser の `choices=list(MAC_MODELS)` により次の名前だけを受理します（大文字小文字も一致が必要です）。

- `Q2_0`、`IQ3_XXS`、`IQ3_S`
- `UD-IQ1_M`、`UD-Q2_0`、`UD-IQ2_XS`、`UD-Q2_K_XL`、`UD-IQ3_XXS`、`UD-Q3_K_XL`、`UD-IQ4_XS-v31`、`UD-Q4_K_XL`、`UD-Q5_K_XL`、`UD-Q6_K_XL`
- `Gyro-S`、`Gyro-M`

値を省略すると parser 上の `a.model` は `None` です。setup はメモリに基づく推薦モデルを初期値に選択メニューを表示します。`--yes` 併用時はその推薦値が選ばれます。明示したモデルはメモリ適合性を検証して拒否するのではなく、必要な Metal 常駐メモリと実測状況などを警告します。現行 revision では `METAL_Q5_0_DOWN = True` で、旧版で `missing` 扱いだった4モデルも parser の選択肢に含まれます。

値なし、または `MAC_MODELS` にない値は `argparse` の引数エラーになります。重複指定時は通常の `argparse` の単一値引数として最後に指定した値が `a.model` に入ります。

## 実行時の動作

- 既存の設定が見つかり、明示的な setup/update/check/build 指定もない場合、通常は既存モデルをすぐ起動します。しかし `--model` があるとこの早期起動条件を満たさず、setup の選択・準備経路へ進みます。
- family は選択モデルの `MAC_MODELS` エントリから決まります。`--family` と異なる場合は警告を出してモデル側の family を使います。選択モデルから family の tag を作り、モデルの shard 名と保存先、pack を決めます。
- 通常経路では不足している shard をダウンロードし、shard 検査と対象 family の hash 検証を行います。Unsloth の複数 shard セットは GPU 用 GGUF に再梱包し、pack が未作成なら `tools/iq_pack.py` で作成します。その後 `strata-<tag>.json` と `run-<tag>.sh` を書き、`--no-start` がなければ起動します。
- モデルが Metal の常駐予算を超える場合は SSD streaming の警告を出します。streaming の選択はモデル名と Mac のメモリ量から計算され、設定にも反映されます。
- `--update` 併用時はモデルファイルをダウンロード・準備せず、指定モデルの shard と pack が既にあるか確認して終了します。未導入なら「何もインストールされていない」旨と `./setup.sh --setup` の案内を表示します。

## 適用条件と副作用

この option が使われるのは `setup.py` が macOS 上で `STRATA_CONTROL_INSTALL` なしに Mac setup へ委譲する経路です。Mac setup は Apple Silicon、必要な macOS バージョン、Command Line Tools を確認し、問題があれば setup を停止します。

モデルの選択によってネットワークからの大容量モデル取得、vision encoder の取得（別 option `--vision` の設定による）、モデル pack や Unsloth 再梱包ファイルの作成、エンジン build、設定 JSON と起動スクリプトの書き込みが発生し得ます。モデル準備が必要なのに Strata engine が実行中なら、Mac の停止リスクを示して準備を中断します。`--model` 自体はファイルを直接削除しません。

同じ値でも別 parser の選択肢・効果とは異なります。特に `setup.py` の Control モードや非 Mac parser の `--model` は本書の scope ではありません。

## 出力とエラー

- 無効な値や値の欠落は `argparse` が usage とエラーを stderr に出し、終了コード 2 で終了します。
- 明示モデルが推奨よりメモリを要する場合や未実測の場合、警告を表示して選択を続けます。Metal engine が動かせないモデルとして `missing` と印された場合も、モデル選択は保持され、ロード時に engine が停止する旨を警告します（現行 revision の parser 候補には `missing` エントリはありません）。
- Mac の要件を満たさない場合や、準備時に Strata engine が実行中の場合は `S.fail` がエラー表示後に終了コード 1 で停止します。
- `parse_known_args` のため未知の余剰引数は拒否されず、`not used on a Mac: ...` と警告されます。これは `--model` の値検証とは別です。

## 根拠

- `metal/setup_mac.py:333-364` — Mac parser の `--model` 宣言、必須値・`MAC_MODELS` choices、未知引数の警告。
- `setup.py:9894-9902` — 通常の `setup.py` 起動から Mac parser への委譲条件。
- `strata_control/mac_fit.py:20-47` — 現行 Mac モデル名、family、shard 数、および Q5_0 kernel 対応フラグ。
- `metal/setup_mac.py:375-428` — 既存設定時の早期起動条件、推薦・明示値の選択、モデル warning、family の決定と不一致時の扱い。
- `strata_control/mac_fit.py:209-250` — 常駐予算判定、メモリ推薦、streaming・未実測・未対応モデルの警告。
- `metal/setup_mac.py:441-454` — `--update` 時の既存ファイル確認と未導入時の案内。
- `metal/setup_mac.py:456-482,484-524,550-579` — shard download/検証、vision encoder、モデル準備と再梱包、設定・起動スクリプト生成、起動抑止。
- `metal/setup_mac.py:497-503` — モデル準備中に engine が動作している場合の停止経路と準備 lock。
- `strata_control/mac_fit.py:162-174`、`setup.py:1072-1077` — Mac 要件判定と `S.fail` の終了動作。
