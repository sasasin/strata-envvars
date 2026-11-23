# `strata-inkling-sycl --no-dspark`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling-sycl` |
| コマンド | `strata-inkling-sycl`（SYCL 版。サブコマンドなし） |
| オプション | `--no-dspark` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

DSpark ドラフターを runner で有効化せずに初期化し、デコードを通常経路に切り替えるフラグです。省略時は有効化を許可しますが、モデルに DSpark が含まれない場合は runner 側で無効になります。これは `strata-inkling-sycl` の自己検査・ベンチマーク用実行経路に適用されます（`engine/src/inkling2/sycl/ink_sy_main.cpp:109-110,198-204,257-265`、`engine/src/inkling2/sycl/ink_sy_runner.h:223-230`）。

## 使い方

```sh
# DSpark を無効にした通常経路でベンチマークする
strata-inkling-sycl --model model.strata --bench --no-dspark
```

`--model` が必要です。`--no-dspark` 自体に引数は付けません（parser: `engine/src/inkling2/sycl/ink_sy_main.cpp:112-125,166-169`）。

## 値と既定値

値を取らない真偽フラグで、parser 内の初期値は `false` です。指定されると `no_dspark = true` になります。反復指定も同じ真偽値を維持します。数値変換やこのフラグ固有の validation はありません（`engine/src/inkling2/sycl/ink_sy_main.cpp:109-110,112-125`）。モデルが DSpark を持たない場合は、フラグを省略しても `use_dspark` は false です（`engine/src/inkling2/sycl/ink_sy_runner.h:223-230`）。

## 実行時の動作

parser はフラグを `no_dspark` に記録し、モデル読み込み後に `runner.init(..., !no_dspark, ...)` へ反転して渡します（`engine/src/inkling2/sycl/ink_sy_main.cpp:124,183,198-204`）。runner はこの値とモデルの `has_dspark` の両方が真の場合だけ `use_dspark` を有効にし、DSpark 用の KV キャッシュと作業バッファを追加確保します。無効時はこれらの runner バッファを確保せず、通常の KV・ShortConv 履歴などの初期化は続けます（`engine/src/inkling2/sycl/ink_sy_runner.h:223-260,313-326`）。

モデルのロードはこのフラグを runner に渡すより前に行われます。また SYCL モデル読み込み処理は trunk と DSpark tensor の両方をマップし、section 1 を読み込んでアップロードします。このため、`--no-dspark` がモデル内の DSpark 重みの読み込み自体を省くとは確認できません（`engine/src/inkling2/sycl/ink_sy_main.cpp:183,198-204`、`engine/src/inkling2/sycl/ink_sy_common.h:1038-1069,1072-1089`）。

`--bench` と併用すると `run_greedy_decode` に渡す speculative 設定も false になり、出力の `mode` は `plain` になります（`engine/src/inkling2/sycl/ink_sy_main.cpp:257-264`）。`--spec-check` は plain と speculative の両方を呼びますが、runner の `use_dspark` が false なら speculative 側のデコードも通常経路へフォールバックします。従ってこの組み合わせでは DSpark の有効性を比較する実行にはなりません（`engine/src/inkling2/sycl/ink_sy_main.cpp:236-249`、`engine/src/inkling2/sycl/ink_sy_main.cpp:53-61`）。`--selfcheck` と `--par-sweep` の forward 呼び出しは speculative を要求しないため、このフラグによる切り替えはありません（`engine/src/inkling2/sycl/ink_sy_main.cpp:209-218,267-280`）。

## 適用条件と副作用

SYCL 版のこの実行ファイルに限るフラグで、環境変数による上書き処理は parser 後の `IK2_EP_SPLIT` / `IK2_GPUS` にのみあります（`engine/src/inkling2/sycl/ink_sy_main.cpp:146-163`）。通常 runner 用の DSpark キャッシュ・作業領域を確保しないことで device allocation 量が変わり、起動時の stderr ログ `runner ready` は `dspark=0` と表示します（`engine/src/inkling2/sycl/ink_sy_runner.h:313-333`）。モデルの読込、通常経路の runner バッファ、指定されている他のモード処理は引き続き実行されます。

## 出力とエラー

このオプション固有の警告やエラー、終了コード分岐はありません。parser に一致しない引数は明示的なエラー分岐がなく、そのまま無視されるため、綴り間違いも報告されません（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-145`）。モデルパスが空なら使用法を stderr に出して `1` を返し、モデル読み込みまたは runner 初期化に失敗した場合も `[ERROR]` を stderr に出して `1` を返します（`engine/src/inkling2/sycl/ink_sy_main.cpp:166-169,183,201-204`）。初期化ログは stderr に出力され、DSpark の実効状態は `dspark=0` / `1` で確認できます（`engine/src/inkling2/sycl/ink_sy_runner.h:328-333`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-145` — 引数 parser。値なしフラグとして `no_dspark` に記録。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:183-204` — モデル読込と runner 初期化の順、反転した値の引き渡し、初期化失敗時の出力。
- `engine/src/inkling2/sycl/ink_sy_runner.h:223-230,313-335` — モデル有無を含む実効条件、DSpark バッファ確保、初期化ログ。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:31-99,236-265` — speculative decode の通常経路への分岐、spec-check / bench との相互作用。
- `engine/src/inkling2/sycl/ink_sy_common.h:1038-1069,1072-1089` — モデルの DSpark tensor 情報と model load 時の section 1 upload 経路。
- `docs/cli/README.md:1572-1592` — `strata-inkling-sycl` のコマンド階層と `--no-dspark` の索引リンク。

調査時の `git status --short --branch` は `## main...origin/main` で、Strata checkout に未コミット変更はありませんでした。既存バイナリの `--help` は実行していません。parser は当該ソースで確認しました。
