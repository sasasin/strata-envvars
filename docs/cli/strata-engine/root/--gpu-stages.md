# `strata generate --gpu-stages`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--gpu-stages` |
| 別名 | なし |
| 値 | 値なしの boolean flag |

## 役割

各モデル層の GPU graph を mixer、FFN front + router、post の3区間に分けて replay し、区間ごとの GPU 時間を表示する計測モードです。`--stage-timing` のような未 capture の区間時間ではなく、capture した graph の replay を計測します。測定値を出した後は通常の token 生成・serve ループへ進まず終了します。

## 使い方

```sh
# pack と必須 token 列を指定して、各 GPU stage の replay 時間を表示する
strata generate --pack /path/to/pack --tokens "1,2,3" --gpu-stages
```

`--pack` と `--tokens` は usage に示される通常の入力です。GPU-stage の replay には layer graph を作れるモデルと単一 GPU の実行構成が必要です。

## 値と既定値

- 値は取りません。`--gpu-stages` が現れると `gpu_stages` を `true` にします。
- 既定値は `false` です。複数回指定しても同じ boolean を true にするだけです。
- parser にこの flag 固有の値検証はありません。

## 実行時の動作

graph capture が有効で native pack でない場合、通常の pre/post graph に加え、split capture と5段階 prefix 用 graph を各層に対して作ります。stage replay は各層の mixer、FFN front + router、post graph を同一 stream 上で順に実行し、GPU event から区間時間を集計します。CUDA 実装では初回の集計後に20回を平均し、GDN/QSA 別の mixer 表、5段階 prefix と sweep による追加計測も行います。最後に `--gpu-only-full` との比較案内を表示し、graph と関連 buffer を解放して終了コード 0 を返します。

この計測用 capture では fused GR を無効にします。出力は標準出力の表で、指定した出力ファイルへの書き込みはこの分岐にはありません。モデルや GPU の初期化・重み読み込みは計測分岐より前に行われるため、この flag は起動コストを省くものではありません。

`--no-capture` を同時指定すると capture が省略されますが、stage 分岐自体は実行されます。その結果 split graph がないという replay error で終了コード 1 になります。`--graph-only` と `--gpu-only-full` を同時に付けても、先に評価される `--gpu-stages` 分岐が計測後に終了するため、それらの計測には進みません。

## 適用条件と副作用

- `--layer-split` による複数 GPU 実行とは併用できません。parser 後の validation が stderr に理由を出し、終了コード 2 で拒否します。
- `--native-flash-attn-short` とも併用できません。同じく通常 decode loop の status validation を要するため終了コード 2 になります。
- `--no-capture` は parser では拒否されず、後段の stage replay が「split capture されていない」として失敗します。
- native pack（IQ pack）は per-layer graph を capture しないため、この計測は利用できません。計測分岐で replay graph がないエラーを stderr に出し、native pack 向けの serve 時 profile の案内を付けて終了コード 1 になります。
- capture や replay、GPU event/synchronization に失敗した場合もエラーを stderr に出して終了コード 1 になります。
- 重み・GPU state を使って graph replay と計時を繰り返します。通常生成の応答文や token stream は出力しません。
- Qwen3.5 MoE family は `generate` の共通 parser より前に `engine/src/qwen35` の runner へ dispatch されます。`--gpu-stages` の受理をその parser について確認できなかったため、この文書の適用範囲には含めません。

## 根拠

- `engine/src/program/generate.cpp:948-951` — flag の説明と既定値 false の field。
- `engine/src/program/generate.cpp:1402-1404` — help に記載された3 graph の計測内容と出力後終了する動作。
- `engine/src/program/generate.cpp:3810-3818` — Qwen3.5 MoE を別 parser へ dispatch する分岐。
- `engine/src/program/generate.cpp:4215-4219` — `--gpu-stages` を値なし flag として parser が受理する箇所。
- `engine/src/program/generate.cpp:5293-5307` — `--native-flash-attn-short` と複数 GPU layer split の拒否・stderr・終了コード。
- `engine/src/program/generate.cpp:6112-6113` — stage 計測時に fused GR を無効にする設定。
- `engine/src/program/generate.cpp:10544-10554` — capture の実行条件、split capture 指定、capture 失敗時の終了コード。
- `engine/src/program/generate.cpp:10728-10761`、`10868-10874` — stage replay、20回平均の表、終了処理と成功終了。
- `engine/src/core/session.cpp:200-218, 226-280` — 通常 graph と split capture の初期化、および層ごとの追加 graph capture。
- `engine/src/core/session.cpp:327-381` — 3区間 graph の replay、GPU event による計時と集計。
- `engine/src/core/session.cpp:424-469` — prefix 計測のため residual を保存・復元しながら prefix graph を replay する処理。
- `engine/src/core/layer.cpp:1549-1556, 1570-1597` — prefix の区間境界と mixer / FFN-front-plus-router の stage 構成。
- `engine/sycl/src/program/generate.cpp:614-616, 2179` — SYCL 側も同じ既定値と値なし parser 分岐を持つこと。
- `engine/sycl/src/program/generate.cpp:2711-2721` — SYCL 側の同じ併用条件の拒否。

## 調査範囲

同一 revision の CUDA/HIP 系 `engine/src` と SYCL 系 `engine/sycl/src` の parser・処理経路を確認しました。CLI help は既存実行ファイルを起動していないため補助資料には使わず、ソースの usage/help 文字列と照合しています。実機での出力値、GPU ごとの計測精度、追加 backend における動作は確認していません。
