# `STRATA_METAL_PREFETCH2`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。外部ライブラリの環境変数は対象外。

## 役割

Metal エンジンで expert を SSD から読む streaming 経路を使うとき、decode 中に現在の層から2層先の router logits を使って expert を先読みする件数（top-k）を指定します。未設定時は `0` で、この2層先先読みは無効です。正の値を設定すると、各 token について予測 logits の上位 expert を選び、まだ arena にない expert の読み込みを I/O queue に追加します。

これは読み込みを先に始めるための値です。router 選択や expert 計算の値を切り替える設定ではありません。対象は `metal/src/engine/stream.cpp` と `window.cpp` の Metal streaming 実装です。

## 値と判定

`ExpertStream::open()` が共通 helper `env_int()` を通して値を読みます。helper は未設定または空文字列なら既定値を返し、それ以外は `std::atoi()` の結果を返します。文字列全体の検証はせず、`atoi` が認識する先頭の整数部分を使います。

| 環境変数の状態 | `pre_k2_` | 2層先先読み |
|---|---:|---|
| 未設定 | 0 | 無効 |
| 空文字列 | 0 | 無効 |
| `0`、`-1`、数値で始まらない文字列 | `atoi` の結果（通常0。`-1` は -1） | 0以下なので無効 |
| 正の整数（例: `4`） | その整数 | 有効。実際に使う top-k は最大32 |
| 整数の後ろに文字が続く値（例: `4xyz`） | `atoi` が読む先頭の整数（この例では4） | 結果が正なら有効 |

先頭空白や符号も `atoi` の変換規則に従います。`atoi` のため、変換不能な文字列と `0` は区別されず、入力範囲や末尾文字に対する独自エラー・警告・fallback はありません。`ahead()` は K を `min(K, 32)` に制限します。

## 有効になる条件

- Metal エンジンが `ExpertStream::wanted()` により SSD streaming を選択し、`ExpertStream::open()` が呼ばれていること。非 streaming ではこの値を読みません。
- `STRATA_METAL_PREFETCH` により次層向けの予測 logits が有効であること。`window.cpp` は同変数が設定され、`atoi(value) <= 0` の場合に通常の予測 buffer を作らず、2層先予測 buffer も作りません。未設定なら有効ですが、空文字は `atoi("") == 0` となるため無効です。
- decode の層 `l` について `l + 2 < 48` であること。最後の2層から先は対象外です。
- `at_layer()` が prompt chunk 経路でないこと。`T > 8` を prompt と判定して先に戻るため、その呼び出しでは2層先読みをしません。

CLI 引数や設定ファイルからこの値を上書きする処理は、調査した参照箇所にはありません。他の streaming 条件（モデルの常駐可否や `STRATA_METAL_STREAM`）を満たさない場合、この設定単独では streaming を開始しません。

## 実行時の詳細

`window.cpp` の初期化で streaming が選ばれると `ExpertStream::open()` が呼ばれ、`pre_k2_` はその時点で一度読み込まれます。既に開いた engine の実行中に環境値を変更しても反映されず、別の engine 初期化で再度読み取られます。

2層先読みが有効なら、`window.cpp` は層 `l` の FFN 入力 `XF_` から層 `l+2` の router logits を計算し、`predL2_` に保存します。層境界の host handshake で `ExpertStream::at_layer()` がその logits を受け取り、`ahead(l + 2, T, pred2, pre_k2_)` を呼びます。`ahead()` は各 token の logits から上位 K 個（K は最大32）を選び、複数 token で重複する expert をまとめ、logit が最大だった候補から順に処理します。arena に既にある expert は再読み込みせず、未配置の expert は空き victim slot と prefetch queue に追加されます。次層向け先読みが先に同じ経路で行われ、その後に2層先向けが queue に追加されます。

この値専用のログやエラーはありません。streaming engine の終了時などに出る集計 `expert stream ... read-aheads ...` は先読み件数全体を示し、次層先読みと2層先読みを個別には区別しません。

## 根拠

- `metal/src/engine/stream.cpp:27-30`: `env_int()` の未設定・空文字処理と `atoi`。
- `metal/src/engine/stream.cpp:149-162`: streaming 初期化時の read split / prefetch 設定の読み込み。対象値の既定値は0。
- `metal/src/engine/stream.cpp:571-612`: 候補上位 K の抽出、重複排除、既存 slot の除外、未配置 expert の先読み投入、K の32上限。
- `metal/src/engine/stream.cpp:614-712`: prompt 経路での早期 return、および decode 経路での次層・2層先読み呼び出し。
- `metal/src/engine/stream.h:62-66,119`: `pred2` の説明、`ahead2()`、既定メンバー値。
- `metal/src/engine/window.cpp:425-435`: streaming 判定後に `ExpertStream` を生成・open する経路。
- `metal/src/engine/window.cpp:538-546`: `STRATA_METAL_PREFETCH` による予測 buffer と2層先予測 buffer の確保条件。
- `metal/src/engine/window.cpp:292-295,760-777`: 層境界で logits を渡す箇所と、`XF_` から次層・2層先 router logits を計算する箇所。
- `docs/MAC.md:183-212`: Metal のスイッチと streaming の説明。`STRATA_METAL_PREFETCH2` 個別の既定値・性能測定値は記載されていないため、効果や速度向上は断定しない。
