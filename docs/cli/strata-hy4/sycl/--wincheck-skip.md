# `strata-hy4-sycl --wincheck-skip`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4-sycl` |
| コマンド | `strata-hy4-sycl`（サブコマンドなし） |
| オプション | `--wincheck-skip` |
| 別名 | なし |
| 値 | 整数として `atoi` で変換される値 |

## 役割

`--wincheck` または `--detcheck` の比較・再現性確認を始める前に、指定数のトークンを greedy decode で進めます。プロンプト直後の状態ではなく、先行する decode を経た状態で検査したい場合に使います。

## 使い方

```sh
strata-hy4-sycl --model model.strata --tokens prompt.ids --wincheck 4 --wincheck-skip 32
strata-hy4-sycl --model model.strata --tokens prompt.ids --detcheck 5 --wincheck-skip 32
```

`model.strata` と `prompt.ids` は利用環境のモデルファイルとトークン ID 入力に置き換えます。`--wincheck` または `--detcheck` を正の値で指定しない場合、このオプションによる先行 decode は行われません。

## 値と既定値

値は必須で、`atoi` の結果が `wincheck_skip` に格納されます。未指定時は `0` です。同じオプションを複数回指定した場合は、parser が順に代入するため最後の値が残ります。明示的な範囲検証や変換エラー判定はありません。負数の場合、後段の `for (s = 0; s < wincheck_skip; ++s)` は実行されず、先行 decode はありません。値が欠けると `ERR --wincheck-skip needs a value` を stdout に出して終了コード `2` で終了します。`atoi` が受理する整数変換の詳細やオーバーフロー時の挙動は、この CLI で別途検証・規定されていません。

## 実行時の動作

通常の（非 `--serve`）実行では、入力トークン列の prefill と logits 計算を済ませた後、`--detcheck` が正ならその検査分岐で、そうでなく `--wincheck` が正なら window 検査分岐で値を読みます。各反復で現在の greedy token を `tok` に追加し、1 token の `forward_chunk` と `head` を実行して次の token を求めます。その後の検査は、この分だけ進んだ KV prefix と token 列を使います。

両方の検査オプションが正の場合は `--detcheck` 分岐が先に選ばれ、同じ skip 数を使います。`--gen` も指定されていても検査分岐が先に評価されるため、生成分岐には進みません。skip 値自体は検査モードを有効化せず、`--wincheck` と `--detcheck` の値も変更しません。

`--serve` の場合は parser 後に `hy4s_serve_main` へ移る経路で、`wincheck_skip` はサーバー設定に渡されません。そのため `--serve` 経路でこの値が使われることは確認できません。

## 適用条件と副作用

このオプションは SYCL backend の `strata-hy4-sycl` parser にあります。skip 数が正で、かつ `--wincheck` または `--detcheck` が正の場合、指定数に応じて GPU 推論の forward を追加実行します。値が大きいほど同じ処理を多く繰り返します。通常の model load、token 入力、GPU 初期化等は検査分岐より前に行われるため、この値だけでそれらの前提を省略することはできません。検査分岐を通った実行は最後に `out_dir/top5.txt`（`--out` の既定値は `.`）を書き出すため、既存ファイルがあれば上書きされます。

初期化後、`--wincheck`、`--detcheck`、または spec check が有効なときは `HY4S_VRAM_STATIC=1` を設定する処理があります。このオプション単独ではその条件を満たしません。

## 出力とエラー

skip ループ内の `forward_chunk` が失敗すると `forward: <理由>` を stderr に出して終了コード `1` で終了します。skip 数そのものを示す出力はありません。後続検査では `--detcheck` の結果（`DETCHECK ...`）または `--wincheck` の比較結果（`WINCHECK ...`）が stdout に出ます。比較結果が不一致でも、その結果出力の後は通常の後処理へ進み、該当分岐自体は失敗終了にしていません（main の末尾は終了コード `0`）。

## 根拠

- `engine/src/hy4flash/sycl/sy_main.cpp:97` — `wincheck_skip` の初期値 `0`。
- `engine/src/hy4flash/sycl/sy_main.cpp:105-115,170-172` — argv parser、値の取得、`atoi` 変換、値不足時の stdout メッセージと終了コード `2`。
- `engine/src/hy4flash/sycl/sy_main.cpp:215-248` — `--serve` が別経路へ移り、`ServeOpts` に `wincheck_skip` を渡さない箇所。
- `engine/src/hy4flash/sycl/sy_main.cpp:298-300` — 検査モード等で `HY4S_VRAM_STATIC` を設定する条件。
- `engine/src/hy4flash/sycl/sy_main.cpp:338-378` — 通常経路で検査分岐より前に入力を prefill し、logits を計算する処理。
- `engine/src/hy4flash/sycl/sy_main.cpp:409-458` — `--detcheck` 経路の skip decode、forward 失敗処理、比較結果出力。
- `engine/src/hy4flash/sycl/sy_main.cpp:459-526` — `--wincheck` 経路の skip decode、検査の前提状態、比較結果出力。
- `engine/src/hy4flash/sycl/sy_main.cpp:527-528,603-616` — `--wincheck` 分岐後に通常の `--gen` 分岐が評価される順序、`top5.txt` 出力と通常終了。
- `docs/cli/README.md:1452-1507` — `strata-hy4-sycl` の SYCL scope と対象オプションの索引登録。

調査時の Strata checkout は `main...origin/main` で、`git status --short --branch` に未コミット変更の表示はありませんでした。安全に使える同一 revision の既存 `--help` は補助資料として使用していません。
