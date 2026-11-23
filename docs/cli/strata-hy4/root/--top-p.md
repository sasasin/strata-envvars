# `--top-p`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4` |
| オプション | `--top-p` |
| 別名 | なし |
| 値 | 浮動小数点数。parser は `atof` で `float` に変換する |

## 役割

`--draft dfly2` を使うオフライン生成で、確率的サンプリングの候補を確率の累積値で絞る nucleus sampling の閾値を指定します。既定の温度は 0（greedy）なので、サンプリングを有効にするには通常 `--temperature` に正数も指定します。

## 使い方

```sh
strata-hy4 --model model.strata --tokens prompt.ids --gen 128 \
  --draft dfly2 --temperature 0.8 --top-p 0.9
```

この値が使われるのは、`--draft dfly2` と正の生成数によって speculative 生成経路に入り、かつ温度が正で確率的サンプリングが有効な場合です。

## 値と既定値

- 既定値は `1.0` です。`SampleOpts` の初期値であり、parser が `--top-p` を受け取らない場合に使われます。
- parser は値を `atof` で読み、`float` に格納します。範囲検証や変換失敗の検出はありません。数値に変換できない文字列は `atof` の結果 `0` として扱われます。
- 同じオプションを複数回指定した場合、ループ中に同じフィールドへ順番に代入されるため最後の値が残ります。
- 値がない場合は `ERR --top-p needs a value` を stdout に出して終了コード 2 で終了します。

## 実行時の動作

- 確率的生成では、まず上位 `top-k` 候補（最大64件）の softmax 確率を計算し、`min-p` による候補削減の後に `top-p` を適用します。降順の確率を加算し、累積値が `top_p` 以上となる候補までを残し、その候補群の確率を再正規化して抽選します。したがって `--top-k` と `--min-p` が同時に有効な場合は、それらで絞った集合の上で閾値が働きます。
- `top_p >= 1` では累積値による追加の削減は行いません。`top_p < 1` では少なくとも先頭候補を残すため、0以下を指定しても候補数は1件です。
- 温度が0以下の場合、サンプリング関数は確率分布の計算に進まず argmax を返すため、`--top-p` は結果に影響しません。
- 通常のオフライン生成（`--draft dfly2` なし）は `k_argmax` で次の token を選び、`cli_samp.top_p` を参照しません。この経路では `--top-p` を指定しても sampling は有効になりません。
- `--serve` では CLI の `cli_samp` は `ServeOpts` に渡されません。サーバーの各 `GEN` 要求にある `top_p=<数値>` が要求ごとの `SampleOpts` に設定されます。したがって、このモードで CLI の `--top-p` をサーバー既定値として使うことはできません。

## 適用条件と副作用

このオプション自体が変更するのは生成時の候補選択です。確率的な DFly2 オフライン生成では各 token の選択結果に影響し得ます。通常の単体 argmax 生成では読み込まれても使用されません。ファイルやネットワークの副作用はオプション固有には確認できません。

## 出力とエラー

値が欠落した場合のエラーは `--top-p` を指す `ERR` 行と終了コード2です。値の形式・範囲を検証して拒否する処理は見つかりませんでした。未知のオプションは別経路で stderr に `unknown arg ...` を出して終了コード2になります。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:365` — `SampleOpts` の生成。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383` — 引数走査と、値欠落時に stdout へエラーを出して終了する処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:416-420` — `--top-p` の parser 登録と `atof` による代入。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:498-505` — 未知引数のエラーと終了コード。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:25-34` — sampler の既定値（`top_p = 1.f`）と greedy 判定。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:700-701, 992-1001` — `--draft dfly2` と `--gen > 0` による speculative モード判定、および sampler を speculative 生成へ渡す条件。
- `engine/src/hy4flash/run/hy4_spec.hip.h:197-203, 248-250` — greedy/no-penalty 時の argmax 短絡と、確率的モードの判定。
- `engine/src/hy4flash/run/hy4_dfly2.hip.h:130-163` — 温度 softmax 後、min-p、top-p の順で候補を絞り、再正規化する処理。greedy は `133-135` で先頭候補に短絡。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:1018-1073` — 通常オフライン生成が argmax kernel で次 token を選び、`cli_samp` を使わない処理。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:555-578` — `ServeOpts` の設定項目に `cli_samp` が含まれず、その他のサーバー引数だけを渡す箇所。
- `engine/src/hy4flash/run/hy4_serve.hip.h:128-179` — `GEN` ごとに `SampleOpts` を初期化し、`top_p=` キーを設定する処理。
