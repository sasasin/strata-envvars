# `strata-hy4-sycl --serve --session-reuse`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-sycl` |
| コマンド | `strata-hy4-sycl --serve`（SYCL） |
| オプション | `--session-reuse` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換。0 は無効、0 以外は有効 |

## 役割

`--serve` の複数リクエスト間で、直前のリクエストまでに計算した prompt の KV を保持し、次の prompt が同じ prefix を含む場合に再利用します。完全な延長なら既計算部分を飛ばし、一部の prefix 一致なら条件を満たす位置まで戻して再計算を減らします。対象は SYCL エンジンの server line protocol です。通常の非 serve 実行では parser が値を受け取りますが、serve 用設定へ渡されないため効果はありません（`engine/src/hy4flash/sycl/sy_main.cpp:100-104,215-248`）。

## 使い方

```sh
# server 起動時にリクエスト間の prompt KV 再利用を有効化
strata-hy4-sycl --serve --native model.strata --engram engram.strata --session-reuse 1

# 再利用を無効化（省略時と同じ設定）
strata-hy4-sycl --serve --native model.strata --engram engram.strata --session-reuse 0
```

## 値と既定値

値は必須です。parser は `atoi` の結果が 0 かどうかだけで bool に変換し、既定値は `false`（無効）です。したがって `0` は無効、`1` や `-1` など 0 以外は有効です。厳密な数値 validation はありません。数値として先頭から解釈できない値は `atoi` により 0 となり、無効扱いです。同じオプションを複数回指定すると parser の走査順で値が上書きされ、最後の指定が残ります（`engine/src/hy4flash/sycl/sy_main.cpp:99-115,130-133`）。

値を省略して引数末尾に置くと、`ERR --session-reuse needs a value` を stdout に出して終了コード 2 で終了します（`engine/src/hy4flash/sycl/sy_main.cpp:107-115`）。

## 実行時の動作

serve 設定に bool を渡し（`engine/src/hy4flash/sycl/sy_main.cpp:226-248`）、有効時は前回の prompt token と KV がある場合に prefix を比較します。前回 prompt 全体と一致し、新 prompt がさらに長ければその位置から処理を再開します。部分一致では 4 token 単位に揃えた位置が IndexPool と SWA ring の安全条件を満たす場合に限り、その位置から再開します。再開時は stdout に `RESUME <位置>` が出て、通常の完了行 `DONE` の末尾にも再利用開始位置が記録されます（`engine/src/hy4flash/sycl/sy_serve.h:408-424,526`）。一致しない場合や条件を満たさない場合は prompt の先頭から処理します。

この状態は server プロセス内の token 配列と GPU 上の KV を使うもので、文書化されたファイルへの永続化はありません。画像を含むリクエストでは prefix 再利用を行わず、リクエスト後の `fwd` も 0 に戻します（`engine/src/hy4flash/sycl/sy_serve.h:325-327,351-379,393-407,523`）。

## 適用条件と副作用

- 再利用が働くのは `--serve` のリクエスト処理だけです。通常実行の token-file 経路ではこの値を参照しません（`engine/src/hy4flash/sycl/sy_main.cpp:215-248,250-285`）。
- server を起動した時点で `INFO` 行に `session_reuse=0|1` が出ます（`engine/src/hy4flash/sycl/sy_serve.h:331-333`）。
- 空 prompt や context 超過などのリクエストはエラー応答で処理を続けます。forward/spec の実行失敗は `ERR forward` / `ERR spec` を返して server 関数を終了します。これらはオプション値自体の validation ではありません（`engine/src/hy4flash/sycl/sy_serve.h:343-345,380-392,451-454,518-520`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:99-115,130-133` — parser の初期値、値取得、整数変換。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248` — serve 経路と `ServeOpts` への受け渡し。
- `engine/src/hy4flash/sycl/sy_serve.h:325-327,408-424,523-526` — 保持状態、prefix 判定、再開出力、画像時の無効化、完了行。
- `engine/src/hy4flash/sycl/sy_serve.h:331-333` — 起動時 `INFO` と `READY` 出力。
