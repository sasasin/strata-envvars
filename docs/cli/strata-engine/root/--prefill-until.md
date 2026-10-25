# `--prefill-until`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。調査対象 checkout は `main` で `origin/main` と一致し、未コミット変更はありませんでした。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数） |
| オプション | `--prefill-until` |
| 別名 | なし |
| 値 | 整数として解釈される値。既定値は `0` |

## 役割

prompt の先頭 `P` 個の位置だけを batched prefill で処理し、後続位置を token ごとの経路で処理するための検証用オプションです。ここで `P` は最初の位置を 0 とした範囲 `[0, P)` の長さです。通常の全 prompt 入力を保ったまま prefill と token 経路を切り替えて比較する用途に使えます（`src/program/generate.cpp:643-646,15696-15698`）。

## 使い方

```sh
strata --pack MODEL --tokens-file prompt.txt --prefill 512 --prefill-until 128
```

この例は `--prefill` により batched prefill を有効にし、その prefill の対象を先頭128位置にします。`--pack` と `--tokens-file` はエンジン parser が受け取る引数です（`src/program/generate.cpp:2425-2435,2574-2583,2606`）。

## 値と既定値

- `Options::prefill_until` の初期値は `0` です。値の取得には `std::atoll` を使い、専用の範囲検証や数値形式検証はありません（`src/program/generate.cpp:643-646,2606`）。
- 値が `1` 以上かつ `n_prompt - 1` 未満のときだけ、その値を `n_batched` に採用します。それ以外（0、負数、`n_prompt - 1` 以上）は `n_prompt - 1` に置き換わり、通常どおり最後の prompt 位置以外が batched prefill の対象になります（`src/program/generate.cpp:15711`）。
- 値がない場合は parser の `next` がエラーメッセージを stderr に出して終了コード 2 で終了します（`src/program/generate.cpp:2418-2420`）。不正な文字列は `atoll` の変換結果として扱われ、明示的な拒否はありません。したがって整数以外の値を指定した場合の正確な変換結果は C ライブラリ実装に依存します。
- prompt が1位置以下、または `--prefill` の chunk が正数でない場合、batched prefill 部分自体が実行されません。この場合 `--prefill-until` による分割は行われません（`src/program/generate.cpp:621,15711-15713`）。

## 実行時の動作

`--prefill-until P` は `n_batched` を通じて `prefill.run` に渡され、batched prefill は prompt の先頭 `n_batched` 個を処理します。その直後の通常 token loop は `pos_start = n_batched` から始まり、prompt が残っていれば次の prompt token を teacher-forcing で入力しながら最後の prompt 位置まで進みます（`src/program/generate.cpp:15711,15815-15818,15849-15855,15873-15876,16084-16090`）。

この分割を有効にするには、別オプション `--prefill` で prefill chunk を正数にする必要があります。`--prefill-until` 自体は chunk の大きさや prefill の有効化を設定しません（`src/program/generate.cpp:621-624,2574-2583,15712-15713`）。

## 適用条件と副作用

- `n_prompt - 1` は最後の prompt token の位置であり、その token の予測が最初の生成 token になります。したがって既定の `0` は最後の prompt token だけを token loop に残し、それより前を batched prefill します（`src/program/generate.cpp:15696-15698,15711,16073-16080`）。
- **native pack では特に注意してください。** batched prefill の後、native pack の token loop は `pos_start` を処理する前に speculative 経路へ抜けます。よって `--prefill-until` で prompt の一部だけを batched prefill した場合、残りの prompt token はこの loop では teacher-forcing されず、prompt の続きが無視される動作になります（`src/program/generate.cpp:15849-15855,15873-15876`）。この注意は `--prefill` が有効で、`n_batched < n_prompt - 1` となる場合に当てはまります。
- 値自体によるファイル作成・上書きやネットワークアクセスは確認できません。通常の prefill のために prompt path のバッファ確保や cache slot の一時借用・返却が発生する場合がありますが、これらは `--prefill-until` 固有ではなく prefill 経路の動作です（`src/program/generate.cpp:15712-15718,15762-15779,15820-15845`）。

## 出力とエラー

parser はこの値に対する範囲エラーや警告を出しません。prefill が実行されると、処理 token 数・chunk 数などを stderr に表示します。prefill の初期化または実行に失敗した場合はエラーを stderr に出して終了コード 1 で終了します（`src/program/generate.cpp:15782-15788,15815-15819,15857-15862`）。native pack で prompt の一部が省かれる場合に専用警告を出す処理は確認できません。

## 根拠

- parser 値の既定値と宣言: `src/program/generate.cpp:643-646`
- parser の値取得: `src/program/generate.cpp:2606`
- prefill 対象数の決定・実行: `src/program/generate.cpp:15711-15713,15815-15818`
- 通常 token loop の開始位置と prompt 継続: `src/program/generate.cpp:15849-15855,15873-15876,16084-16090`
- native pack の早期離脱: `src/program/generate.cpp:15873-15876`
- parser の値不足エラー: `src/program/generate.cpp:2418-2420`
