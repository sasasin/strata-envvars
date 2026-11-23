# `--draft`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-sycl`（通常実行または `--serve`） |
| オプション | `--draft` |
| 別名 | なし |
| 値 | `off`、`dfly2`、`auto`（`--serve` ではこの3値を検証） |

## 役割

Hy4-Flash の DFly2 drafter を使った speculative decode の選択を制御します。通常実行では `dfly2` を明示した場合にだけ生成時の speculative decode を使い、`--serve` では既定の `auto` がモデル内の drafter tensors と chunk サイズを見て利用可否を決めます。DFly2 の draft 候補は target 側の検証と組み合わせて生成されます。

## 使い方

```sh
# 通常実行で DFly2 speculative decode を指定する
strata-hy4-sycl --model SQ32.strata --engram Engram-Q8.strata \
  --tokens ids.txt --gen 32 --draft dfly2

# engine line protocol で起動し、モデル・chunk 条件に応じて DFly2 を自動選択する
strata-hy4-sycl --serve --native SQ.strata --engram ENG.strata --chunk 8

# serve で DFly2 を必須にする。モデルに drafter がない、chunk が 8 未満、
# または drafter 初期化に失敗した場合は起動エラーになる
strata-hy4-sycl --serve --native SQ.strata --engram ENG.strata \
  --chunk 8 --draft dfly2
```

## 値と既定値

- `--draft` は次の引数を文字列として受け取り、同じオプションを複数回指定した場合は最後に読んだ値が残ります（`engine/src/hy4flash/sycl/sy_main.cpp:107-115,179`）。
- 通常実行では省略時に `off` です。通常実行経路では値の許容リスト検証がなく、`draft == "dfly2" && --gen > 0` のときだけ speculative decode を有効にします。したがって `auto` や未定義の文字列は通常実行では DFly2 を有効にしません（同 `sy_main.cpp:250,279`）。
- `--serve` では省略時に `auto` に置き換わり、明示値は `off`、`dfly2`、`auto` のみ受理されます。それ以外は `ERR --draft <値>: expected off, dfly2 or auto` を標準出力へ出して終了コード 2 で終了します（同 `sy_main.cpp:215-225,241`）。
- 値のない指定は parser が `ERR --draft needs a value` を標準出力へ出し、終了コード 2 で終了します（同 `sy_main.cpp:109-114,179`）。空文字列を値にすると `draft.empty()` と判定され、通常実行は `off`、serve は `auto` 相当になります（同 `sy_main.cpp:241,250`）。

## 実行時の動作

### 通常実行

`dfly2` を指定すると、モデルの load、runner 初期化、expert pool の準備後に `DFly2::init` を実行し、その後に入力の prefill を始めます。初期化失敗時は標準エラーへ `dfly2: <理由>` を出し終了コード 1 です。初期化が成功しても、実際に `Spec::run` を呼ぶのは `--gen` が正数で speculative mode になった場合です。生成中に spec が失敗すると `spec: <理由>` を標準エラーへ出して終了コード 1 になります（`engine/src/hy4flash/sycl/sy_main.cpp:255-317,344-395`）。

### `--serve`

serve 起動時、モデル manifest に DFly2 tensors があるかを確認します。`auto` は値が `off` でなく、tensors があり、`--chunk` が 8 以上なら speculative decode を試みます。`dfly2` は tensors がない場合、chunk が 8 未満の場合、または `DFly2::init` に失敗した場合に `ERR --draft dfly2: ...` を標準出力へ出して終了コード 2 で拒否されます。`auto` で初期化に失敗した場合はエラーを返さず `use_spec` が false のまま通常 decode へ進みます。`off` は drafter を使いません（`engine/src/hy4flash/sycl/sy_serve.h:231-233,248-278`）。

初期化後の `INFO` 行は `drafter=dfly2` または `drafter=off` と draft window を報告し、その後 `READY` を出します。リクエストでは、speculative path が有効で、新規 token 上限が正数、かつ画像入力でない場合に `Spec::run` を使います。それ以外のリクエストは通常の decode 経路です。成功時の token や完了状態は line protocol の `T` / `DONE` 行で返り、spec 実行エラーは `ERR spec: ...` となり終了コード 1 です（同 `sy_serve.h:303-307,331-334,464-479`）。

## 適用条件と副作用

- DFly2 の使用には `.strata` 内の drafter tensors が必要です。serve の `auto` はそれがない場合に通常 decode へ進みますが、`dfly2` はエラーです（`engine/src/hy4flash/sycl/sy_serve.h:231-255`）。
- serve の DFly2 は `--chunk >= 8` が条件です。通常実行側には `--draft` による chunk 下限チェックはありません（`sy_main.cpp:279`; `sy_serve.h:253-256`）。
- `--serve` で条件が揃って `use_spec` になった場合、および通常実行で `--draft dfly2` を指定した場合に `Spec` を作成します。いずれも drafter 用 GPU / host バッファを確保し、speculative decode では GPU 計算を伴います（`engine/src/hy4flash/sycl/sy_dfly2.h:465-483,511-553`; `sy_main.cpp:310-316,379-386`; `sy_serve.h:271-307`）。
- 既定値と適用条件は通常実行と serve で異なります。通常実行で `--draft auto` としても自動選択にはならず、serve で省略すると `auto` です（`sy_main.cpp:215-250,279`）。

## 出力とエラー

| 条件 | 出力・終了 |
| --- | --- |
| 値の欠落 | `ERR --draft needs a value`（stdout）、終了コード 2 |
| serve で不正な値 | `ERR --draft <値>: expected off, dfly2 or auto`（stdout）、終了コード 2 |
| serve の `dfly2` で drafter tensors がない | `ERR --draft dfly2: this .strata has no DFly2 drafter tensors`（protocol stdout）、終了コード 2 |
| serve の `dfly2` で chunk が 8 未満 | `ERR --draft dfly2 needs --chunk >= 8`（protocol stdout）、終了コード 2 |
| 通常実行の DFly2 初期化失敗 | `dfly2: <理由>`（stderr）、終了コード 1 |
| serve の DFly2 初期化失敗 | `dfly2` は `ERR --draft dfly2: <理由>`（protocol stdout）、終了コード 2。`auto` は通常 decode に fallback |
| speculative decode の実行失敗 | `spec: <理由>`（通常実行 stderr）または `ERR spec: <理由>`（serve protocol stdout）、終了コード 1 |

根拠: `engine/src/hy4flash/sycl/sy_main.cpp:109-115,179,215-225,241-250,279-280,310-317,379-395`; `engine/src/hy4flash/sycl/sy_serve.h:231-278,303-307,331-334,464-479`; `engine/src/hy4flash/sycl/sy_dfly2.h:511-553`。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:93-105` — 初期状態。`draft` の初期値は空文字列。
- `engine/src/hy4flash/sycl/sy_main.cpp:107-115,179` — 共通引数ループで値を取得し `draft` に代入する parser。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248` — serve の許容値、既定 `auto`、`ServeOpts` への値の受け渡し。
- `engine/src/hy4flash/sycl/sy_main.cpp:250-317,379-395` — 通常実行の既定 `off`、有効条件、DFly2 初期化と spec decode 呼び出し。
- `engine/src/hy4flash/sycl/sy_serve.h:231-278` — manifest 判定、serve の有効条件、必須指定時の失敗と `auto` の fallback。
- `engine/src/hy4flash/sycl/sy_serve.h:303-307,331-334,464-479` — speculative runner の生成、起動時 INFO、リクエストごとの利用条件・エラー。
- `engine/src/hy4flash/sycl/sy_dfly2.h:511-553` — drafter tensors の確認と初期化用バッファ確保。

## 調査範囲

SYCL 実装の parser と通常実行・serve の使用経路を確認しました。GPU 上での実行結果、各 device での資源量、性能差はこの調査では実測していません。
