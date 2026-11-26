# `--pcie-mode`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（2026-11-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` の有無にかかわらず共通 parser） |
| オプション | `--pcie-mode` |
| 別名 | なし |
| 値 | 文字列。`auto`、`kernel`、`dma`、`direct` が実装コメントに記載されている |

## 役割

キャッシュにない expert の PCIe share を verifier がどの経路で扱うかを選びます。`auto` は既定値で、すべての pack で copy-kernel 経路を使います。値は CUDA/HIP 側と SYCL 側の engine parser にあります。

## 使い方

```sh
# 既定の copy-kernel 経路を明示する
strata --pack model.strata --tokens prompt.txt --pcie-mode kernel

# DMA 経路を選ぶ
strata --pack model.strata --tokens prompt.txt --pcie-mode dma

# PCIe share の読み出しで device alias を直接使う
strata --pack model.strata --tokens prompt.txt --pcie-mode direct
```

## 値と既定値

- 省略時は `auto` です。ソースの parser は値を文字列として保存し、値の列挙チェックや補正を行いません。
- verifier へ渡す際、`dma` は mode 0、`direct` は mode 1、それ以外は mode 2 に変換されます。したがって `auto` と `kernel` は同じ mode 2 になり、未記載の値も拒否されず mode 2 として動きます。
- 同じオプションを複数回指定すると、parser の走査中に同じ設定値を代入するため最後の値が残ります。
- 値を末尾で省略すると `--pcie-mode needs a value` を stderr に出し、終了コード 2 で終了します。

## 実行時の動作

| 値 | verifier の mode | ソースで確認できる処理 |
| --- | --- | --- |
| `auto`、`kernel`、その他の文字列 | 2 | PCIe share の blob を verifier の copy kernel で staging 領域へ移し、参照先を staging に切り替えます。 |
| `dma` | 0 | expert source が staging 領域を転送先にし、fetch callback に fetch 数を渡します。verifier は DMA 側の staging に到着した share を使います。 |
| `direct` | 1 | expert source の device alias を share の参照先にし、fetch callback へは 0 件を渡します。mode 2 の staging copy は行いません。 |

この設定は PCIe share の実行経路を選ぶもので、share の有無や大きさを指定しません。実際に share があるかは `--pcie-frac` 等の計画結果に依存し、share の expert がない場合はこの経路も使われません。layer split 時も各 stage の verifier に mode が設定されます。

## 適用条件と副作用

- `--pcie-mode dma` では `STRATA_PIPED_CONCURRENT=1` の並行 prompt read が無効になります。該当条件で engine は `strata batch: STRATA_PIPED_CONCURRENT is off beside --pcie-mode dma` と stderr に理由を出し、通常の読み取り経路へ進みます。
- `STRATA_ADAPT_FETCH` による PCIe miss の resident slot への admission は、`dma` と `direct` では無効です。serve/generate の該当処理は理由を含む stderr の案内を出します。`auto`、`kernel` および未知値はこの二値の除外条件には該当しません。
- copy-kernel 経路では verifier 内で staging copy kernel を呼びます。`dma` / `direct` ではこの mode 2 専用処理を通りません。

## 出力とエラー

値自体の不正を示すエラーはありません。parser が値を列挙検証しないため、未知値は copy-kernel 経路として受理されます。値が末尾で欠けた場合は parser が stderr に不足を出し、コード 2 で終了します。未知の別オプションは `unknown argument` を stderr に出して usage を表示し、コード 2 で終了します。

## 根拠

- `engine/src/program/generate.cpp:1044` — `auto` の既定値と実装コメント上の値候補。
- `engine/src/program/generate.cpp:3842-3847, 4068` — 引数値の取得、値不足時の stderr と終了コード 2、parser 登録。
- `engine/src/program/generate.cpp:13682-13707, 24542-24547` — CUDA/HIP 系 verifier（通常および stage）の mode 変換。`dma` / `direct` 以外が mode 2 となる。
- `engine/src/core/expert_source.cpp:5624-5627, 5688-5695` — mode 0 では staging pointer、非 0 では device alias を指定し、非 0 では fetch 数を 0 として callback へ渡す。
- `engine/src/core/verify.cpp:2881-2890` — mode 2 に限る verifier の staging copy kernel と pointer の再配置。
- `engine/src/program/generate.cpp:15067-15076, 24580-24589` — `STRATA_ADAPT_FETCH` の `dma` / `direct` 除外条件と stderr の理由出力。
- `engine/src/program/generate.cpp:21018-21035` — `dma` を `STRATA_PIPED_CONCURRENT` の停止理由に含める判定。
- `engine/sycl/src/program/generate.cpp:691, 2061, 7962-7987, 13786-13790`、`engine/sycl/src/core/verify.cpp:1772-1779` — SYCL parser と同じ mode 変換、および mode 2 の staging copy。
- `engine/src/program/generate.cpp:4268-4273` — 未知のオプション名の stderr、usage 表示、終了コード 2。値の未知性はこの分岐では検出されない。
