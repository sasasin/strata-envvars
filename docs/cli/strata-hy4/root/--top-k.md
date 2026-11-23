# `strata-hy4 --top-k`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（トップレベル） |
| オプション | `--top-k` |
| 別名 | なし |
| 値 | 整数。parser に範囲検証はない。確率的サンプリングで使う候補数は 1〜64 に制限される |

## 役割

非対話の `strata-hy4` 実行で、確率的サンプリングに使う logits 上位候補数を指定する。生成結果に影響するのは DFly2 の speculative generation で temperature が正の確率的サンプリングを行う場合に限られ、greedy 生成には作用しない。

## 使い方

```sh
strata-hy4 --model model.strata --tokens ids.txt --draft dfly2 --gen 32 --temperature 0.8 --top-k 20
```

`--temperature` を正にして DFly2 生成を行う例。モデルとトークン ID ファイルは実際の入力に置き換える。

## 値と既定値

- parser は `atoi` で値を `int` に変換する。`--top-k` の既定値は `SampleOpts::top_k = 64`（`engine/src/hy4flash/run/hy4_main.hip.cpp:365,418`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35`）。
- CLI parser に範囲検証や変換エラー処理はない。整数として解釈できない値は `atoi` により 0 となり、後段で 1 に補正される。負数も同様に 1 に補正される。64 より大きい値は 64 に制限される（`engine/src/hy4flash/run/hy4_dfly2.hip.h:59-60,117`）。
- 複数回指定した場合は引数走査で同じフィールドを再代入するため、後の指定が残る（`engine/src/hy4flash/run/hy4_main.hip.cpp:375-384,418`）。
- 値を省略すると `nxt()` が `ERR --top-k needs a value` を標準出力へ出し、flush 後に終了コード 2 で終了する（`engine/src/hy4flash/run/hy4_main.hip.cpp:377-382`）。

## 実行時の動作

parser は値を `cli_samp.top_k` に保存する。CLI の DFly2 生成モードは `--draft dfly2`、`--gen` が正、かつ `--dfly-alloc-only` でない場合に選ばれる（`engine/src/hy4flash/run/hy4_main.hip.cpp:486,701`）。この分岐では `temperature <= 0` かつ penalty 無効なら `SampleOpts` 自体を `Spec::run` に渡さず、正の temperature または penalty があるときだけ渡す（同 `:992-1000`、`engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35`）。従って `--top-k` 単独ではサンプリングに切り替わらず、既定 temperature 0 のままでは候補数設定も生成結果に影響しない。penalty のみ有効で greedy の場合は sampler が渡るが、分布処理は上位候補の先頭（argmax）を返すので K による結果の変化はない（`engine/src/hy4flash/run/hy4_dfly2.hip.h:74-77,133-135`）。

サンプリング経路では、過去トークンへの penalty 適用後の logits から上位 K 件を選び、その候補上で temperature softmax を計算する。DFly2 の全 logits 分布・候補部分集合のどちらも K を `[1, 64]` に丸める（`engine/src/hy4flash/run/hy4_dfly2.hip.h:41-86,109-145`）。その後の `min_p`、`top_p` のフィルタリングにも同じ `SampleOpts` が使われる（同 `:87-105`）。

この CLI 値は `--serve` 用の `ServeOpts` へコピーされないため、serve 起動時の `--top-k` はプロトコル要求のサンプリング設定を変更しない（`engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611`、`engine/src/hy4flash/run/hy4_serve.hip.h:43-67`）。serve プロトコルには別途 `top_k=` キーがあるが、CLI オプションとは別の入力である（`engine/src/hy4flash/run/hy4_serve.hip.h:137-180`）。通常の非 speculative 生成は各ステップで `k_argmax` を起動するため、この `--top-k` は使わない（`engine/src/hy4flash/run/hy4_main.hip.cpp:1018-1073`）。

また、`--ab` による plain/DFly2 比較では、比較内の `Spec::run` 呼び出しに sampler 引数を渡していないため、CLI のサンプリング設定は比較生成へ反映されない（`engine/src/hy4flash/run/hy4_main.hip.cpp:914-964`）。

## 適用条件と副作用

- 対象は索引に記載された CUDA/HIP の `strata-hy4`（`engine/src/hy4flash/run/hy4_main.hip.cpp`）であり、Metal / SYCL の別ツールにはこの文書の挙動を適用しない（`docs/cli/README.md:1277-1282`）。
- DFly2 の speculative generation が失敗すると `spec: <理由>` を標準エラーへ出して終了コード 1 となる（`engine/src/hy4flash/run/hy4_main.hip.cpp:1002-1005`）。成功時は生成 ID を標準出力へ出し、`<out>/gen_ids.txt` を書き込む（同 `:1006-1011`）。既定の出力ディレクトリは `.`（同 `:347`）。
- `--top-k` 専用の警告・エラーや出力ファイルは確認できなかった。`--top-k` の値に関する追加 validation、境界外値の拒否、負数・不正文字列をエラーにする処理はない。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:365,416-420` — `SampleOpts` の生成と sampler 関連 CLI 引数の parser。`--top-k` は `atoi` で `cli_samp.top_k` に設定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:377-382,498-505` — 値欠落時の標準出力・終了コード 2、および未知引数の失敗経路。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-577,611` と `engine/src/hy4flash/run/hy4_serve.hip.h:43-67` — serve 設定への転送項目。`cli_samp` / `top_k` は転送されない。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:701,992-1005,1018-1073` — speculative mode の条件、`SampleOpts` を渡す条件、通常 decode の argmax 経路、および speculative 失敗処理。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:25-35,41-105,109-145` — 既定 sampler 値、greedy 判定、全 logits / 候補集合での K 制限とサンプリング処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:1006-1011` — speculative decode の標準出力と `gen_ids.txt` 書き込み。
- `engine/src/hy4flash/run/hy4_serve.hip.h:137-180` — serve プロトコルの別個の `top_k=` 設定。
