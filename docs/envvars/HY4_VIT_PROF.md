# `HY4_VIT_PROF`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

HY4-Flash の GPU vision encoder が ViT 各段の処理時間を計測し、画像ごとに `[vit prof]` 行を stderr に出す診断用フラグです。計測有効時は段ごとに GPU stream を同期します。画像エンコードの計算式・モデル設定を切り替える値ではありませんが、同期を挿入するため実行時間の計測条件に影響します。読み取りと計測処理は `VisionEncoder::encode` にあります（`engine/src/hy4flash/run/hy4_vision.hip.h:888-895,946-956`）。

## 値と判定

`getenv("HY4_VIT_PROF") != nullptr` の設定有無だけで判定し、文字列の内容は変換・比較しません。未設定なら無効、空文字を含む何らかの値が設定されていれば有効です。したがって `0`、`false`、空文字、任意の文字列はいずれも有効で、数値境界や大文字小文字による違いはありません。コメントには `HY4_VIT_PROF=1` とありますが、実装は `1` に限定していません（`engine/src/hy4flash/run/hy4_vision.hip.h:946-947`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| GPU `VisionEncoder::encode` の計測判定 | 無効 | 空文字、`0`、`1`、`false`、任意の文字列 | なし（設定値の内容による無効値はない） |

## 有効になる条件

- HY4-Flash の画像を GPU vision encoder で処理すること。リクエストに画像がなければ `VisionCtx` はなく、この画像エンコード処理に入りません（`engine/src/hy4flash/run/hy4_graph.hip.h:218`、`engine/src/hy4flash/run/hy4_vision.hip.h:1126-1143`）。
- `VisionEncoder` が CPU モードでないこと。`encode` は計測判定より先に `cpu_mode` の場合 `encode_cpu` を返します。低 VRAM 時など CPU 読み込みになった場合、または GPU workspace OOM から CPU にフォールバックした画像では、GPU ViT の `[vit prof]` 計測は行われません（`engine/src/hy4flash/run/hy4_vision.hip.h:604-630,888-894,913-923`）。
- vision shard がロード済みで、入力サイズと head dim の検査を通ること。未ロード・サイズ不正・未対応 head dim では計測部より前に失敗します（`engine/src/hy4flash/run/hy4_vision.hip.h:888-903`）。
- 値を有効にする別の CLI 引数や環境変数はありません。コード上、この判定箇所は `HY4_CUDA` などの build macro で囲われていません。HIP/CUDA 共通の GPU encoder にある一方、CPU encoder には適用されません（`engine/src/hy4flash/run/hy4_vision.hip.h:1-7,888-895,946-947`）。

## 実行時の詳細

関数内 `static const bool prof` として初めてこの宣言を実行した時に値を読み、その後は同じプロセス内でキャッシュされます。プロセス実行中に環境を変更しても値は再読込されません。`VisionCtx::setup` は画像レコードごとに `enc.encode` を呼ぶため、GPU モードで複数画像を処理すると各画像の成功時に計測行を出します（`engine/src/hy4flash/run/hy4_vision.hip.h:946-947,1126-1144`）。

有効時、ViT 処理の各 `lap` で `hipStreamSynchronize(st)` を呼び、その区間の経過秒数を同名ステージごとに加算します。出力ステージは `ln`、`qkv gemm`、`attention`、`o_proj gemm`、`fc1 gemm+ln`、`fc2 gemm`、`adapter` です。各 ViT layer の計測値は同じキーへ累積されます。最後は出力 stream を同期した後に adapter 区間を記録し、`std::map` のキー順で値を連結して stderr に出します。計測値は `std::to_string` の先頭5文字です（`engine/src/hy4flash/run/hy4_vision.hip.h:946-956,957-1005`）。

タイマー開始は GPU workspace の確保、RGB 転送、patch embedding の投入後です。そのため最初の `ln` 区間にはこれらの保留処理も含みます。`lap` は各区間で同期するため、コメントどおり測定向けの追加同期が発生します。計測フラグが無効なら `lap` は同期や集計を行わず、プロファイル行も出しません（`engine/src/hy4flash/run/hy4_vision.hip.h:925-956,1000-1005`）。

## ログと測定値

正常に GPU エンコードを完了し、`prof` が有効な場合、stderr に次の形式で一行出ます（値は実行時計測値）。

```text
[vit prof] <stage> <seconds> s, ...
```

ソース上の接頭辞は `[vit prof] ` で、各ステージ値は秒単位です。キャンセルで ViT layer の途中から戻る場合や GPU encoder が通常のエラー経路で失敗する場合は、この末尾の出力に到達しません（`engine/src/hy4flash/run/hy4_vision.hip.h:957-963,1000-1005`）。比較可能な測定結果やハードウェア条件付きの既存測定値は本ソースと `docs/DETAILS.md:1113-1144` に記載がないため、ここでは示しません。

## 根拠

- `engine/src/hy4flash/run/hy4_vision.hip.h:888-903,946-956,957-1008` — GPU/CPU 分岐、環境変数判定、段階計測と stderr 出力。
- `engine/src/hy4flash/run/hy4_vision.hip.h:604-630,913-923` — shard の GPU/CPU ロード選択と workspace OOM 時の CPU fallback。
- `engine/src/hy4flash/run/hy4_vision.hip.h:1126-1144` — 画像ごとの encoder 呼び出し。
- `engine/src/hy4flash/run/hy4_graph.hip.h:218` — テキストのみの要求で vision context が null となること。
- `docs/DETAILS.md:1113-1144` — 利用者向け vision 概要との照合。`HY4_VIT_PROF` 固有の挙動説明はありません。
