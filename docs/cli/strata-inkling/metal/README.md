# `strata-inkling-metal`（Apple Silicon / Metal）

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-metal` |
| 入口 | Metal backend 用のネイティブ実行ファイル |
| 主な実装 | `engine/src/inkling2/metal/ink_metal_main.cpp` |

## 役割

Inkling-2-Mini の `.strata` モデルを Metal backend で読み込み、自己検査、通常生成と speculative decode の一致確認、単一リクエストまたは複数 slot のベンチマークを実行するコマンドです。モデル情報だけを表示する経路もあります。通常の対話入力や常駐サーバーを提供する実装ではなく、検査・計測用の固定入力を使う実行ファイルです。Apple Silicon 向けのビルドスクリプトは `engine/src/inkling2/metal/build_mac.sh` です（同ファイル 1–4、40–46 行）。

## 基本的な使い方

```sh
# モデルの manifest 情報を表示する（モデル実行環境の初期化は行わない）
strata-inkling-metal --info model.strata

# モデルをロードして固定 token 列で自己検査する。Metal GPU を使用する
strata-inkling-metal --model model.strata --selfcheck

# 通常 decode と speculative decode の出力一致を比較する
strata-inkling-metal --model model.strata --spec-check --gen 32

# 1、4、8、32、64 slot の並列ベンチマークを順に実行する
strata-inkling-metal --model model.strata --par-sweep --prompt-len 128 --gen 32
```

## 実行モード

| モード | 呼び出し例 | 動作 |
|---|---|---|
| バージョン表示 | `strata-inkling-metal --version` | バージョン文字列を表示して終了する。モデル指定は不要。 |
| モデル情報表示 | `strata-inkling-metal --info model.strata` | `.strata` の先頭と manifest section を読み、構成情報を表示して終了する。`--vision` が後続引数にあれば、Vision shard の有無も情報に含める。 |
| ロードのみ | `strata-inkling-metal --model model.strata` | モデルを読み込み、既定では warm 処理と runner 初期化を行って終了する。生成・server 起動には進まない。 |
| 自己検査 | `strata-inkling-metal --model model.strata --selfcheck` | 既定または `--ids` の token 列を slot 0 で forward し、logits の NaN 数と上位 token を表示する。 |
| speculative decode 比較 | `strata-inkling-metal --model model.strata --spec-check` | 同じ入力で通常 greedy decode と speculative decode を行い、出力の一致と計測値を表示する。 |
| 単一リクエスト計測 | `strata-inkling-metal --model model.strata --bench` | 固定生成 token 列を使って prompt/decode の時間と throughput を表示する。 |
| 並列 slot 計測 | `strata-inkling-metal --model model.strata --par-sweep` | 最大 slot 数まで、1・4・8・32・64 の各並列度で prompt/decode 計測を実行する。 |
| Vision 入力確認 | `strata-inkling-metal --model model.strata --vision vision.strata --image image.png` | Vision を初期化して画像を encode し、token 数・次元・統計値を表示する。 |

`--info` と `--version` はモデル必須チェックより前に終了します。それ以外は `--model` が必要です。モード指定がなくてもモデルのロード、（無効化しない限り）warm、runner 初期化が行われます。複数の処理フラグは排他的ではなく、該当する処理がソース上の順番で実行されます。例として `--selfcheck --bench` は自己検査の後にベンチマークを続けます。

## 主な動作

引数を走査した後、通常経路では Metal context を作成し、モデルをロードします。既定ではモデルの warm 処理を行い、指定された slot 数・context 長・batch 上限・Vision shard・kernel directory を渡して runner を初期化します。その後、指定に応じて画像 encode、自己検査、通常/ speculative decode 比較、単一ベンチマーク、並列 sweep を実行します。入力 token 列は `--ids` がなければ固定の 8 token で、ベンチマーク用 prompt は別に生成した決定的な token 列です（`engine/src/inkling2/metal/ink_metal_main.cpp:417-430, 475-515, 517-548, 560-614`）。

`--selfcheck` または `--dump-logits` を指定すると、最後の token の logits を計算します。`--dump-logits` は指定したパスを binary write mode で開き、語彙サイズ分の `float` logits を書きます。開けない場合はソース上でエラーを表示せず、dump を省略して処理を続けます。既存ファイルを指定すると上書きされます（同 `:517-548`）。

`--image` は画像 encode を行いますが、その埋め込みを生成 prompt に接続する処理はこの main の後続にはありません。自己検査・speculative 比較・ベンチマークは `printf` で標準出力へ結果を出し、初期化・forward 等の失敗は主に標準エラーへ `[ERROR]` を出して status 1 で終了します。未知引数およびモデル未指定は status 2 です（同 `:432-473, 483-508, 531-548, 560-616`）。

この実装には `--serve` の parser や server loop はありません。ファイル冒頭コメントに `--serve` の記載がありますが、引数 parser では未知引数として拒否されます（同 `:1-4, 432-467`）。また、自動的な `--help` 処理もなく、未知引数として status 2 になります。

## オプションの文書

Metal コマンドの option scope と個別文書は、[CLI 索引の `strata-inkling-metal` 節](../../README.md#strata-inkling)を参照してください。値・既定値・条件などの詳細は各 option 文書に記載しています。

## 根拠

- `engine/src/inkling2/metal/ink_metal_main.cpp:1-4` — 実行ファイルの説明コメント。`--serve` については現行 parser と不一致。
- `engine/src/inkling2/metal/ink_metal_main.cpp:91-116, 417-473` — `--info` / `--version` の早期終了、引数認識、必須モデル、未知引数と usage の処理。
- `engine/src/inkling2/metal/ink_metal_main.cpp:475-515` — Metal context、モデルロード、warm、runner 初期化、画像確認、既定 token 列。
- `engine/src/inkling2/metal/ink_metal_main.cpp:517-548, 560-616` — 自己検査・logits 出力、decode 比較、bench、parallel sweep と失敗経路。
- `engine/src/inkling2/metal/build_mac.sh:1-4, 40-46` — Apple Silicon 向け実行ファイルのビルドと配置先引数。
