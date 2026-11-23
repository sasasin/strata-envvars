# `strata-inkling-sycl`（SYCL）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| 入口 | Inkling-2-Mini の SYCL standalone CLI |
| 主な実装 | `engine/src/inkling2/sycl/ink_sy_main.cpp`、モデルと GPU 選択処理は `engine/src/inkling2/sycl/ink_sy_common.h` |

## 役割

Inkling-2-Mini の `.strata` v1.1 モデルを SYCL backend で読み込み、モデル情報の表示、forward の自己検査、通常 greedy decode と D-Spark speculative decode の結果照合、生成ベンチマーク、並列 slot 数の計測を行うコマンドです。通常のユーザープロンプトを受け取って文章を生成する対話 CLI ではありません。生成系の検査・計測は、既定の token ID 列または `--prompt-tokens` で指定した整数列を入力に使い、出力は token ID や計測値として標準出力へ表示します（`engine/src/inkling2/sycl/ink_sy_main.cpp:103-110,206-208,236-285`）。

## 基本的な使い方

```sh
# モデルの manifest 情報を読み、概要を表示する
strata-inkling-sycl --info ./model.strata

# 既定の token 列で forward の自己検査を行う
strata-inkling-sycl --model ./model.strata --selfcheck

# 通常 decode と D-Spark decode の token 一致を確認する
strata-inkling-sycl --model ./model.strata --spec-check --gen 32

# 指定 token 列を使って decode ベンチマークを行う
strata-inkling-sycl --model ./model.strata --prompt-tokens 1,2,3,4 --bench
```

これらの例はモデルファイルと利用可能な SYCL GPU がある実行環境を前提とします。情報表示以外はモデルのロードと runner 初期化を行います（`engine/src/inkling2/sycl/ink_sy_main.cpp:171-183,198-203`）。

## 実行モード

| モード | 呼び出し例 | 動作 |
| --- | --- | --- |
| 既定 | `strata-inkling-sycl --model ./model.strata` | モデルをロードして runner を初期化した後、追加の検査・計測をせず終了します。通常の文章生成は行いません（`engine/src/inkling2/sycl/ink_sy_main.cpp:183-203,288`）。 |
| 情報表示 | `strata-inkling-sycl --info ./model.strata` | `probe_only` でモデルを調べ、build・層数・vocab・expert 数などを表示して終了します。通常のモデルロードや runner 初期化より先に処理されます（`engine/src/inkling2/sycl/ink_sy_main.cpp:119,171-180`）。 |
| 自己検査 | `strata-inkling-sycl --model ./model.strata --selfcheck` | prompt token 列で forward を実行し、NaN 数・argmax・上位 logits を表示します。NaN があれば終了コード 2 です（`engine/src/inkling2/sycl/ink_sy_main.cpp:209-234`）。 |
| speculative parity 検査 | `strata-inkling-sycl --model ./model.strata --spec-check` | greedy decode を通常経路と D-Spark 経路で行い、token の一致数や速度を表示します。不一致なら両 token 列を表示して終了コード 3 です（`engine/src/inkling2/sycl/ink_sy_main.cpp:236-254`）。 |
| ベンチマーク | `strata-inkling-sycl --model ./model.strata --bench` | greedy decode の prefill/decode 計測値を表示します。`--no-dspark` がなければ D-Spark 経路を選びます（`engine/src/inkling2/sycl/ink_sy_main.cpp:257-265`）。 |
| 並列 sweep | `strata-inkling-sycl --model ./model.strata --par-sweep` | slot 数 1、4、8、32、64 で forward の集計 token/s と request あたり token/s を計測します。初期化時にも 64 slot を確保します（`engine/src/inkling2/sycl/ink_sy_main.cpp:123,198-199,267-285`）。 |

検査・計測フラグは複数指定でき、処理は自己検査、parity 検査、ベンチマーク、並列 sweep の順に進みます（`engine/src/inkling2/sycl/ink_sy_main.cpp:209-286`）。`--vision` と `--image` の両方が指定された場合は、モデルロード後に画像 encoder を読み込み、画像 embedding の統計値を表示します。片方だけではこの処理に入りません（`engine/src/inkling2/sycl/ink_sy_main.cpp:117-118,185-196`）。

## 主な動作

モデルパスが空なら usage を標準エラーに出して終了コード 1 になります。`--info` はモデルを probe し、失敗時は `[ERROR]` を表示して 1 で終了します。それ以外のモードはモデルをロードしてから runner を初期化し、どちらかに失敗するとエラーを表示して 1 で終了します（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-183,198-203`）。

デフォルト prompt は token ID `1,2,3,4,5,6,7,8`、生成長は 32、context 上限は 4096、parallel は 1 です。prompt の CSV 要素は `atoi` で整数化され、空列になった場合はデフォルト列へ戻ります。整数形式や範囲を厳密に検証する処理はこの parser にはありません（`engine/src/inkling2/sycl/ink_sy_main.cpp:103-104,125-127,144,206-208`）。

複数 GPU は `--gpus` / `--devices` の個数または ID リストで要求できます。2 台目 GPU の初期化に失敗した場合や可視 GPU が不足する場合は、ソース上で単一 GPU へ fallback する経路があります。expert split は `--ep-split` で設定され、`IK2_EP_SPLIT` が `0 < 値 < 1` の場合は環境変数の値が CLI 値を上書きします（`engine/src/inkling2/sycl/ink_sy_main.cpp:129-148,150-163`）。モデル loader は要求値を 0.1〜0.9 に clamp し、GPU 2 台目の利用可否も確認します（`engine/src/inkling2/sycl/ink_sy_common.h:784-834`）。

## 注意点

- `--help` 専用の parser 分岐はありません。未知の引数も parser の分岐でエラーにせず読み飛ばすため、`--help` を渡しても通常はモデル指定不足として usage が表示され、終了コード 1 になります（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-145,166-169`）。
- `--info` は `--model` なしでも直後の非 option 引数をモデルパスとして受け取ります。`--info` の後に option が続く場合はその値を消費しません（`engine/src/inkling2/sycl/ink_sy_main.cpp:119`）。
- `--vision` と `--image` のロード・画像処理は両方が指定された場合だけ実行されます。失敗時は `[ERROR]` を表示して終了コード 1 です（`engine/src/inkling2/sycl/ink_sy_main.cpp:185-196`）。
- `--selfcheck`、`--spec-check`、`--bench`、`--par-sweep` は GPU forward/decode を実行するモードです。コマンドの既定動作と区別して選択してください（`engine/src/inkling2/sycl/ink_sy_main.cpp:209-285`）。

## オプションの文書

SYCL 版の option 一覧と個別文書は [CLI 索引の `strata-inkling-sycl` 節](../../README.md#strata-inkling)を参照してください。共通の CUDA/HIP 版や Metal 版とは parser と option scope が異なります。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-145` — CLI parser、既定値、受理する option と alias。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:146-180` — 環境変数との優先関係、モデル必須判定、情報表示。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:183-208` — モデル・画像ロード、runner 初期化、prompt の既定値。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:209-288` — 検査・計測モード、出力と失敗時の終了コード。
- `engine/src/inkling2/sycl/ink_sy_common.h:772-834` — VRAM 予算、2 GPU の初期化・fallback、expert split の clamp。
