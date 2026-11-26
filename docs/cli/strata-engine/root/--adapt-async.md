# `strata --adapt-async`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。`--serve` 時に適用） |
| オプション | `--adapt-async` |
| 別名 | なし |
| 値 | 値を取る。`atoi` で整数変換し、0 は blocking、0 以外は asynchronous の要求として扱う |

## 役割

適応型 expert tier の交換を、decode/verify window が一巡するまで同期的に待つ代わりに、バックグラウンド job thread で進める指定です。明示 `1` は asynchronous tier を要求し、`0` は blocking tier を選びます。対象は `--serve` の resident RAM mode（`--resident-experts` など）または expert arena で、arena では交換 round は GPU への copy-in のみです。この機能は実行ごとに結果が bit-exact になるとは限りません（`engine/src/program/generate.cpp:1057-1062,1499-1504`）。

## 使い方

```sh
# 適応 tier を有効にして非同期交換を要求する（MODEL.gguf は実際のモデルパスに置き換える）
strata --serve --model MODEL.gguf --resident-experts --adapt-every 100 --adapt-swaps 32 --adapt-async 1

# 明示的に blocking tier を選ぶ
strata --serve --model MODEL.gguf --resident-experts --adapt-every 100 --adapt-swaps 32 --adapt-async 0
```

`--adapt-every` と `--adapt-swaps` が正であることが適応 tier の前提です。実際のモデル引数・serve 設定に合わせて指定してください。

## 値と既定値

- `--adapt-async` の parser は次の argv を `atoi` で読み、0 以外を `1`、0 を `0` にして保存します。したがって `1` / `0` のほか、`2` や `-1` も asynchronous 要求になります。数値として読めない文字列や空文字列は `atoi` の結果が 0 となり、blocking 指定として扱われます。値の範囲検証や専用エラーはありません（`engine/src/program/generate.cpp:3842-3847,4061`）。
- 値が欠けると `--adapt-async needs a value` を stderr に出して終了コード 2 で終了します。オプションを複数回指定すると、引数走査中に同じフィールドへ順に代入されるため最後の指定が残ります（同: `3842-3847,4061`）。
- オプション省略時の `adapt_async` 初期値は 0 ですが、未指定を示す別フィールドも保持されます。自動選択条件を満たす場合に限り、serve セッション中の計測で asynchronous tier を試します。`STRATA_ADAPT_ASYNC=0` はこの自動選択を止めます。明示 `--adapt-async 0` も自動選択を止めます（`engine/src/program/generate.cpp:1057-1062,11774-11795`; `engine/include/strata/core/adapt_async_default.hpp:35-60`）。

## 実行時の動作

明示 `1` または自動選択により tier が有効になった場合、適応交換用の job thread と cache home を準備し、expert の cache/RAM 間の交換や arena からの copy-in を decode window 間で進めます。resident RAM mode では交換 buffer を追加で確保し、page-lock できることを確認します。初期ログには asynchronous tier、round あたりの swap 上限、round の間隔が stderr に出ます（`engine/src/program/generate.cpp:12166-12180,15582-15616`; job thread: `engine/src/program/generate.cpp:2454-2476`）。

オプションを省略した自動選択は、CUDA build、`--serve`、有効な適応 tier、expert arena、単一 GPU、pipeline windows なし、batch slots なし、peer/remote expert tier なし、`STRATA_ADAPT_OVERLAP` なし、`STRATA_ADAPT_FETCH` が無効、かつ `STRATA_ADAPT_ASYNC` が 0 でない、など全条件が成立する場合に限られます。HIP build では自動選択しません（`engine/src/program/generate.cpp:11777-11794`; `engine/include/strata/core/adapt_async_default.hpp:19-60`）。適用されると blocking tier で warm-up 64 windows、その後 64 windows を計測し、window の待ち時間が計測時間の 5% 以上なら asynchronous tier を試します。試行開始後4 windowsを除外して64 windowsを計測し、ms/token が blocking 計測より悪化しなければそのセッション中は維持し、悪化すれば blocking に戻ります（`engine/include/strata/core/adapt_async_default.hpp:63-106`; ログと切替: `engine/src/program/generate.cpp:23163-23183`）。

## 適用条件と副作用

- 明示 `1` は `--serve`、`--adapt-every > 0` と `--adapt-swaps > 0`、resident RAM mode・`--resident-experts`・expert arena のいずれかを必要とします。arena では layer split と `--pipeline-windows 2` は不可です。さらに `--batch` と `--batch-groups > 1` の組合せ、peer device、remote expert optimization は不可です。pipeline windows の resident mode は `STRATA_PIPELINE_ADAPT_ASYNC=0` でも無効になります（`engine/src/program/generate.cpp:11796-11811`）。条件を満たさない要求は stderr に `strata generate: --adapt-async 1 is off (<理由>): the blocking adaptive tier` を出し、blocking tier へ戻します。
- `--adapt-async 1` は Windows HIP build で既定拒否されます。`STRATA_WIN_HIP_RISKY=1` による解除時は警告を出して後続条件へ進みます（`engine/src/program/generate.cpp:2259-2265,11761-11768`）。この環境変数の説明は [STRATA_WIN_HIP_RISKY](../../../envvars/STRATA_WIN_HIP_RISKY.md) を参照してください。
- resident RAM mode で async 用の交換 buffer を確保できない場合、最大192 swap分を要求し、96より大きい要求で失敗した際は96で再試行します。再試行も失敗する、buffer を page-lock できない、または resident RAM mode が実際には稼働していない場合は理由付きで blocking に戻します（`engine/src/program/generate.cpp:12166-12180,12257-12258`）。
- asynchronous tier は helper thread と GPU transfer を伴います。実行時に adaptive refill が失敗すると `ERR an adaptive refill failed` を出す経路があります（`engine/src/program/generate.cpp:22958-22960,23159-23161`）。GPU/backend ごとの実行成否や性能は、このソース調査では測定していません。

## 根拠

- `engine/src/program/generate.cpp:1057-1062` — 既定値と「未指定」・自動選択状態を分ける option fields。
- `engine/src/program/generate.cpp:3842-3847,4061` — 値の取得、欠値エラー、`atoi` による0/非0変換。
- `engine/src/program/generate.cpp:1499-1504` — engine usage の値表記と説明。
- `engine/src/program/generate.cpp:11761-11811` — Windows HIP guard、自動選択入力、明示要求の適用条件とblocking fallback。
- `engine/include/strata/core/adapt_async_default.hpp:35-60,63-106` — 環境変数の読み取り、自動選択条件、計測・試行の閾値と継続判定。
- `engine/src/program/generate.cpp:12166-12180,12257-12258,15582-15616,23163-23183` — buffer確保/fallback、job thread 起動、起動・計測・切替ログ。
- `engine/src/program/generate.cpp:22958-22960,23159-23161` — adaptive refill 失敗時のエラー出力。

調査範囲は上記 revision の Strata ソースに限ります。CLI help は実行せず、usage 文字列を parser と照合しました。
