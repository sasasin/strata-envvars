# `--gen`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling`（CUDA/HIP） |
| オプション | `--gen` |
| 別名 | なし |
| 値 | 整数として `std::atoi` で変換される値 |

## 役割

`--gen N` は、ベンチマークでは生成デコードの目標ステップ数を指定し、直接生成では出力するトークン ID の最大個数を指定します。parser は同じ変数に値を格納するため、`--bench` を付けるかどうかで処理と値の適用条件が変わります。

## 使い方

```sh
# ベンチマークで生成デコードを最大 64 ステップ実行
strata-inkling --bench --native ./model.strata --gen 64

# モデルの直接生成で最大 32 個のトークン ID を出力
strata-inkling --native ./model.strata --gen 32
```

## 値と既定値

- 値は `std::atoi` で整数化されます。明示的な数値形式・範囲検証はなく、整数として解釈できない値は `atoi` の結果として `0` になります。値を省略すると parser が `missing value after --gen` を stderr に出し、終了コード `2` で終了します。 (`engine/src/inkling2/ink_main.cpp:376-383,480-481`)
- 省略時は `bench_gen = 32` です。`--gen` を複数回指定した場合は、引数を順に処理して同じ変数へ代入するため最後の値が残ります。 (`engine/src/inkling2/ink_main.cpp:376,379-384,480-481`)
- 負数や `0` も parser では拒否されません。ベンチマークではデコード反復が行われず、直接生成でも生成ループが実行されません。 (`engine/src/inkling2/ink_main.cpp:153-157,600`)

## 実行時の動作

`--bench` を指定すると、合成 prompt の長さ（既定 `64`、`--prompt-len` で変更）と `--gen` の値を使って計測します。モデルの backend 初期化後、prompt が実効 context 以上なら `max(1, eff_ctx - 1)` に縮め、生成長が残り context を超える場合は `max(0, eff_ctx - prompt_len)` まで縮めて stderr に補正内容を出します。したがってベンチマークの生成数は指定値以下です。 (`engine/src/inkling2/ink_main.cpp:376,478-481`; `engine/src/inkling2/ink_main.cpp:130-157`)

`--bench` を指定しない場合は直接生成モードとなり、モデルを開いて backend と slot を初期化した後、prompt の logits から最大 `bench_gen` 回サンプリングします。既定 prompt はソース内の固定 token ID 列で、`--prompt-ids` を指定するとその ID 列を使用します。`--gen` 自体は生成上限として使われ、`--max-context` 由来の slot 上限に合わせた事前の生成長クランプはありません。EOS または EOT token を得ると、指定数より前でも終了します。 (`engine/src/inkling2/ink_main.cpp:551-593,595-613`)

直接生成の出力はサンプリングした token ID の整数列で、カンマ区切りで stdout に逐次出力されます。乱数生成器の seed は `42` に固定されています。`--temp` は同じ `SampleOpts` の temperature に設定されます。 (`engine/src/inkling2/ink_main.cpp:595-605`)

モード選択との相互作用として、`--bench` はモデル読込前に dispatch されるため、同時に指定した `--serve` より先に実行されます。`--serve` のみの場合は serve loop に入り、直接生成ループへ進まないので `--gen` は使われません。 (`engine/src/inkling2/ink_main.cpp:544-549,551-573,575-600`)

## 適用条件と副作用

- `--gen` は `strata-inkling` の CUDA/HIP parser のトップレベル option です。索引上、Metal と SYCL は別ツール ID・parser scope であり、この文書の値規則を適用しません。 (`docs/cli/README.md:1511-1523,1549-1557,1572-1578`)
- ベンチマークではモデルを読み込み backend を初期化し、prompt prefill と decode を実行して性能値を stdout に表示します。直接生成ではモデル読込、backend 初期化、slot 確保、prefill/decode を行います。GPU/backend の利用可否や context 上限は `--gen` の値だけでは決まらず、backend・モデル・他の設定に依存します。 (`engine/src/inkling2/ink_main.cpp:130-165,544-613`)
- `--serve` 単独では解析されても直接生成の上限に反映されません。サーバーリクエスト側の生成長は別のプロトコル入力で扱われます。 (`engine/src/inkling2/ink_main.cpp:392-395,480-481,571-600`; `engine/src/inkling2/ink_serve.h:523-530`)

## 出力とエラー

- ベンチマークでは実際に使用した prompt / gen 数、prefill・decode の計測値を `[bench] ...` 行として stdout に出します。context による gen の切り詰めは stderr に表示します。 (`engine/src/inkling2/ink_main.cpp:153-157,243-249`)
- 直接生成では token ID を stdout に出します。モデルを開けない、backend 初期化できない、slot 確保できない、prefill/decode に失敗した場合は各段階のエラーを stderr に出し、終了コード `1` で終了します。prompt ID 列の parse 失敗は stderr に理由を出して終了コード `2` です。 (`engine/src/inkling2/ink_main.cpp:558-569,576-593,608-610`)
- `--gen` の値自体に対する範囲エラーはありません。直接生成時に指定数が利用可能 context を超えた場合の最終挙動は backend の処理結果に依存し、この parser 側では事前に切り詰めません。 (`engine/src/inkling2/ink_main.cpp:480-481,575-613`)

## 根拠

- `engine/src/inkling2/ink_main.cpp:376,379-384,480-481` — 既定値、値取得、`atoi` 変換、および値省略時の失敗。
- `engine/src/inkling2/ink_main.cpp:130-157,194-249,549` — ベンチマークへの値伝達、実効 context によるクランプ、decode 回数、結果出力。
- `engine/src/inkling2/ink_main.cpp:551-613` — 直接生成への分岐、prompt、生成 loop、token ID 出力と失敗経路。
- `engine/src/inkling2/ink_main.cpp:544-573` — 各モードの dispatch 順序と serve 経路。
- `engine/src/inkling2/ink_serve.h:523-530` — server リクエストの生成上限が CLI の `bench_gen` ではなく要求内容から設定されること。
- `docs/cli/README.md:1511-1523,1549-1557,1572-1578` — `strata-inkling` が CUDA/HIP scope であること、および Metal/SYCL parser と別文書に分かれること。索引は配置・scope の確認にのみ使用。
