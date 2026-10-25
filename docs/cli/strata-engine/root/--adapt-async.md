# `--adapt-async`

調査対象: Strata commit `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（ネイティブ推論エンジンの引数 parser） |
| オプション | `--adapt-async` |
| 別名 | なし |
| 値 | 整数として読み、0 は無効、0 以外は有効（内部値 1） |

## 役割

`--serve` で動く適応型 expert tier の swap を、verify window 全体が終わるまで待つ方式から、window 間に段階的に進める非同期方式へ切り替えます。resident RAM mode では swap のコピーや RAM 移動をバックグラウンド job と CUDA stream に分け、expert arena mode では主に GPU への copy-in を進めます。既定値は `0` で、同期方式です（`src/program/generate.cpp:699-702`, `10463-10514`）。

## 使い方

```sh
strata --pack ./model --serve --resident-experts --adapt-async 1
```

この例は `--serve` を有効にし、resident RAM mode を要求したうえで非同期 tier を opt-in します。実際に有効になる条件は「適用条件と副作用」を参照してください。エンジンの help も `--adapt-async 1` と `0` を説明しています（`src/program/generate.cpp:1072-1077`）。

## 値と既定値

- 値は必須です。後続 argv を `std::atoi` で整数変換し、0 なら 0、0 以外なら 1 に正規化します。したがって負数も有効扱いになり、数値として読めない文字列は `atoi` の結果が 0 となって無効扱いです。parser にこの値固有の範囲検証はありません（`src/program/generate.cpp:2416-2421`, `2626-2630`）。
- オプション省略時は `Options::adapt_async` の初期値 `0` です（`src/program/generate.cpp:699-702`）。同じオプションを複数回指定した場合、parser は各回の値を順に代入し、最後の値が残ります（`src/program/generate.cpp:2416-2421`, `2626-2630`）。
- 値を省略すると `%s needs a value` を stderr に出し、終了コード `2` で終了します（`src/program/generate.cpp:2418-2420`）。

## 実行時の動作

非同期方式が有効な場合、adaptive round の選択とコピーを一度に完了させず、window の間で段階的に進めます。resident RAM mode では退避 expert を交換 buffer に戻し、新 expert を RAM copy から GPU cache に入れ、RAM 上の配置を移し、最後に offset を反映します。window が読み取り中の slot や RAM 領域を上書きしないよう、段階ごとに CUDA event / stage の gap を使います。arena mode は arena 内の expert を保持したまま、退避・resident 状態の更新と copy-in を行います（`src/program/generate.cpp:10463-10514`）。

通常の resident RAM mode では交換用 buffer を非同期コピー向けに追加確保し、page-lock を試みます。buffer を確保できない場合、または exchange buffer を page-lock できない場合は理由を stderr に出して `adapt_async` を 0 に戻し、同期 tier を使います（`src/program/generate.cpp:8250-8258`, `8073-8075`）。非同期 worker は routing usage があり、resident complement と十分な交換容量がある場合（または arena mode）に作られ、起動時に swap 上限と interval を stderr に表示します（`src/program/generate.cpp:10532-10551`）。

## 適用条件と副作用

非同期 tier の初期 gate は次の条件を確認します。満たさない場合は `--adapt-async 1 is off (<理由>): the blocking adaptive tier` を stderr に出し、同期 tier に戻します（`src/program/generate.cpp:8066-8092`）。

- `--serve` が必要です。
- 適応 tier が有効である必要があり、`--adapt-every` と `--adapt-swaps` がともに正数である必要があります。
- resident CPU expert mode または expert arena が必要です。arena を使う layer split、および arena と `--pipeline-windows 2` の組み合わせは無効です。
- `--batch` 使用時の `--batch-groups` が 1 より大きい構成、`--peer-device`、`--remote-expert-opt` とは併用できません。
- `--pipeline-windows 2` は `STRATA_PIPELINE_ADAPT_ASYNC=0` で無効化できます。この環境変数が 0 の場合、pipeline と非同期 tier の組み合わせを同期 tier に戻します。自動 pipeline の選択条件にも `!o.adapt_async` が含まれます（`src/program/generate.cpp:4253-4271`, `8077-8092`）。
- layer split が 3 stage 以上の pipeline では `--adapt-async` と併用できません（`src/program/generate.cpp:4273-4288`）。

help は resident RAM mode または arena、single GPU を opt-in の用途として説明しています（`src/program/generate.cpp:1074-1077`）。source では layer split 上の pipeline との互換処理も実装されているため、上記 gate と組み合わせて判断してください。

arena mode では `STRATA_ADAPT_PICK_INLINE`（既定 1）、`STRATA_ADAPT_ASYNC_WAIT`（既定 1）、`STRATA_ADAPT_ASYNC_BATCH`（既定 0、0 は tick あたり全 copy）が選択動作を調整します。これらは arena 使用時だけ読み取られます（`src/program/generate.cpp:10535-10543`）。非同期 swap のタイミングによって、どの verify window が swap-in 済み expert を最初に使うかが変わり得るため、結果は bit-exact ではありません（`src/program/generate.cpp:10475-10480`; help の説明は `src/program/generate.cpp:1074-1077`）。

## 出力とエラー

適用条件を満たさない場合や、必要な exchange buffer の確保・page-lock に失敗した場合は stderr に理由を表示して同期 tier に戻します。これらの条件では、このオプション単独を理由に終了するのではなく fallback する実装です（`src/program/generate.cpp:8073-8092`, `8250-8258`）。非同期 worker が作成されると `strata serve: adaptive tier asynchronous (--adapt-async 1): ...` を stderr に出します（`src/program/generate.cpp:10544-10551`）。値不足は終了コード `2` です（`src/program/generate.cpp:2418-2420`）。

## 根拠

- parser・値変換・既定値: `src/program/generate.cpp:699-702`, `2416-2421`, `2626-2630`
- help 表示: `src/program/generate.cpp:1072-1077`
- 条件判定・同期 fallback: `src/program/generate.cpp:8066-8092`, `8250-8258`, `8310`
- 自動 pipeline / batch との関係: `src/program/generate.cpp:4253-4288`, `5280-5297`
- worker の作成、環境変数、非同期 round の処理: `src/program/generate.cpp:10463-10551`

