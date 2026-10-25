# `STRATA_SPLIT_NEAR_TIE_PCT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve --layer-split auto` の自動配置を終えた後、予測時間が選択配置に近い別の layer split があれば、その候補を試す方法とともに stderr に表示するための割合（%）です。配置を選ぶコストモデルや、最終的に選ばれる split はこの値では変わりません。対象処理は CUDA の multi-GPU split 探索です。

## 値と判定

値は `std::atof` で `double` に変換されます。文字列全体の妥当性検査、範囲制限、clamp はありません。

| 環境変数の状態 | `near_pct` | 結果 |
|---|---:|---|
| 未設定 | `4.0` | 選択配置の予測時間より最大 4% 高い予測時間までを候補にする |
| 数値文字列 | 変換された値 | 正の値なら候補範囲に使う。例: `2.5` は 2.5%、`0.5` は 0.5% |
| 空文字 | `0.0` | `near_pct > 0` を満たさず案内しない |
| 数字で始まらない文字列 | `0.0` | 同上。`atof` が変換できない場合の値 |
| `0` または負数 | 0 以下 | 案内しない |

`atof` は文字列全体が数値かを検証しないため、数値の後ろにある文字は変換結果に影響しない場合があります（例: `4abc` は `4` として変換されます）。大文字小文字の比較や真偽値としての解釈はありません。`nan` など正数比較を満たさない値も案内条件を通りません。

## 有効になる条件

環境変数の判定結果が正の値でも、次の条件をすべて満たすときだけ候補を探します。

- `--serve` と `--layer-split auto` が指定されている。
- 自動 split が実際に複数 GPU で動く（GPU が1台だけなら自動 split は解除される）。
- GPU 数 `ns` が2または3。4 GPU 以上はこの案内処理の対象外。
- GPU 間の差が「混在」と判定される。コードでは、最速と最遅の GPU の推定 layer 時間の比が10%を超えるか、PCIe miss cost scale の比が10%を超える場合です。
- 探索後の最良予測時間が正で、価格付け済み候補がある。
- 最良配置の境界から少なくとも3 layer 離れ、かつ閾値内に入る別候補がある。feasibility gate が有効なときは、その候補も prompt を開始できる配置である必要があります。

明示的な `--layer-split K[,K2...]`、serve でない実行、単一 GPU、4 GPU 以上、差の小さい GPU 構成ではこの変数は参照されても警告条件に到達しません。CUDA device の layer 時間は SM 数と clock から見積もられ、link scale は split 探索中の PCIe probe 結果（native pack でない場合は各段階 1.0）から作られます。

## 実行時の詳細

値は `src/program/generate.cpp` の自動配置探索が完了した後、近似候補のログを組み立てる箇所で読み取られます。式は `getenv` で設定有無を調べ、設定時には再度 `getenv` した文字列を `atof` に渡します。static cache ではなく、この判定箇所で評価されます。候補条件は `pc.first <= best_ms * (1 + near_pct / 100)` で、境界間距離が3 layer未満の近傍配置は除外します。最も予測時間が小さい適格な別配置を表示します。

候補があれば、stderr に `strata generate: layer split auto: NEAR TIE - ...` の行を出し、候補の K、予測時間、最良配置との差、予測は decode window の価格付けで prompt を価格付けしていないこと、`--layer-split K` で試す方法を表示します。候補がなければこの行は出ません。この変数がログ以外の動作や配置結果を変える処理はありません。

## 文書との照合

`docs/MULTI_GPU.md` は `--layer-split auto` が各カードの VRAM を見て配置することと、起動ログの例を説明していますが、`STRATA_SPLIT_NEAR_TIE_PCT` や近似候補の案内については記載していません。変数の値域、既定値、条件、ログ動作はソースコードを根拠にしています。

## 根拠

- `src/program/generate.cpp:2299-2346` — layer split は `--serve` が必要で、`auto` は可視 GPU が1台なら解除される。
- `src/program/generate.cpp:3582-3598,3692-3727` — 自動 split 探索、GPU 数と layer/link コスト推定。
- `src/program/generate.cpp:3964-3978,3995-4094` — 2/3 GPU の候補価格付けと選択、4 GPU の別探索経路。
- `src/program/generate.cpp:4162-4200` — near-tie 候補条件、環境変数の既定値・変換、stderr の案内文。
- `docs/MULTI_GPU.md:41,63-68,180-187` — 自動 split の概要と標準起動ログ例。
