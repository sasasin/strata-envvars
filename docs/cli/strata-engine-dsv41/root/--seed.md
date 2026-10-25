# `--seed`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine-dsv41` |
| コマンド | `strata-dsv41`（DeepSeek V4.1 用の独立エンジン） |
| オプション | `--seed` |
| 別名 | なし |
| 値 | 10進表記を `unsigned long long` に変換する seed 値 |

## 役割

通常の token ID 入力から続けて生成する経路で、サンプラーに渡す Philox seed を指定します。seed と生成位置の counter がサンプルの乱数値に使われます。結果は logits と sampler の設定にも依存します。

## 使い方

モデルの pack と token ID 列を指定して生成します。以下は温度サンプリングを有効にする例です。

```sh
strata-dsv41 --pack ./model/maya-ds4 --ids 0,128803,42 --n 32 --temperature 0.7 --seed 12345
```

`--ids` は prompt の token ID 列、`--n` は生成数です。`--temperature` の既定値は `0` なので、seed の抽選効果を使うには正の温度も指定してください（`src/dsv41/ds4_main.cpp:1191-1195,1246-1247,1282-1285,1385-1387`）。

## 値と既定値

- 値は必須です。省略すると `--seed needs a value` を stderr に出して終了コード `2` で終了します（`src/dsv41/ds4_main.cpp:1202-1207,1247`）。
- 未指定時の初期値は `1` です（`src/dsv41/ds4_main.cpp:1194`）。
- 値は `std::strtoull(..., 10)` で変換され、変換末尾やエラー状態の検査はありません。したがって、厳密な数値形式 validation はなく、変換できない先頭値はライブラリ関数の規則に従います。境界外入力をどう扱うかは実行環境の C ライブラリに依存します（`src/dsv41/ds4_main.cpp:1247`）。
- 同じオプションを複数回指定した場合、引数走査中に同じ変数へ再代入されるため最後の値が残ります（`src/dsv41/ds4_main.cpp:1200-1208,1247`）。

## 実行時の動作

通常の生成経路では、prompt の処理後、`--n` が正の場合に最初の token を `m.sample()` で選び、以後の decode round にも同じ `cli_seed` と更新される counter を渡します。speculative decode が有効な round では drafter と verifier にも同じ seed/counter が渡され、採択数に応じて counter が進みます（`src/dsv41/ds4_main.cpp:167-203,1382-1403`）。モデル側は seed と counter を sampler parameter に設定して `sample_tokens()` を呼びます（`src/dsv41/ds4_model.cu:8966-8982`）。サンプラーの通常抽選は `philox_uniform(p.seed, p.counter + t)` を使います（`src/dsv41/vendor/sampler.cu:403-449`）。

このオプションは通常生成経路の seed 変数にだけ代入されます。`--serve` はモデル load 後、通常生成処理に入る前に別の serve 処理へ戻るため、CLI の `--seed` は serve リクエストの seed にはなりません。serve プロトコルではリクエストごとの `seed=N` を別途解釈します（`src/dsv41/ds4_main.cpp:1247,1291-1296`; `src/dsv41/ds4_main.cpp:206-211,292-310`）。score、profile、spec-eval の各モードも通常生成処理より先に分岐するため、この CLI seed はそれらの処理に適用されません（`src/dsv41/ds4_main.cpp:1297-1302`）。

## 適用条件と副作用

- `--temperature` の既定値は `0.0` で、モデル側の `sample()` は `temperature <= 0.0` のとき `greedy` を有効にします。この場合、seed による抽選は行われません。正の温度で通常生成するときに seed がサンプラーの乱数系列に関与します（`src/dsv41/ds4_main.cpp:1193-1194,1246-1247,1385-1402`; `src/dsv41/ds4_model.cu:8966-8977`）。
- 通常生成では正の温度のとき top-k は `64`、top-p は `1.0`、min-p は `0.0` として sample/round に渡されます。seed 自体はこれらの値を変更しません（`src/dsv41/ds4_main.cpp:1385-1402`）。
- seed は生成 token 選択の入力です。ファイルや環境設定を変更する処理はありません。生成 token ID は stdout にカンマ区切りで出力され、進捗などは stderr に出ます（`src/dsv41/ds4_main.cpp:1385-1415`）。

## 出力とエラー

`--seed` の値そのものを受理時に表示する処理はありません。引数値の欠落では stderr にエラーを出し終了コード `2`、未知のオプションも usage を stderr に出して終了コード `2` です（`src/dsv41/ds4_main.cpp:1202-1207,1266-1272`）。温度が正の通常生成では、生成 token ID が stdout に出力されます（`src/dsv41/ds4_main.cpp:1395-1415`）。

## 根拠

- `src/dsv41/ds4_main.cpp:1187-1208,1246-1273` — CLI 引数 parser、seed 初期値、必須値の扱い、未認識オプション。
- `src/dsv41/ds4_main.cpp:1282-1302,1382-1415` — モード選択、通常生成での seed/counter 使用と出力。
- `src/dsv41/ds4_model.cu:8966-8982` — seed を sampler parameter に設定し、token を選ぶ箇所。
- `src/dsv41/vendor/sampler.cu:403-449` — top-p/min-p/temperature と Philox seed/counter を使う抽選経路。
- `src/dsv41/ds4_main.cpp:85-94` — usage 表示。parser は `--temperature` と `--seed` を受理しますが、この synopsis には両方とも記載されていません。索引の対象 revision に対して help 表示は実行していません。
